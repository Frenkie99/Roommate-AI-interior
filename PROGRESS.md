# Auto-Deploy Fix Progress

## Goal
Push main → GitHub Actions deploys reliably. User never opens Aliyun console.

## Status: READY FOR APPROVAL

## Task 0 — Initial Check (2026-08-04)
- `git status --short`: clean ✅
- `node scripts/test-auto-deploy-config.mjs`: FAIL → FIXED ✅
- `cd frontend && npm run build`: 1537 modules, 974ms ✅
- `bash -n scripts/server-deploy.sh`: OK ✅

## Task 1 — Fixes Applied
1. **server-deploy.sh** rewritten:
   - Protects input/, output/, backend/.env from git clean
   - Records PREV_COMMIT before deployment
   - Frontend built by CI, uploaded as tarball, atomically switched
   - Health check: polls 127.0.0.1:8000/health (10 retries, 2s apart)
   - Rollback on failure: git reset --soft + restore backups + restart
   - No longer builds frontend on the 1GB server
2. **deploy.yml** fixed:
   - Order: checkout → build CI → upload frontend → server deploy → verify
   - Frontend uploads BEFORE backend restart (no half-new/half-old window)
   - Verification step: checks backend health + homepage 200 + deployed commit
3. **test-auto-deploy-config.mjs** updated:
   - Accepts --prefer-binary flag
   - Verifies upload-before-deploy ordering
   - Checks for health check, rollback, data protection features
4. **docs/auto-deploy.md** rewritten:
   - Normal flow: push main → check one result
   - Documented rollback, verification, health endpoint

## Task 2 — Local Verification
| Check | Result |
|-------|--------|
| `test-auto-deploy-config.mjs` | ✅ All checks passed |
| `bash -n scripts/server-deploy.sh` | ✅ Syntax OK |
| `npm run build` | ✅ 1537 modules, 974ms |
| `git diff --check` | ✅ OK |
| Failure drill (`deploy-test-rollback.sh`) | ✅ 7/7 passed |

Failure drill verified: health check fails → rollback triggered → git reset to old commit → input/output/.env preserved → old dist intact → dist.new cleaned up.

## Awaiting User Approval
- Push commit with all fixes
- Re-enable GitHub Actions workflow
- Trigger first real deployment
