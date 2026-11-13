"""MobileNetV3 inference through NVIDIA's installed CUDA Driver API."""

import ctypes as ct
import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path


U32 = ct.c_uint32
U64 = ct.c_uint64
INT = ct.c_int
PTR = ct.c_void_p
SIZE = ct.c_size_t
PTX = Path(__file__).with_name('mobilenet.ptx')


class CudaDriver:
    def __init__(self):
        self.library = ct.WinDLL('nvcuda.dll') if os.name == 'nt' else ct.CDLL('libcuda.so.1')
        self.context = PTR()
        self.module = PTR()
        self.allocations = []
        self.allocated = 0
        self.peak_bytes = 0
        self.call('cuInit', (U32,), 0)
        device = INT()
        self.call('cuDeviceGet', (ct.POINTER(INT), INT), ct.byref(device), 0)
        name = ct.create_string_buffer(256)
        self.call('cuDeviceGetName', (PTR, INT, INT), name, len(name), device)
        self.device = name.value.decode()
        size = SIZE()
        self.call('cuDeviceTotalMem_v2', (ct.POINTER(SIZE), INT), ct.byref(size), device)
        self.vram_mib = size.value // 1048576
        version = INT()
        self.call('cuDriverGetVersion', (ct.POINTER(INT),), ct.byref(version))
        self.version = f'{version.value // 1000}.{version.value % 1000 // 10}'
        self.call('cuCtxCreate_v2', (ct.POINTER(PTR), U32, INT), ct.byref(self.context), 0, device)
        try:
            code = PTX.read_bytes()
            self.kernel_digest = hashlib.sha256(code).hexdigest()
            self.call('cuModuleLoadData', (ct.POINTER(PTR), ct.c_char_p), ct.byref(self.module), code)
            self.functions = {}
            for name in ('conv', 'average', 'combine'):
                handle = PTR()
                self.call('cuModuleGetFunction', (ct.POINTER(PTR), PTR, ct.c_char_p),
                          ct.byref(handle), self.module, name.encode('ascii'))
                self.functions[name] = handle
        except Exception:
            self.close()
            raise

    def call(self, name, args, *values):
        method = getattr(self.library, name)
        method.argtypes = args
        method.restype = INT
        result = method(*values)
        if result:
            error = ct.c_char_p()
            self.library.cuGetErrorName(INT(result), ct.byref(error))
            detail = error.value.decode() if error.value else str(result)
            raise RuntimeError(f'{name} returned {detail}.')

    def malloc(self, length):
        ptr = U64()
        self.call('cuMemAlloc_v2', (ct.POINTER(U64), SIZE), ct.byref(ptr), length)
        self.allocations.append((ptr, length))
        self.allocated += length
        self.peak_bytes = max(self.peak_bytes, self.allocated)
        return ptr

    def send(self, tensor):
        array = tensor.detach().contiguous().numpy()
        destination = self.malloc(array.nbytes)
        self.call('cuMemcpyHtoD_v2', (U64, PTR, SIZE), destination, array.ctypes.data, array.nbytes)
        return destination

    def receive(self, ptr, array):
        self.call('cuMemcpyDtoH_v2', (PTR, U64, SIZE), array.ctypes.data, ptr, array.nbytes)
        return array

    def kernel(self, name, count, *args):
        pointers = (PTR * len(args))(*(ct.cast(ct.pointer(value), PTR) for value in args))
        self.call('cuLaunchKernel', (PTR, U32, U32, U32, U32, U32, U32, U32, PTR, PTR, PTR),
                  self.functions[name], (count + 127) // 128, 1, 1, 128, 1, 1, 0, None, pointers, None)

    def release(self, start):
        for ptr, length in reversed(self.allocations[start:]):
            self.call('cuMemFree_v2', (U64,), ptr)
            self.allocated -= length
        del self.allocations[start:]

    def close(self):
        if self.context:
            self.call('cuCtxDestroy_v2', (PTR,), self.context)
            self.context = PTR()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@dataclass
class Feature:
    ptr: U64
    channels: int
    height: int
    width: int

    @property
    def count(self):
        return self.channels * self.height * self.width


@dataclass
class Conv:
    weights: U64
    bias: U64
    channels: int
    channels_per_group: int
    outputs_per_group: int
    kernel: tuple[int, int]
    stride: tuple[int, int]
    padding: tuple[int, int]
    activation: int


@dataclass
class Excitation:
    reduce: Conv
    expand: Conv


@dataclass
class Block:
    layers: list
    residual: bool


class MobileNetFeatures:
    def __init__(self, driver, network, classify=False):
        import torch
        from torchvision.models.mobilenetv3 import InvertedResidual
        from torchvision.ops.misc import Conv2dNormActivation, SqueezeExcitation

        self.driver = driver
        self.layers = []
        self.torch = torch
        self.types = (Conv2dNormActivation, SqueezeExcitation, InvertedResidual)
        self.activations = {torch.nn.ReLU: 1, torch.nn.Hardswish: 2, torch.nn.Hardsigmoid: 3, type(None): 0}
        self.classifier = []
        if classify:
            first, activation, _, last = network.classifier
            # A linear layer on a pooled feature is a 1x1 convolution.
            for layer, kind in ((first, type(activation)), (last, type(None))):
                self.classifier.append(Conv(driver.send(layer.weight), driver.send(layer.bias),
                                            layer.out_features, layer.in_features, layer.out_features,
                                            (1, 1), (1, 1), (0, 0), self.activations[kind]))
        for layer in network.features:
            if isinstance(layer, InvertedResidual):
                self.layers.append(Block([self.compile(part) for part in layer.block], layer.use_res_connect))
            else:
                self.layers.append(self.compile(layer))

    def compile_conv(self, conv, activation):
        if conv.dilation != (1, 1) or conv.padding_mode != 'zeros':
            raise ValueError('The fixed workload supports zero padding and unit dilation.')
        bias = conv.bias if conv.bias is not None else self.torch.zeros(conv.out_channels)
        return Conv(self.driver.send(conv.weight), self.driver.send(bias), conv.out_channels,
                    conv.in_channels // conv.groups, conv.out_channels // conv.groups,
                    conv.kernel_size, conv.stride, conv.padding, self.activations[type(activation)])

    def compile(self, layer):
        conv_activation, excitation, _ = self.types
        if isinstance(layer, conv_activation):
            conv = self.torch.nn.utils.fusion.fuse_conv_bn_eval(layer[0], layer[1])
            return self.compile_conv(conv, layer[2] if len(layer) == 3 else None)
        if isinstance(layer, excitation):
            return Excitation(self.compile_conv(layer.fc1, layer.activation),
                              self.compile_conv(layer.fc2, layer.scale_activation))
        raise ValueError(f'Unexpected model layer {type(layer).__name__}.')

    def apply_conv(self, x, op):
        h = (x.height + 2 * op.padding[0] - op.kernel[0]) // op.stride[0] + 1
        w = (x.width + 2 * op.padding[1] - op.kernel[1]) // op.stride[1] + 1
        y = Feature(self.driver.malloc(op.channels * h * w * 4), op.channels, h, w)
        integers = (y.count, x.height, x.width, h, w, op.channels_per_group, op.outputs_per_group,
                    *op.kernel, *op.stride, *op.padding, op.activation)
        self.driver.kernel('conv', y.count, x.ptr, op.weights, op.bias, y.ptr, *(U32(v) for v in integers))
        return y

    def average(self, feature):
        result = Feature(self.driver.malloc(feature.channels * 4), feature.channels, 1, 1)
        self.driver.kernel('average', feature.channels, feature.ptr, result.ptr,
                           U32(feature.channels), U32(feature.width * feature.height))
        return result

    def combine(self, left, right, scale):
        result = Feature(self.driver.malloc(left.count * 4), left.channels, left.height, left.width)
        self.driver.kernel('combine', left.count, left.ptr, right.ptr, result.ptr,
                           U32(left.count), U32(left.width * left.height), U32(scale))
        return result

    def apply(self, x, op):
        if isinstance(op, Conv):
            return self.apply_conv(x, op)
        if isinstance(op, Excitation):
            scale = self.apply_conv(self.apply_conv(self.average(x), op.reduce), op.expand)
            return self.combine(x, scale, True)
        branch = x
        for child in op.layers:
            branch = self.apply(branch, child)
        return self.combine(branch, x, False) if op.residual else branch

    def encode(self, image):
        import numpy as np

        start = len(self.driver.allocations)
        try:
            result = Feature(self.driver.send(image), *image.shape)
            for layer in self.layers:
                result = self.apply(result, layer)
            result = self.average(result)
            for layer in self.classifier:
                result = self.apply_conv(result, layer)
            output = self.driver.receive(result.ptr, np.empty(result.channels, dtype=np.float32))
            if self.classifier:
                return output.tolist()
            scale = math.sqrt(float(np.dot(output, output)))
            if not math.isfinite(scale) or scale <= 0:
                raise RuntimeError('The GPU produced a non-finite embedding.')
            return (output / scale).tolist()
        finally:
            self.driver.release(start)
