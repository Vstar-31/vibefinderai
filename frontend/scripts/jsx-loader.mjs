import { readFile } from 'node:fs/promises';
import { transformWithEsbuild } from 'vite';

export async function load(url, context, nextLoad) {
  if (!url.endsWith('.jsx')) return nextLoad(url, context);
  const source = await readFile(new URL(url), 'utf8');
  const { code } = await transformWithEsbuild(source, url, { loader: 'jsx', jsx: 'automatic' });
  return { format: 'module', source: code, shortCircuit: true };
}
