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
    fail "nginx is listening but no master process was found."
  fi
  $SUDO kill -HUP "$master_pid"
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
  git clean -fdq
fi

log "Pulling origin/${BRANCH}"
git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

log "Installing backend dependencies"
cd "$BACKEND_DIR"
if [ -x venv/bin/python ] && [ -f requirements.txt ]; then
  venv/bin/python -m pip install -r requirements.txt
elif [ -f requirements.txt ]; then
  python3 -m pip install -r requirements.txt
fi

log "Installing frontend dependencies"
cd "$FRONTEND_DIR"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi

log "Building frontend"
npm run build

log "Restarting backend: ${BACKEND_SERVICE}"
$SUDO systemctl restart "$BACKEND_SERVICE"

reload_nginx

log "Deployment complete"
