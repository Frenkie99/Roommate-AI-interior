import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const workflowPath = join(root, '.github', 'workflows', 'deploy.yml');
const deployScriptPath = join(root, 'scripts', 'server-deploy.sh');
const guidePath = join(root, 'docs', 'auto-deploy.md');

// --- File existence ---
assert.equal(existsSync(workflowPath), true, 'deploy workflow must exist');
assert.equal(existsSync(deployScriptPath), true, 'server deploy script must exist');
assert.equal(existsSync(guidePath), true, 'auto deploy guide must exist');

// --- Workflow: triggers ---
const workflow = readFileSync(workflowPath, 'utf8');
assert.match(workflow, /branches:\s*\[\s*main\s*\]/, 'workflow must deploy only main');
assert.match(workflow, /workflow_dispatch:/, 'workflow must allow manual runs');

// --- Workflow: SSH setup ---
assert.match(workflow, /ALIYUN_SSH_KEY/, 'workflow must use SSH key secret');
assert.match(workflow, /ssh-keyscan/, 'workflow must add server host key');

// --- Workflow: frontend build on CI runner ---
assert.match(workflow, /npm ci/, 'workflow must install exact frontend deps on CI');
assert.match(workflow, /npm run build/, 'workflow must build frontend on CI runner');

// --- Workflow: upload before server deploy ---
const uploadIdx = workflow.indexOf('Upload frontend dist');
const deployIdx = workflow.indexOf('Run server deployment');
assert.ok(uploadIdx > 0, 'workflow must have frontend upload step');
assert.ok(deployIdx > 0, 'workflow must have server deploy step');
assert.ok(uploadIdx < deployIdx, 'frontend must be uploaded BEFORE server deployment runs');

// --- Workflow: verification ---
assert.match(workflow, /Verify deployment/, 'workflow must verify deployment after deploy');
assert.match(workflow, /127\.0\.0\.1:8000\/health/, 'workflow must check backend health endpoint');
assert.match(workflow, /roommate-ai\.cn/, 'workflow must check production homepage');

// --- Deploy script: fail fast ---
const deployScript = readFileSync(deployScriptPath, 'utf8');
assert.match(deployScript, /set -Eeuo pipefail/, 'deploy script must fail fast');

// --- Deploy script: configurable paths ---
assert.match(deployScript, /APP_DIR="\$\{APP_DIR:-\/var\/www\/roommate\}"/, 'deploy script must default app dir');
assert.match(deployScript, /BACKEND_SERVICE="\$\{BACKEND_SERVICE:-roommate-backend\.service\}"/, 'deploy script must default backend service');

// --- Deploy script: git operations ---
assert.match(deployScript, /git pull --ff-only origin "\$BRANCH"/, 'deploy script must fast-forward pull');

// --- Deploy script: backend deps (accept --prefer-binary or bare -r) ---
assert.match(deployScript, /pip install.*-r requirements\.txt/, 'deploy script must install backend requirements');

// --- Deploy script: frontend from CI (not built on server) ---
assert.match(deployScript, /frontend.*uploaded by CI|FRONTEND_TARBALL|Skipping frontend build/, 'deploy script must not build frontend on server');

// --- Deploy script: backend restart ---
assert.match(deployScript, /systemctl restart "\$BACKEND_SERVICE"/, 'deploy script must restart backend');

// --- Deploy script: health check ---
assert.match(deployScript, /wait_for_backend/, 'deploy script must have backend health check');
assert.match(deployScript, /HEALTH_RETRIES/, 'deploy script must retry health checks');

// --- Deploy script: rollback ---
assert.match(deployScript, /rollback\(\)/, 'deploy script must have rollback function');
assert.match(deployScript, /PREV_COMMIT/, 'deploy script must record pre-deployment commit');

// --- Deploy script: runtime data protection ---
assert.match(deployScript, /backup_protected/, 'deploy script must backup runtime data');
assert.match(deployScript, /verify_protected/, 'deploy script must verify runtime data after pull');

// --- Deploy script: nginx ---
assert.match(deployScript, /reload_nginx\(\)/, 'deploy script must isolate nginx reload');

// --- Guide: verification steps ---
const guide = readFileSync(guidePath, 'utf8');
assert.match(guide, /health/, 'guide must mention health check endpoint');
assert.match(guide, /deployed-commit/, 'guide must mention deployed commit file');

console.log('All auto-deploy config checks passed.');
