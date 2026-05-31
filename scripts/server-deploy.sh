#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/var/www/roommate}"
BRANCH="${BRANCH:-main}"
BACKEND_SERVICE="${BACKEND_SERVICE:-roommate-backend.service}"
BACKEND_DIR="${APP_DIR}/backend"
FRONTEND_DIR="${APP_DIR}/frontend"
DEPLOY_STATE_DIR="${DEPLOY_STATE_DIR:-/var/tmp/roommate-deploy}"
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

file_hash() {
  sha256sum "$1" | awk '{print $1}'
}

install_backend_dependencies() {
  log "Installing backend dependencies"
  cd "$BACKEND_DIR"
  if [ ! -f requirements.txt ]; then
    log "No backend requirements.txt found; skipping"
    return
  fi

  current_hash="$(file_hash requirements.txt)"
  marker="${DEPLOY_STATE_DIR}/backend-requirements.sha256"
  if [ -f "$marker" ] && [ "$(cat "$marker")" = "$current_hash" ]; then
    log "Backend dependencies unchanged; skipping"
    return
  fi

  if [ -x venv/bin/python ]; then
    venv/bin/python -m pip install -r requirements.txt
  else
    python3 -m pip install -r requirements.txt
  fi
  printf '%s\n' "$current_hash" > "$marker"
}

install_frontend_dependencies() {
  log "Installing frontend dependencies"
  cd "$FRONTEND_DIR"

  manifest="package.json"
  if [ -f package-lock.json ]; then
    manifest="package-lock.json"
  fi

  current_hash="$(file_hash "$manifest")"
  marker="${DEPLOY_STATE_DIR}/frontend-${manifest}.sha256"
  if [ -d node_modules ] && [ -f "$marker" ] && [ "$(cat "$marker")" = "$current_hash" ]; then
    log "Frontend dependencies unchanged; skipping"
    return
  fi

  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi
  printf '%s\n' "$current_hash" > "$marker"
}

log "Entering ${APP_DIR}"
cd "$APP_DIR"
mkdir -p "$DEPLOY_STATE_DIR"

git config --global --add safe.directory "$APP_DIR" >/dev/null 2>&1 || true

if ! git diff --quiet || ! git diff --cached --quiet; then
  git status -sb
  fail "Server repository has local tracked changes. Clean them before deployment."
fi

untracked_files="$(git ls-files --others --exclude-standard)"
if [ -n "$untracked_files" ]; then
  printf '%s\n' "$untracked_files"
  fail "Server repository has untracked files. Clean them before deployment."
fi

log "Pulling origin/${BRANCH}"
git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

install_backend_dependencies
install_frontend_dependencies

log "Building frontend"
cd "$FRONTEND_DIR"
npm run build

log "Restarting backend: ${BACKEND_SERVICE}"
$SUDO systemctl restart "$BACKEND_SERVICE"

reload_nginx

log "Deployment complete"
