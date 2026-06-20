#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-audit}"
CONFIRM="${EKKLESIA_DISK_CLEANUP_CONFIRM:-}"

usage() {
  cat <<'EOF'
Usage:
  scripts/server-disk-maintenance.sh audit
  EKKLESIA_DISK_CLEANUP_CONFIRM=EKKLESIA-SAFE-CLEANUP scripts/server-disk-maintenance.sh safe-clean

Modes:
  audit       Read-only disk report. Default.
  safe-clean  Conservative cleanup only:
              - dangling Docker images
              - stopped Docker containers older than 24h
              - Docker builder cache older than 7d
              - apt package cache
              - journald capped to 500M

Never prunes Docker volumes. Never removes Ollama models. Never removes backups.
EOF
}

section() {
  printf '\n== %s ==\n' "$1"
}

require_safe_confirm() {
  if [[ "$CONFIRM" != "EKKLESIA-SAFE-CLEANUP" ]]; then
    echo "ERROR: safe-clean requires EKKLESIA_DISK_CLEANUP_CONFIRM=EKKLESIA-SAFE-CLEANUP" >&2
    exit 2
  fi
}

audit() {
  section "filesystem"
  df -hT / /opt /var 2>/dev/null || df -hT
  df -ih / /opt /var 2>/dev/null || df -ih

  section "docker system df"
  docker system df || true

  section "docker volume usage"
  docker system df -v | sed -n '/Local Volumes space usage:/,/Build cache usage:/p' | sed -n '1,120p' || true

  section "top /opt/ekklesia"
  du -xh --max-depth=2 /opt/ekklesia 2>/dev/null | sort -h | tail -40 || true

  section "top /var/lib"
  du -xh --max-depth=1 /var/lib 2>/dev/null | sort -h | tail -40 || true

  section "ollama models"
  docker exec ekklesia-ollama ollama list 2>/dev/null || true

  section "project artifacts"
  for d in \
    /opt/ekklesia/build-artifacts \
    /opt/ekklesia/release-builds \
    /opt/ekklesia/downloads \
    /opt/ekklesia/backups \
    /opt/ekklesia/app/docs/download/backups
  do
    [[ -e "$d" ]] && du -sh "$d"
  done

  section "safe cache candidates"
  journalctl --disk-usage 2>/dev/null || true
  du -sh /var/cache/apt /var/lib/snapd/cache 2>/dev/null || true

  section "dangling docker volumes (manual review only)"
  docker volume ls -qf dangling=true | while read -r volume_name; do
    [[ -z "$volume_name" ]] && continue
    size="$(du -sh "/var/lib/docker/volumes/$volume_name" 2>/dev/null | cut -f1 || true)"
    printf '%s %s\n' "$volume_name" "${size:-unknown}"
  done
}

safe_clean() {
  require_safe_confirm

  section "before"
  df -h /
  docker system df || true

  section "safe docker prune"
  docker container prune -f --filter "until=24h"
  docker image prune -f
  docker builder prune -af --filter "until=168h"

  section "host cache cleanup"
  apt-get clean
  journalctl --vacuum-size=500M

  section "after"
  df -h /
  docker system df || true
}

case "$MODE" in
  audit)
    audit
    ;;
  safe-clean)
    safe_clean
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

