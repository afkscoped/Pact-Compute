// Pure helpers for job detail: stage timing rows and workload-spec rows (unit-tested with `node --test`).
export const STAGE_LABELS: [string, string, string][] = [
  ['staging', 'Staging', 'Fetching and checking the input on the runner'],
  ['startup', 'Startup', 'GPU process, CUDA and model load'],
  ['compute', 'Compute', 'Model inference on the GPU'],
  ['validation', 'Validation', 'Control plane checking rows, embeddings and digests'],
  ['upload', 'Upload', 'Control plane storing the verified output'],
];

export type StageRow = { key: string; label: string; hint: string; seconds: number; share: number };

export function stageRows(stages: Record<string, number> | null | undefined): StageRow[] {
  const known = STAGE_LABELS.filter(([key]) => typeof stages?.[key] === 'number');
  const total = known.reduce((sum, [key]) => sum + (stages as Record<string, number>)[key], 0);
  return known.map(([key, label, hint]) => {
    const seconds = (stages as Record<string, number>)[key];
    return { key, label, hint, seconds, share: total > 0 ? seconds / total : 0 };
  });
}

export type Workload = {
  version: number; template_id: string; spec_sha256: string;
  runtime: { kind: string; task_sha256: string; kernels_sha256: string };
  model: { name: string; weights_sha256: string | null; digest_status: string };
  input_manifest: { artifact_id: string | null; sha256: string | null; rows: number; format: string };
  hardware: { min_vram_mib: number; gpu_count: number; backend: string; gpu_model: string | null };
  region: string | null; timeout_s: number | null;
  output_schema: { name: string; rows: number; dimension: number };
  retry: { max_attempts: number; automatic_retry: boolean; manual_resubmit: boolean };
};

export function specRows(spec: Workload): [string, string][] {
  const short = (value: string | null) => (value ? value.slice(0, 16) + '…' : 'not recorded');
  return [
    ['Template', spec.template_id + ' · spec v' + spec.version],
    ['Runtime (code digest)', short(spec.runtime.task_sha256) + ' · kernels ' + short(spec.runtime.kernels_sha256)],
    ['Model', spec.model.name + ' · ' + (spec.model.weights_sha256 ? 'weights ' + short(spec.model.weights_sha256) : spec.model.digest_status)],
    ['Input manifest', spec.input_manifest.rows + ' rows · ' + short(spec.input_manifest.sha256)],
    ['Hardware', spec.hardware.gpu_count + ' × ' + spec.hardware.backend.toUpperCase() + ' GPU, at least ' + spec.hardware.min_vram_mib + ' MiB' + (spec.hardware.gpu_model ? ', ' + spec.hardware.gpu_model : '')],
    ['Region', spec.region ?? 'not constrained'],
    ['Timeout', spec.timeout_s == null ? 'not reserved' : spec.timeout_s + ' s'],
    ['Output schema', spec.output_schema.name + ' · ' + spec.output_schema.rows + ' rows × ' + spec.output_schema.dimension + ' values'],
    ['Retries', spec.retry.automatic_retry ? 'up to ' + spec.retry.max_attempts + ' attempts' : 'no automatic retry' + (spec.retry.manual_resubmit ? '; resubmit manually' : '')],
  ];
}
