import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const workflowPath = join(root, '.github', 'workflows', 'deploy.yml');
const deployScriptPath = join(root, 'scripts', 'server-deploy.sh');
const guidePath = join(root, 'docs', 'auto-deploy.md');

assert.equal(existsSync(workflowPath), true, 'deploy workflow should exist');
assert.equal(existsSync(deployScriptPath), true, 'server deploy script should exist');
assert.equal(existsSync(guidePath), true, 'auto deploy guide should exist');

const workflow = readFileSync(workflowPath, 'utf8');
assert.match(workflow, /branches:\s*\[\s*main\s*\]/, 'workflow should deploy only main');
assert.match(workflow, /workflow_dispatch:/, 'workflow should allow manual runs');
assert.match(workflow, /ALIYUN_SSH_KEY/, 'workflow should use the SSH key secret');
assert.match(workflow, /ssh-keyscan/, 'workflow should add the server host key');
assert.match(workflow, /scripts\/server-deploy\.sh/, 'workflow should run the server deploy script');

const deployScript = readFileSync(deployScriptPath, 'utf8');
assert.match(deployScript, /set -Eeuo pipefail/, 'deploy script should fail fast');
assert.match(deployScript, /APP_DIR="\$\{APP_DIR:-\/var\/www\/roommate\}"/, 'deploy script should default to the server app directory');
assert.match(deployScript, /BACKEND_SERVICE="\$\{BACKEND_SERVICE:-roommate-backend\.service\}"/, 'deploy script should default to the backend service');
assert.match(deployScript, /git pull --ff-only origin "\$BRANCH"/, 'deploy script should fast-forward pull main');
assert.match(deployScript, /npm ci/, 'deploy script should install exact frontend dependencies');
assert.match(deployScript, /npm run build/, 'deploy script should build the frontend');
assert.match(deployScript, /systemctl restart "\$BACKEND_SERVICE"/, 'deploy script should restart the backend service');
assert.match(deployScript, /systemctl reload nginx/, 'deploy script should reload nginx');
