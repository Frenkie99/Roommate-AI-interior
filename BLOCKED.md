# Blocked Items

## BLOCKED-01: GitHub Actions workflow disabled
- **Status**: Blocker for real deployment drill (Task 2)
- **Detail**: Workflow was manually disabled after repeated failures. Must be re-enabled after fixes pass local verification.
- **Resolution**: User must click "Enable workflow" in GitHub Actions UI after approving push.
- **Impact**: Cannot run real deployment until resolved.

## BLOCKED-02: Server SSL cert for dmxapi.cn expired
- **Status**: Not blocking (unrelated platform, noted for awareness)
- **Detail**: `api.dmxapi.cn` SSL cert expired; works on `www.dmxapi.cn`.
- **Impact**: None on deploy fix.

## BLOCKED-03: No GitHub Secrets audit
- **Status**: Pre-check needed before real deployment
- **Detail**: Must confirm ALIYUN_HOST, ALIYUN_SSH_KEY, ALIYUN_USER secrets are present and valid in GitHub repo before enabling workflow.
- **Resolution**: User confirms or adds missing secrets. Cannot verify from local.
- **Impact**: Deployment will fail at SSH step if secrets missing.
