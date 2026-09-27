#!/usr/bin/env bash
set -Eeuo pipefail

# Fresh-PC bootstrap and logical data transfer for this repository's databases.
# This script never removes Docker volumes. Use export/restore instead of copying
# /var/lib/docker volume files between machines.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_NAME="stock-coin-trade"
NETWORK_NAME="postgresql_default"
MARIADB_CONTAINER="crypto-mock-mariadb"
QUANT_CONTAINER="crypto-mock-postgres"
REDIS_CONTAINER="crypto-mock-redis"
PGSTOCK_CONTAINER="pg-stock"
WITH_APP=false
SEED_OHLCV=false
CONFIRM_RESTORE=false

COMPOSE=(docker compose -p "$PROJECT_NAME" --profile local-db
  -f "$REPO_ROOT/docker-compose.yml"
  -f "$REPO_ROOT/docker-compose.pg-stock.yml")

log() {
  printf '[db-setup] %s\n' "$*"
}

die() {
  printf '[db-setup] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  scripts/setup-docker-databases.sh install
  scripts/setup-docker-databases.sh init [--with-app] [--seed-ohlcv]
  scripts/setup-docker-databases.sh verify
  scripts/setup-docker-databases.sh export BACKUP_PARENT_DIR
  scripts/setup-docker-databases.sh restore BACKUP_DIR --confirm-restore [--with-app]

Commands:
  install  Ubuntu/Debian에 Docker Engine과 Compose plugin을 설치합니다.
  init     .env, 외부 Docker 네트워크와 MariaDB/PostgreSQL/Redis를 준비합니다.
  verify   네 DB의 health와 핵심 테이블을 읽기 전용으로 확인합니다.
  export   다른 PC로 옮길 MariaDB/Quant/pg-stock 논리 덤프를 새 폴더에 만듭니다.
  restore  export 결과를 현재 DB에 복원합니다. 기존 테이블 데이터가 교체될 수
           있으므로 --confirm-restore가 반드시 필요합니다.

Options:
  --with-app    frontend와 python-backend까지 빌드·기동합니다.
  --seed-ohlcv  앱 기동 후 주요 종목 OHLCV를 공급자에서 최초 수집합니다.

This script never runs `docker compose down -v` and never deletes named volumes.
USAGE
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker and Compose plugin are already installed."
    docker --version
    docker compose version
    return
  fi

  [[ -r /etc/os-release ]] || die "/etc/os-release not found"
  # shellcheck disable=SC1091
  source /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *) die "install supports Ubuntu/Debian only; install Docker Desktop/Engine manually on ${ID:-unknown}" ;;
  esac

  require_command sudo
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  printf 'Types: deb\nURIs: https://download.docker.com/linux/%s\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' \
    "$ID" "${VERSION_CODENAME:?VERSION_CODENAME missing}" "$(dpkg --print-architecture)" \
    | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable --now docker
  sudo usermod -aG docker "${SUDO_USER:-$(id -un)}"
  log "Docker installed. Log out/in once so the docker group applies, then run the init command."
}

require_docker() {
  require_command docker
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 plugin is not installed"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable or this user lacks permission"
}

init_env() {
  if [[ ! -f "$REPO_ROOT/.env" ]]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    chmod 0600 "$REPO_ROOT/.env"
    log "Created .env from .env.example."
  else
    log "Preserving existing .env."
  fi
  if grep -Eq '^(MARIADB_ROOT_PASSWORD|MARIADB_PASSWORD|QUANT_DB_PASSWORD|SECRET_KEY)=change-me' "$REPO_ROOT/.env"; then
    log "WARNING: .env still contains change-me values. Replace them before shared/remote use."
  fi
}

ensure_network() {
  if docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    log "Docker network exists: $NETWORK_NAME"
  else
    docker network create --driver bridge "$NETWORK_NAME" >/dev/null
    log "Created Docker network: $NETWORK_NAME"
  fi
}

wait_for_health() {
  local container status attempt
  for container in "$MARIADB_CONTAINER" "$QUANT_CONTAINER" "$REDIS_CONTAINER" "$PGSTOCK_CONTAINER"; do
    status=""
    for attempt in $(seq 1 60); do
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
      [[ "$status" == healthy || "$status" == running ]] && break
      [[ "$status" == unhealthy || "$status" == exited || "$status" == dead ]] && break
      sleep 2
    done
    [[ "$status" == healthy || "$status" == running ]] || die "$container did not become healthy (status=${status:-missing})"
    log "$container: $status"
  done
}

start_databases() {
  require_docker
  init_env
  ensure_network
  if docker container inspect "$PGSTOCK_CONTAINER" >/dev/null 2>&1; then
    log "Reusing existing pg-stock container."
    if [[ "$(docker inspect -f '{{.State.Running}}' "$PGSTOCK_CONTAINER")" != true ]]; then
      docker start "$PGSTOCK_CONTAINER" >/dev/null
    fi
    docker network connect "$NETWORK_NAME" "$PGSTOCK_CONTAINER" >/dev/null 2>&1 || true
    "${COMPOSE[@]}" up -d mariadb postgres redis
  else
    "${COMPOSE[@]}" up -d mariadb postgres redis pg-stock
  fi
  wait_for_health
  if [[ "$WITH_APP" == true || "$SEED_OHLCV" == true ]]; then
    "${COMPOSE[@]}" up -d --build mariadb postgres redis python-backend frontend
  fi
  if [[ "$SEED_OHLCV" == true ]]; then
    "${COMPOSE[@]}" exec -T python-backend python crawl_major_ohlcv.py
  fi
}

verify_databases() {
  require_docker
  local maria_count quant_count stock_count redis_reply
  maria_count="$(docker exec "$MARIADB_CONTAINER" sh -ec '
    export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"
    mariadb -N -uroot "$MARIADB_DATABASE" -e "SELECT count(*) FROM information_schema.tables WHERE table_schema=DATABASE()"
  ')"
  quant_count="$(docker exec "$QUANT_CONTAINER" sh -ec '
    psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pg_tables WHERE schemaname=current_schema()"
  ')"
  stock_count="$(docker exec "$PGSTOCK_CONTAINER" sh -ec '
    psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM pg_tables WHERE schemaname=current_schema()"
  ')"
  redis_reply="$(docker exec "$REDIS_CONTAINER" redis-cli ping)"
  printf '%-26s %s\n' \
    'MariaDB mockinv tables:' "$maria_count" \
    'PostgreSQL quant tables:' "$quant_count" \
    'PostgreSQL pg-stock tables:' "$stock_count" \
    'Redis:' "$redis_reply" \
    'Qdrant:' 'in-memory; python-backend restart recreates seeded collection'
  [[ "$maria_count" -gt 0 ]] || die "MariaDB schema is empty"
  [[ "$quant_count" -gt 0 ]] || die "Quant schema is empty"
  [[ "$stock_count" -gt 0 ]] || die "pg-stock schema is empty"
  [[ "$redis_reply" == PONG ]] || die "Redis did not return PONG"
}

export_databases() {
  local parent="$1" stamp target
  require_docker
  require_command gzip
  require_command sha256sum
  stamp="$(date +%Y%m%dT%H%M%S)"
  mkdir -p "$parent"
  target="$(cd "$parent" && pwd)/stock-coin-trade-db-$stamp"
  install -d -m 0700 "$target"
  log "Exporting logical dumps to $target"
  docker exec "$MARIADB_CONTAINER" sh -ec '
    export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"
    exec mariadb-dump -uroot --databases "$MARIADB_DATABASE" \
      --single-transaction --quick --routines --events --triggers --hex-blob
  ' | gzip -9 >"$target/mariadb.sql.gz"
  docker exec "$QUANT_CONTAINER" sh -ec '
    exec pg_dump --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"
  ' | gzip -9 >"$target/quant.sql.gz"
  docker exec "$PGSTOCK_CONTAINER" sh -ec '
    exec pg_dump --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"
  ' | gzip -9 >"$target/pg-stock.sql.gz"
  gzip -t "$target/mariadb.sql.gz" "$target/quant.sql.gz" "$target/pg-stock.sql.gz"
  (cd "$target" && sha256sum mariadb.sql.gz quant.sql.gz pg-stock.sql.gz > SHA256SUMS)
  chmod 0600 "$target"/*.sql.gz "$target/SHA256SUMS"
  log "Export complete: $target"
  log "Copy this directory to the new PC with an encrypted disk, scp, or rsync over SSH."
}

restore_databases() {
  local source="$1" file start_app="$WITH_APP" app_was_running=false
  [[ "$CONFIRM_RESTORE" == true ]] || die "restore requires --confirm-restore"
  source="$(cd "$source" && pwd)"
  for file in mariadb.sql.gz quant.sql.gz pg-stock.sql.gz SHA256SUMS; do
    [[ -f "$source/$file" ]] || die "missing backup file: $source/$file"
  done
  require_command gzip
  require_command sha256sum
  (cd "$source" && sha256sum -c SHA256SUMS)
  if [[ "$(docker inspect -f '{{.State.Running}}' crypto-mock-python 2>/dev/null || true)" == true ]]; then
    app_was_running=true
    "${COMPOSE[@]}" stop frontend python-backend
    log "Stopped frontend/python-backend during database restore."
  fi
  # Restore DBs before starting Flask so requests/schedulers cannot write during import.
  WITH_APP=false
  SEED_OHLCV=false
  start_databases
  log "Restoring MariaDB mockinv..."
  gzip -cd "$source/mariadb.sql.gz" | docker exec -i "$MARIADB_CONTAINER" sh -ec '
    export MYSQL_PWD="$MARIADB_ROOT_PASSWORD"
    exec mariadb -uroot
  '
  log "Restoring PostgreSQL quant_research..."
  gzip -cd "$source/quant.sql.gz" | docker exec -i "$QUANT_CONTAINER" sh -ec '
    exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
  '
  log "Restoring PostgreSQL pg-stock..."
  gzip -cd "$source/pg-stock.sql.gz" | docker exec -i "$PGSTOCK_CONTAINER" sh -ec '
    exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
  '
  if [[ "$start_app" == true ]]; then
    "${COMPOSE[@]}" up -d --build mariadb postgres redis python-backend frontend
  elif [[ "$app_was_running" == true ]]; then
    "${COMPOSE[@]}" up -d python-backend frontend
  fi
  verify_databases
  log "Restore complete. Redis login sessions and in-memory Qdrant data are intentionally not migrated."
}

[[ $# -ge 1 ]] || { usage; exit 2; }
if [[ "$1" == -h || "$1" == --help ]]; then
  usage
  exit 0
fi
ACTION="$1"
shift
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-app) WITH_APP=true ;;
    --seed-ohlcv) SEED_OHLCV=true; WITH_APP=true ;;
    --confirm-restore) CONFIRM_RESTORE=true ;;
    -h|--help) usage; exit 0 ;;
    --*) die "unknown option: $1" ;;
    *) POSITIONAL+=("$1") ;;
  esac
  shift
done

cd "$REPO_ROOT"
case "$ACTION" in
  install)
    [[ ${#POSITIONAL[@]} -eq 0 ]] || die "install takes no path argument"
    install_docker
    ;;
  init)
    [[ ${#POSITIONAL[@]} -eq 0 ]] || die "init takes no path argument"
    start_databases
    verify_databases
    ;;
  verify)
    [[ ${#POSITIONAL[@]} -eq 0 ]] || die "verify takes no path argument"
    verify_databases
    ;;
  export)
    [[ ${#POSITIONAL[@]} -eq 1 ]] || die "export requires BACKUP_PARENT_DIR"
    export_databases "${POSITIONAL[0]}"
    ;;
  restore)
    [[ ${#POSITIONAL[@]} -eq 1 ]] || die "restore requires BACKUP_DIR"
    restore_databases "${POSITIONAL[0]}"
    ;;
  *)
    usage
    die "unknown command: $ACTION"
    ;;
esac
