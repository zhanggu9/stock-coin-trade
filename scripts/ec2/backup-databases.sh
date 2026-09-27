#!/usr/bin/env bash
set -Eeuo pipefail

# EC2 Docker DB 전체 논리 백업. systemd 서비스에서 root로 실행한다.
BACKUP_ROOT="${DB_BACKUP_ROOT:-/var/backups/stock-coin-trade}"
RETENTION_DAYS="${DB_BACKUP_RETENTION_DAYS:-3}"
MARIADB_CONTAINER="${MARIADB_BACKUP_CONTAINER:-crypto-mock-mariadb}"
POSTGRES_CONTAINER="${POSTGRES_BACKUP_CONTAINER:-crypto-mock-postgres}"
# OHLCV 원본(pg-stock)은 운영 EC2에만 있을 수 있으므로 선택적으로 백업한다.
PGSTOCK_CONTAINER="${PGSTOCK_BACKUP_CONTAINER:-pg-stock}"
LOCK_FILE="${DB_BACKUP_LOCK_FILE:-/run/lock/stock-coin-trade-db-backup.lock}"
STAMP="$(TZ=Asia/Seoul date +%Y%m%dT%H%M%S%z)"
MARIADB_DIR="$BACKUP_ROOT/mariadb"
POSTGRES_DIR="$BACKUP_ROOT/postgresql"
PGSTOCK_DIR="$BACKUP_ROOT/pg-stock"
PARTIAL_FILES=()

log() {
  printf '%s %s\n' "$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')" "$*"
}

cleanup() {
  local file
  for file in "${PARTIAL_FILES[@]:-}"; do
    [[ -n "$file" ]] && rm -f -- "$file"
  done
}
trap cleanup EXIT

[[ "$RETENTION_DAYS" =~ ^[1-9][0-9]*$ ]] || {
  log "ERROR: DB_BACKUP_RETENTION_DAYS must be a positive integer"
  exit 2
}

command -v docker >/dev/null
command -v gzip >/dev/null
command -v sha256sum >/dev/null
command -v flock >/dev/null

install -d -m 0700 "$BACKUP_ROOT" "$MARIADB_DIR" "$POSTGRES_DIR" "$PGSTOCK_DIR" "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  log "SKIP: another database backup is still running"
  exit 0
}

for container in "$MARIADB_CONTAINER" "$POSTGRES_CONTAINER"; do
  [[ "$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null)" == "true" ]] || {
    log "ERROR: container is not running: $container"
    exit 1
  }
done

backup_mariadb() {
  local final="$MARIADB_DIR/mariadb_all_${STAMP}.sql.gz"
  local partial="${final}.partial"
  PARTIAL_FILES+=("$partial")
  log "START: MariaDB all databases -> $final"
  docker exec "$MARIADB_CONTAINER" sh -ec '
    export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"
    exec mariadb-dump -uroot \
      --all-databases --single-transaction --quick \
      --routines --events --triggers --hex-blob
  ' | gzip -9 >"$partial"
  gzip -t "$partial"
  mv "$partial" "$final"
  chmod 0600 "$final"
  (cd "$MARIADB_DIR" && sha256sum "$(basename "$final")" >"$(basename "$final").sha256")
  chmod 0600 "${final}.sha256"
  log "DONE: MariaDB $(du -h "$final" | awk '{print $1}')"
}

backup_postgresql() {
  local final="$POSTGRES_DIR/postgresql_all_${STAMP}.sql.gz"
  local partial="${final}.partial"
  PARTIAL_FILES+=("$partial")
  log "START: PostgreSQL roles and all databases -> $final"
  docker exec "$POSTGRES_CONTAINER" sh -ec '
    exec pg_dumpall --clean --if-exists -U "$POSTGRES_USER"
  ' | gzip -9 >"$partial"
  gzip -t "$partial"
  mv "$partial" "$final"
  chmod 0600 "$final"
  (cd "$POSTGRES_DIR" && sha256sum "$(basename "$final")" >"$(basename "$final").sha256")
  chmod 0600 "${final}.sha256"
  log "DONE: PostgreSQL $(du -h "$final" | awk '{print $1}')"
}

backup_pgstock() {
  [[ "$(docker inspect -f '{{.State.Running}}' "$PGSTOCK_CONTAINER" 2>/dev/null)" == "true" ]] || {
    log "SKIP: pg-stock 컨테이너가 없어 OHLCV 백업을 건너뜁니다 ($PGSTOCK_CONTAINER)"
    return 0
  }
  local final="$PGSTOCK_DIR/pg-stock_all_${STAMP}.sql.gz"
  local partial="${final}.partial"
  PARTIAL_FILES+=("$partial")
  log "START: pg-stock (OHLCV) roles and all databases -> $final"
  docker exec "$PGSTOCK_CONTAINER" sh -ec '
    exec pg_dumpall --clean --if-exists -U "$POSTGRES_USER"
  ' | gzip -9 >"$partial"
  gzip -t "$partial"
  mv "$partial" "$final"
  chmod 0600 "$final"
  (cd "$PGSTOCK_DIR" && sha256sum "$(basename "$final")" >"$(basename "$final").sha256")
  chmod 0600 "${final}.sha256"
  log "DONE: pg-stock $(du -h "$final" | awk '{print $1}')"
}

delete_expired() {
  local retention_minutes=$((RETENTION_DAYS * 24 * 60))
  local deleted
  deleted="$(find "$BACKUP_ROOT" -type f \
    \( -name '*.sql.gz' -o -name '*.sql.gz.sha256' -o -name '*.partial' \) \
    -mmin "+$retention_minutes" -print -delete | wc -l)"
  log "RETENTION: removed $deleted file(s) older than ${RETENTION_DAYS} day(s)"
}

backup_mariadb
backup_postgresql
backup_pgstock
delete_expired
log "SUCCESS: database backup batch completed"
