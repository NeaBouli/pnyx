#!/usr/bin/env bash
# Connection via PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD (bootstrap superuser).
set +x
set -euo pipefail
for name in EKKLESIA_API_PASSWORD EKKLESIA_MIGRATOR_PASSWORD EKKLESIA_MONITOR_PASSWORD EKKLESIA_DASHBOARD_PASSWORD EKKLESIA_BACKUP_PASSWORD; do
    if [[ -z "${!name:-}" ]]; then
        printf 'Required secret is missing: %s\n' "$name" >&2
        exit 2
    fi
    export "$name"
done
: "${PGDATABASE:?Set PGDATABASE explicitly}"
: "${PGUSER:?Set PGUSER to the bootstrap superuser}"
if [[ "${1:-}" == "--docker" ]]; then
    [[ $# == 2 ]] || { echo 'Usage: db-roles.sh --docker CONTAINER' >&2; exit 2; }
    exec docker exec -i --env PGHOST --env PGPORT --env PGDATABASE --env PGUSER --env PGPASSWORD \
        --env EKKLESIA_API_PASSWORD --env EKKLESIA_MIGRATOR_PASSWORD \
        --env EKKLESIA_MONITOR_PASSWORD --env EKKLESIA_DASHBOARD_PASSWORD --env EKKLESIA_BACKUP_PASSWORD \
        "$2" psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 < "$(dirname "$0")/db-roles.sql"
fi
exec psql --no-psqlrc --quiet --set=ON_ERROR_STOP=1 --file="$(dirname "$0")/db-roles.sql" "$@"
