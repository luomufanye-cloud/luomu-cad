// Luomu CAD Node compatibility API. Copyright (c) 2026 luomufanye-cloud.
import { spawnSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const localPython = resolve(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const python = process.env.LUOMU_CAD_COMPONENT_PYTHON || (existsSync(localPython) ? localPython : 'python');
function call(action, input) {
  const r = spawnSync(python, [resolve(root, 'scripts/component_bridge.py'), action], {
    input: input === undefined ? '' : JSON.stringify(input), encoding: 'utf8',
    windowsHide: true, maxBuffer: 64*1024*1024, timeout: 60000,
  });
  if (r.error) throw r.error;
  if (r.status) throw new Error(r.stderr || 'Component process failed');
  return JSON.parse(r.stdout);
}
export const catalog = () => call('catalog');
export const assemble = plan => call('build', plan);
export const furnitureGeometry = item => call('furniture', item);
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const action = process.argv[2];
  if (action === 'catalog') console.log(JSON.stringify(catalog()));
  else if (action === 'build') console.log(JSON.stringify(assemble(JSON.parse(readFileSync(process.argv[3],'utf8')))));
  else if (action === 'probe') console.log(JSON.stringify(call('probe')));
  else throw new Error('Use catalog/build/probe');
}
