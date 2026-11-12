"""Allowlisted workload entry point. It runs in the separately pinned CUDA environment."""

import argparse
import base64
import ctypes
import hashlib
import io
import json
import os
import threading
import time
from pathlib import Path


MODEL = 'MobileNetV3-Large IMAGENET1K_V2'


def guard_parent(pid, timeout):
    def watch():
        if os.name == 'nt':
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
            kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            handle = kernel.OpenProcess(0x00100000, False, pid)
            if handle:
                kernel.WaitForSingleObject(handle, int(timeout * 1000))
            os._exit(124)
        until = time.monotonic() + timeout
        while os.getppid() == pid and time.monotonic() < until:
            time.sleep(.25)
        os._exit(124)

    threading.Thread(target=watch, daemon=True).start()


def torch_cuda():
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError('The installed PyTorch does not expose a CUDA GPU.')
    return torch


def weights_path(torch, weights):
    filename = weights.url.rsplit('/', 1)[-1]
    return Path(torch.hub.get_dir()) / 'checkpoints' / filename


def load_weights(torch, download=False):
    from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large

    cache = Path(os.getenv('PACT_STATE_DIR', str(Path(__file__).resolve().parents[2] / '.local'))) / 'torch'
    if 'TORCH_HOME' not in os.environ:
        torch.hub.set_dir(str(cache / 'hub'))
    weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
    path = weights_path(torch, weights)
    if download and not path.is_file():
        weights.get_state_dict(progress=True, check_hash=True)
    if not path.is_file():
        raise RuntimeError('Model weights are missing. Run gpu_task.py prepare once.')
    prefix = path.stem.rsplit('-', 1)[-1]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not digest.startswith(prefix):
        raise RuntimeError('The model weights failed their upstream hash check.')
    model = mobilenet_v3_large(weights=None)
    model.load_state_dict(torch.load(path, map_location='cpu', weights_only=True))
    return model.eval(), weights, digest


def probe(engine, download=False):
    import torch

    torch.set_num_threads(2)
    model, _, _ = load_weights(torch, download=download)
    if engine == 'torch':
        torch_cuda()
        value = (torch.ones((64, 64), device='cuda') @ torch.ones((64, 64), device='cuda'))[0, 0].item()
        assert value == 64.0
        info = torch.cuda.get_device_properties(0)
        print(json.dumps({'device': info.name, 'vram_mib': info.total_memory // 1048576,
                          'torch': torch.__version__, 'cuda': torch.version.cuda, 'kernel_verified': True}))
        return
    from cuda_driver import CudaDriver, MobileNetFeatures

    generator = torch.Generator().manual_seed(2026)
    sample = torch.randn((3, 224, 224), generator=generator)
    with torch.inference_mode(), CudaDriver() as driver:
        features = MobileNetFeatures(driver, model)
        actual = torch.tensor(features.encode(sample))
        expected = torch.nn.functional.normalize(model.avgpool(model.features(sample[None])).flatten(1), dim=1)[0]
        cosine = float(torch.dot(expected, actual))
        max_error = float((expected - actual).abs().max())
        if cosine < .99999 or max_error > .0005:
            raise RuntimeError(f'GPU model did not match the CPU reference. Cosine {cosine:.8f}, max error {max_error:.8f}.')
        print(json.dumps({'device': driver.device, 'vram_mib': driver.vram_mib, 'torch': torch.__version__,
                          'cuda': driver.version, 'kernel_verified': True, 'cpu_reference_cosine': cosine,
                          'cpu_reference_max_error': max_error, 'kernels_sha256': driver.kernel_digest}))


def execute(input_path, output_path, engine):
    from PIL import Image
    import torch

    torch.set_num_threads(2)
    model, weights, digest = load_weights(torch)
    source = json.loads(input_path.read_bytes())
    if source['template'] != 'image-embeddings-v1' or not 1 <= len(source['images']) <= 16:
        raise ValueError('Invalid workload manifest.')
    preprocess = weights.transforms()
    tensors = []
    for item in source['images']:
        data = base64.b64decode(item['png'], validate=True)
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Image checksum mismatch.')
        with Image.open(io.BytesIO(data), formats=['PNG']) as image:
            tensors.append(preprocess(image.convert('RGB')))
    if engine == 'torch':
        torch_cuda()
        with torch.inference_mode():
            batch = torch.stack(tensors).cuda()
            model = model.cuda()
            began = time.perf_counter()
            features = model.features(batch)
            pooled = model.avgpool(features).flatten(1)
            result = torch.nn.functional.normalize(pooled, dim=1).cpu().tolist()
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - began
            metadata = {'device': torch.cuda.get_device_name(0), 'cuda': torch.version.cuda,
                        'peak_allocated_mib': round(torch.cuda.max_memory_allocated() / 1048576, 2)}
    else:
        from cuda_driver import CudaDriver, MobileNetFeatures

        with torch.inference_mode(), CudaDriver() as driver:
            features = MobileNetFeatures(driver, model)
            began = time.perf_counter()
            result = [features.encode(tensor) for tensor in tensors]
            elapsed = time.perf_counter() - began
            metadata = {'device': driver.device, 'cuda': driver.version, 'kernels_sha256': driver.kernel_digest,
                        'peak_allocated_mib': round(driver.peak_bytes / 1048576, 2)}
    records = []
    for item, embedding in zip(source['images'], result, strict=True):
        records.append({key: item[key] for key in ('row', 'name', 'sha256')} | {'embedding': [round(v, 8) for v in embedding]})
    manifest = {'template': source['template'], 'model': MODEL, 'weights_sha256': digest, 'backend': 'cuda',
                'torch': torch.__version__, 'engine': engine, **metadata,
                'inference_seconds': round(elapsed, 6),
                'dimension': 960, 'items': records}
    output_path.write_text(json.dumps(manifest, allow_nan=False, separators=(',', ':')), encoding='utf-8')


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('command', choices=['probe', 'prepare', 'execute'])
    cli.add_argument('--input', type=Path)
    cli.add_argument('--output', type=Path)
    cli.add_argument('--parent', type=int)
    cli.add_argument('--timeout', type=float)
    cli.add_argument('--engine', choices=['driver', 'torch'], default='driver')
    args = cli.parse_args()
    if args.command == 'execute':
        guard_parent(args.parent, args.timeout)
        execute(args.input, args.output, args.engine)
    else:
        probe(args.engine, download=args.command == 'prepare')
