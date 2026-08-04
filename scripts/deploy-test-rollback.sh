#!/usr/bin/env bash
# Failure drill: simulate deployment where health check fails,
# verify rollback keeps old version and protected dirs survive.
set -Eeuo pipefail

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

# --- Setup: simulate server directory ---
echo "=== Setting up test environment ==="
mkdir -p "$TEST_DIR/var/www/roommate"/{input,output,backend}
echo 'APIYI_KEY=test123' > "$TEST_DIR/var/www/roommate/backend/.env"
echo 'user photo' > "$TEST_DIR/var/www/roommate/input/test.jpg"
echo 'result png' > "$TEST_DIR/var/www/roommate/output/result.png"

# Init git with a bare "origin" so fetch/pull work
FAKE_ORIGIN="$TEST_DIR/origin.git"
git init --bare -q "$FAKE_ORIGIN"

# Create v1 and push to origin
WORK_DIR="$TEST_DIR/work"
git init -q "$WORK_DIR"
cd "$WORK_DIR"
git config user.email "test@test"
git config user.name "test"
echo 'v1' > version.txt
git add version.txt
git commit -qm "v1"
git remote add origin "$FAKE_ORIGIN"
git push -q origin main 2>/dev/null

ORIG_COMMIT="$(git rev-parse --short HEAD)"
echo "Original commit (v1): $ORIG_COMMIT"

# Create v2 on origin only (simulate upstream change)
TMP_CLONE="$TEST_DIR/tmpclone"
git clone -q "$FAKE_ORIGIN" "$TMP_CLONE" 2>/dev/null
cd "$TMP_CLONE"
git config user.email "test@test"
git config user.name "test"
echo 'v2' > version.txt
git add version.txt
git commit -qm "v2"
git push -q origin main 2>/dev/null
NEW_REMOTE_COMMIT="$(git rev-parse --short HEAD)"
echo "New remote commit (v2): $NEW_REMOTE_COMMIT"
rm -rf "$TMP_CLONE"

# Now set up the "server" repo at v1 (simulating the server before deploy)
cd "$TEST_DIR/var/www/roommate"
rm -rf .git
cp -r "$WORK_DIR/.git" .
git reset --hard HEAD 2>/dev/null
git remote set-url origin "$FAKE_ORIGIN" 2>/dev/null || git remote add origin "$FAKE_ORIGIN"
git branch --set-upstream-to=origin/main main 2>/dev/null || true
rm -rf "$WORK_DIR"

# Create .gitignore (production has this; needed so git doesn't track dist/)
cat > .gitignore << 'GITIGNORE'
dist/
node_modules/
GITIGNORE
CURRENT_COMMIT="$(git rev-parse --short HEAD)"
echo "Server is at: $CURRENT_COMMIT (origin has $NEW_REMOTE_COMMIT)"

# Create frontend/dist with old content (simulates deployed state)
mkdir -p frontend/dist
echo 'old index' > frontend/dist/index.html

# --- Run deployment script with forced health check failure ---
echo ""
echo "=== Running deploy script (health check will fail) ==="

# Copy deploy script and override wait_for_backend to always fail
cp /Users/frenkie99/project/Roommate-AI-interior-main/scripts/server-deploy.sh "$TEST_DIR/deploy.sh"
chmod +x "$TEST_DIR/deploy.sh"

# Create a fake frontend tarball for CI upload simulation
mkdir -p "$TEST_DIR/fake-dist"
echo 'new index' > "$TEST_DIR/fake-dist/index.html"
tar -C "$TEST_DIR/fake-dist" -czf /tmp/frontend-dist.tar.gz .

# Mock systemctl for local testing
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/systemctl" << 'MOCK'
#!/bin/bash
case "$1" in
  restart|reload|is-active) echo "[mock systemctl $*]"; exit 0 ;;
  *) echo "[mock systemctl $*]"; exit 0 ;;
esac
MOCK
chmod +x "$TEST_DIR/bin/systemctl"
export PATH="$TEST_DIR/bin:$PATH"

# Mock pgrep for nginx master check
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/pgrep" << 'MOCK'
#!/bin/bash
exit 1  # No nginx master found
MOCK
chmod +x "$TEST_DIR/bin/pgrep"

# Mock curl for health check (always fail on the nonexistent health URL)
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/curl" << 'MOCK'
#!/bin/bash
for arg in "$@"; do
  case "$arg" in
    *9999*|*nonexistent*)
      exit 1  # Simulate health check failure
      ;;
  esac
done
# For any other URL, fake success
echo '{"status":"ok"}'
exit 0
MOCK
chmod +x "$TEST_DIR/bin/curl"
export PATH="$TEST_DIR/bin:$PATH"

# Mock nginx reload commands
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/nginx" << 'MOCK'
#!/bin/bash
exit 0
MOCK
chmod +x "$TEST_DIR/bin/nginx"
export PATH="$TEST_DIR/bin:$PATH"

# Run deploy with forced failure
set +e
APP_DIR="$TEST_DIR/var/www/roommate" \
BRANCH=main \
BACKEND_SERVICE=roommate-backend.service \
SUDO="" \
HEALTH_URL="http://127.0.0.1:9999/nonexistent" \
HEALTH_RETRIES=3 \
HEALTH_DELAY=1 \
FRONTEND_TARBALL=/tmp/frontend-dist.tar.gz \
bash "$TEST_DIR/deploy.sh" 2>&1 | tail -40
DEPLOY_EXIT=${PIPESTATUS[0]}
set -e

echo "Deploy exit code: $DEPLOY_EXIT"

# --- Verify ---
echo ""
echo "=== Verification ==="

# 1. Deployment should have failed
if [ "$DEPLOY_EXIT" -ne 0 ]; then
  pass "deploy script exited non-zero on health failure"
else
  fail "deploy script should have failed"
fi

# 2. Protected dirs still exist with data
if [ -f "$TEST_DIR/var/www/roommate/input/test.jpg" ]; then
  pass "input/ data preserved"
else
  fail "input/ data lost"
fi

if [ -f "$TEST_DIR/var/www/roommate/output/result.png" ]; then
  pass "output/ data preserved"
else
  fail "output/ data lost"
fi

if [ -f "$TEST_DIR/var/www/roommate/backend/.env" ]; then
  env_content="$(cat "$TEST_DIR/var/www/roommate/backend/.env")"
  if echo "$env_content" | grep -q 'APIYI_KEY=test123'; then
    pass ".env preserved with correct content"
  else
    fail ".env content changed: $env_content"
  fi
else
  fail ".env file lost"
fi

# 3. Git rolled back to original commit
CURRENT_COMMIT="$(cd "$TEST_DIR/var/www/roommate" && git rev-parse --short HEAD)"
if [ "$CURRENT_COMMIT" = "$ORIG_COMMIT" ]; then
  pass "git rolled back to $ORIG_COMMIT"
else
  echo "  Expected: $ORIG_COMMIT, Got: $CURRENT_COMMIT"
  fail "git not rolled back"
fi

# 4. dist.new should be cleaned up (or dist preserved)
if [ -f "$TEST_DIR/var/www/roommate/frontend/dist/index.html" ]; then
  dist_content="$(cat "$TEST_DIR/var/www/roommate/frontend/dist/index.html")"
  if echo "$dist_content" | grep -q 'old index'; then
    pass "old frontend dist preserved (not replaced by failed deploy)"
  else
    fail "frontend dist was replaced despite failed deploy"
  fi
else
  fail "frontend dist directory missing"
fi

# 5. dist.new should NOT exist (cleaned up on failure)
if [ ! -d "$TEST_DIR/var/www/roommate/frontend/dist.new" ]; then
  pass "dist.new cleaned up after failed deploy"
else
  fail "dist.new not cleaned up"
fi

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
rm -f /tmp/frontend-dist.tar.gz

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
