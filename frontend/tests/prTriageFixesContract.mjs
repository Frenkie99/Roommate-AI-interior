import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');

const playground = readFileSync(resolve(root, 'src/pages/PlaygroundPage.jsx'), 'utf8');
const uploader = readFileSync(resolve(root, 'src/components/ImageUploader.jsx'), 'utf8');

assert.match(playground, /API_TIMEOUT_MS\s*=/);
assert.match(playground, /AbortSignal\.timeout\(API_TIMEOUT_MS\)/);
assert.match(playground, /catch \(error\)/);
assert.match(playground, /finally\s*\{/);

assert.match(uploader, /useRef/);
assert.match(uploader, /URL\.revokeObjectURL/);
assert.match(uploader, /return \(\) =>/);
