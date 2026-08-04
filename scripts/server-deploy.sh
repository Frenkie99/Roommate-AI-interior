#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/var/www/roommate}"
BRANCH="${BRANCH:-main}"
BACKEND_SERVICE="${BACKEND_SERVICE:-roommate-backend.service}"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend"
SUDO="${SUDO-sudo -n}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-10}"
HEALTH_DELAY="${HEALTH_DELAY:-2}"

# --- helpers ---

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  printf '\n[DEPLOY FAILED] %s\n' "$*" >&2
  exit 1
}

reload_nginx() {
  log "Reloading nginx"
  if $SUDO systemctl is-active --quiet nginx 2>/dev/null; then
    $SUDO systemctl reload nginx
    return
  fi
  if [ -x /usr/sbin/nginx ]; then
    $SUDO /usr/sbin/nginx -t
    if [ -s /run/nginx.pid ]; then
      $SUDO /usr/sbin/nginx -s reload
      return
    fi
    master_pid="$(pgrep -o -f 'nginx: master process' || true)"
    if [ -n "$master_pid" ]; then
      $SUDO kill -HUP "$master_pid"
      return
    fi
  fi
  log "nginx reload skipped (not running or not found)"
}

# --- health check ---

wait_for_backend() {
  local attempt=1
  while [ "$attempt" -le "$HEALTH_RETRIES" ]; do
    log "Health check attempt ${attempt}/${HEALTH_RETRIES}"
    if curl -sf --connect-timeout 5 "$HEALTH_URL" >/dev/null 2>&1; then
      log "Backend healthy"
      return 0
    fi
    sleep "$HEALTH_DELAY"
    attempt=$((attempt + 1))
  done
  return 1
}

# --- rollback ---

rollback() {
  local prev_commit="$1"
  local reason="$2"
  log "ROLLBACK: reverting to ${prev_commit} — ${reason}"

  cd "$APP_DIR"

  # Try fetching origin (non-fatal if unreachable)
  git fetch origin "$BRANCH" 2>/dev/null || log "Could not fetch origin (continuing rollback)"

  # Soft-reset to previous commit — keeps working tree intact
  # Then checkout only tracked files from that commit
  if git reset --soft "$prev_commit" 2>/dev/null; then
    log "Soft reset to ${prev_commit}"
  else
    log "WARNING: git reset failed, attempting checkout"
    git checkout "$prev_commit" -- . 2>/dev/null || true
  fi

  # Restore protected paths from backup
  for dir in input output; do
    if [ -d "/tmp/deploy-backup/${dir}" ]; then
      log "Restoring ${dir}/ from backup"
      cp -rn /tmp/deploy-backup/"${dir}"/. "${APP_DIR}/${dir}/" 2>/dev/null || true
    fi
  done
  if [ -f /tmp/deploy-backup/.env ]; then
    cp -n /tmp/deploy-backup/.env "${BACKEND_DIR}/.env" 2>/dev/null || true
  fi

  # Clean up failed dist.new
  rm -rf "${FRONTEND_DIR}/dist.new" 2>/dev/null || true

  log "Restarting backend with rollback version"
  $SUDO systemctl restart "$BACKEND_SERVICE" 2>/dev/null || true

  if wait_for_backend; then
    reload_nginx
    log "Rollback complete — backend serving ${prev_commit}"
    return 0
  else
    log "CRITICAL: backend still unhealthy after rollback"
    return 1
  fi
}

# --- protect runtime data ---

PROTECTED_DIRS="input output"
PROTECTED_FILES="${BACKEND_DIR}/.env"

backup_protected() {
  rm -rf /tmp/deploy-backup
  mkdir -p /tmp/deploy-backup
  for d in $PROTECTED_DIRS; do
    if [ -d "${APP_DIR}/${d}" ]; then
      cp -r "${APP_DIR}/${d}" /tmp/deploy-backup/ 2>/dev/null || true
      log "Backed up ${d}/"
    fi
  done
  if [ -f "$PROTECTED_FILES" ]; then
    cp "$PROTECTED_FILES" /tmp/deploy-backup/.env
    log "Backed up .env"
  fi
}

verify_protected() {
  local ok=true
  for d in $PROTECTED_DIRS; do
    if [ ! -d "${APP_DIR}/${d}" ]; then
      log "MISSING: ${APP_DIR}/${d}/ — restoring from backup"
      mkdir -p "${APP_DIR}/${d}"
      if [ -d "/tmp/deploy-backup/${d}" ]; then
        cp -rn /tmp/deploy-backup/"${d}"/. "${APP_DIR}/${d}/" 2>/dev/null || true
      fi
      ok=false
    fi
  done
  if [ ! -f "$PROTECTED_FILES" ]; then
    log "MISSING: ${PROTECTED_FILES}"
    if [ -f /tmp/deploy-backup/.env ]; then
      cp /tmp/deploy-backup/.env "$PROTECTED_FILES"
      log "Restored .env from backup"
    fi
    ok=false
  fi
  if [ "$ok" = false ]; then
    fail "Protected paths were deleted during deployment. Restored from backup but deployment aborted."
  fi
}

# ============================================================
# MAIN
# ============================================================

log "Entering ${APP_DIR}"
cd "$APP_DIR"

git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true

# Record pre-deployment state
PREV_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
log "Pre-deployment commit: ${PREV_COMMIT}"

# Protect runtime data before any git operations
backup_protected

# Clean only build artifacts, not runtime data
# Use pathspec to limit checkout/clean scope
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "Discarding local tracked changes (excluding input/output/.env)"
  git checkout -- . ':!input' ':!output' ':!backend/.env'
fi

untracked_files="$(git ls-files --others --exclude-standard)"
if [ -n "$untracked_files" ]; then
  # Filter: only clean files NOT in protected dirs
  to_clean="$(echo "$untracked_files" | grep -v '^input/' | grep -v '^output/' | grep -v '^frontend/dist' | grep -v '^backend/\.env$' || true)"
  if [ -n "$to_clean" ]; then
    log "Removing untracked build artifacts"
    echo "$to_clean" | xargs rm -rf 2>/dev/null || true
  fi
fi

log "Pulling origin/${BRANCH}"
$SUDO chown -R "$(whoami)" .git 2>/dev/null || true
if ! git fetch origin "$BRANCH" 2>/dev/null; then
  fail "git fetch origin/${BRANCH} failed — network or remote unavailable"
fi
if ! git pull --ff-only origin "$BRANCH" 2>/dev/null; then
  fail "git pull --ff-only failed — check for merge conflicts or server state"
fi

NEW_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
log "Deploying commit: ${NEW_COMMIT}"

# Verify protected paths survived git pull
verify_protected

# Install backend dependencies
log "Installing backend dependencies"
cd "$BACKEND_DIR"
if [ -x venv/bin/python ] && [ -f requirements.txt ]; then
  venv/bin/python -m pip install --prefer-binary -r requirements.txt 2>&1 | tail -5
elif [ -f requirements.txt ]; then
  python3 -m pip install --prefer-binary -r requirements.txt 2>&1 | tail -5
fi

# Frontend: CI uploads dist tarball to /tmp/frontend-dist.tar.gz
FRONTEND_TARBALL="${FRONTEND_TARBALL:-/tmp/frontend-dist.tar.gz}"

if [ -f "$FRONTEND_TARBALL" ]; then
  log "Extracting frontend dist from CI upload"
  rm -rf "${FRONTEND_DIR}/dist.new" "${FRONTEND_DIR}/dist.old"
  mkdir -p "${FRONTEND_DIR}/dist.new"
  tar -C "${FRONTEND_DIR}/dist.new" -xzf "$FRONTEND_TARBALL"
  rm -f "$FRONTEND_TARBALL"
  log "Frontend extracted to dist.new"
else
  log "No frontend tarball found at ${FRONTEND_TARBALL} — keeping existing dist"
fi

# Restart backend
log "Restarting backend: ${BACKEND_SERVICE}"
$SUDO systemctl restart "$BACKEND_SERVICE"

# Health check
if ! wait_for_backend; then
  log "Backend health check FAILED after ${HEALTH_RETRIES} retries"
  # Clean up dist.new if it exists
  rm -rf "${FRONTEND_DIR}/dist.new" 2>/dev/null || true
  rollback "$PREV_COMMIT" "backend health check failed"
  fail "Deployment aborted — backend unhealthy after restart. Rolled back to ${PREV_COMMIT}."
fi

# Atomic frontend switch (only if dist.new exists)
if [ -d "${FRONTEND_DIR}/dist.new" ]; then
  log "Atomically switching frontend dist"
  if [ -d "${FRONTEND_DIR}/dist" ]; then
    mv "${FRONTEND_DIR}/dist" "${FRONTEND_DIR}/dist.old"
  fi
  mv "${FRONTEND_DIR}/dist.new" "${FRONTEND_DIR}/dist"
  rm -rf "${FRONTEND_DIR}/dist.old"
  log "Frontend dist switched"
fi

reload_nginx

# Record successful deployment
printf '%s\n' "$NEW_COMMIT" > "${APP_DIR}/.deployed-commit" 2>/dev/null || true
log "Deployment complete — ${PREV_COMMIT} → ${NEW_COMMIT}"

# Cleanup backup
rm -rf /tmp/deploy-backup
