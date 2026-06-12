#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/var/www/roommate}"
BRANCH="${BRANCH:-main}"
BACKEND_SERVICE="${BACKEND_SERVICE:-roommate-backend.service}"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend"
SUDO="${SUDO:-sudo -n}"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  printf '\n[deploy failed] %s\n' "$*" >&2
  exit 1
}

reload_nginx() {
  log "Reloading nginx"
  if $SUDO systemctl is-active --quiet nginx; then
    $SUDO systemctl reload nginx
    return
  fi

  $SUDO /usr/sbin/nginx -t
  if [ -s /run/nginx.pid ]; then
    $SUDO /usr/sbin/nginx -s reload
    return
  fi

  master_pid="$(pgrep -o -f 'nginx: master process')"
  if [ -z "$master_pid" ]; then
    fail "nginx is listening but no master master process was found."
  fi
  $SUDO kill -HUP "$master_pid"
}

# Ensure swap exists (1GB RAM servers need it for pip install torch)
ensure_swap() {
  if [ "$(wc -l < /proc/swaps 2>/dev/null || echo 0)" -gt 1 ]; then
    log "Swap already active"
    return
  fi
  log "Creating 2GB swap file (prevent OOM during pip install)"
  $SUDO fallocate -l 2G /swapfile 2>/dev/null || $SUDO dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
  $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile
  $SUDO swapon /swapfile
  log "Swap activated"
}

log "Entering ${APP_DIR}"
cd "$APP_DIR"

git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true

# Auto-clean local changes (build artifacts, renamed assets) instead of failing
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "Discarding local tracked changes"
  git checkout -- .
fi

untracked_files="$(git ls-files --others --exclude-standard)"
if [ -n "$untracked_files" ]; then
  log "Removing untracked files"
  git clean -fdq || true
fi

log "Pulling origin/${BRANCH}"
$SUDO chown -R "$(whoami)" .git 2>/dev/null || true
git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

# Ensure swap before heavy pip install
ensure_swap

log "Installing backend dependencies"
cd "$BACKEND_DIR"
if [ -x venv/bin/python ] && [ -f requirements.txt ]; then
  venv/bin/python -m pip install --prefer-binary -r requirements.txt 2>&1 | tail -5
elif [ -f requirements.txt ]; then
  python3 -m pip install --prefer-binary -r requirements.txt 2>&1 | tail -5
fi

# Frontend build: by default CI (GitHub Actions) builds and uploads dist,
# so the server no longer runs npm build (avoids OOM on the ~1GB box).
# Build locally only as a fallback when SKIP_FRONTEND_BUILD != 1 (manual run).
if [ "${SKIP_FRONTEND_BUILD:-0}" = "1" ]; then
  log "Skipping frontend build on server (dist uploaded by CI)"
else
  log "Installing frontend dependencies"
  cd "$FRONTEND_DIR"
  if [ -f package-lock.json ]; then
    npm ci --prefer-offline 2>&1 | tail -5
  else
    npm install --prefer-offline 2>&1 | tail -5
  fi

  log "Building frontend (local fallback)"
  npm run build 2>&1 | tail -5
fi

log "Restarting backend: ${BACKEND_SERVICE}"
$SUDO systemctl restart "$BACKEND_SERVICE"

reload_nginx

log "Deployment complete"
