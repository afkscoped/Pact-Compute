import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { build } from 'esbuild-wasm';

await mkdir('dist/assets', { recursive: true });
const result = await build({
  entryPoints: { console: 'src/main.tsx' },
  bundle: true,
  outdir: 'dist/assets',
  entryNames: '[name]-[hash]',
  metafile: true,
  minify: true,
  jsx: 'automatic',
  platform: 'browser',
  format: 'esm',
  target: 'es2022',
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
});
const entry = Object.entries(result.metafile.outputs).find(([, details]) => details.entryPoint === 'src/main.tsx');
if (!entry?.[1].cssBundle) throw new Error('Expected a React entry point and its stylesheet.');
const template = await readFile('index.html', 'utf8');
const html = template.replace('/src/main.tsx', '/' + entry[0].replace(/^dist\//, ''))
  .replace('</head>', '<link rel="stylesheet" href="/' + entry[1].cssBundle.replace(/^dist\//, '') + '">\n  </head>');
await writeFile('dist/index.html', html, 'utf8');
