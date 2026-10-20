#!/usr/bin/env bash
# 서버에서 pg-stock-api 컨테이너를 새 이미지로 다시 만든다 (설정은 그대로, 지정한 환경변수만 변경).
#
# 로컬 PC에서 (이미지는 미리 서버에서 docker build -t pg-stock-api-sample:latest 로 만들어 둔다):
#   ssh -i /home/l/stock-coin-trade/test-0922.pem ubuntu@13.209.87.155 'bash -s' \
#     < pg-stock-api-sample/scripts/redeploy_container.sh
#
# - 실행 중인 컨테이너의 환경변수(이미지 기본값 제외)·네트워크·포트·재시작 정책을 그대로 쓴다.
# - OVERRIDES 의 값만 바꾼다 (기본: KOSPI·KOSDAQ 주식 전체, 2016년부터).
# - EXTRA_ENV_FILE(기본 ~/pg-stock-api-deploy/minute.env)이 있으면 그 값(KIS 키, MINUTE_SYNC_ENABLED 등)도 넣는다.
# - 새 컨테이너가 /health 에 90초 안에 응답하지 않으면 원래 컨테이너로 되돌린다.
# - 원래 설정은 ~/pg-stock-api-deploy/ 에 백업한다.
set -euo pipefail

NAME="${NAME:-pg-stock-api}"
IMAGE="${IMAGE:-pg-stock-api-sample:latest}"
OVERRIDES="${OVERRIDES:-OHLCV_SYNC_TICKERS=listed OHLCV_SYNC_START_YEAR=2016}"
BACKUP_DIR="$HOME/pg-stock-api-deploy"
EXTRA_ENV_FILE="${EXTRA_ENV_FILE:-$BACKUP_DIR/minute.env}"
[ -r "$EXTRA_ENV_FILE" ] || EXTRA_ENV_FILE=""
TS="$(date +%Y%m%d%H%M%S)"

umask 077
mkdir -p "$BACKUP_DIR"
sudo docker inspect "$NAME" > "$BACKUP_DIR/$NAME.$TS.json"
OLD_IMAGE_ID="$(sudo docker inspect -f '{{.Image}}' "$NAME")"
sudo docker image inspect "$OLD_IMAGE_ID" > "$BACKUP_DIR/image.$TS.json"

# 이미지 기본값을 뺀 컨테이너 환경변수에 OVERRIDES를 적용해 env 파일을 만든다 (비밀값은 화면에 출력하지 않음).
EXTRA_ENV_FILE="$EXTRA_ENV_FILE" python3 - "$BACKUP_DIR/$NAME.$TS.json" "$BACKUP_DIR/image.$TS.json" "$BACKUP_DIR/app.env" $OVERRIDES <<'PY'
import json, os, sys
container_path, image_path, out_path, *overrides = sys.argv[1:]
extra = os.environ.get("EXTRA_ENV_FILE")
if extra:
    overrides += [line.strip() for line in open(extra) if "=" in line and not line.lstrip().startswith("#")]
container = json.load(open(container_path))[0]
image_env = set(json.load(open(image_path))[0]["Config"]["Env"] or [])
env = {}
for item in container["Config"]["Env"] or []:
    if item not in image_env:
        key, _, value = item.partition("=")
        env[key] = value
for item in overrides:
    key, _, value = item.partition("=")
    env[key] = value
with open(out_path, "w") as fh:
    fh.writelines(f"{k}={v}\n" for k, v in env.items())
ports = container["HostConfig"]["PortBindings"] or {}
args = []
for cport, bindings in ports.items():
    for b in bindings or []:
        host = f"{b['HostIp']}:" if b.get("HostIp") else ""
        args.append(f"-p {host}{b['HostPort']}:{cport.split('/')[0]}")
net = container["HostConfig"]["NetworkMode"]
restart = container["HostConfig"]["RestartPolicy"]["Name"] or "no"
print(f"NETWORK={net}\nRESTART={restart}\nPORT_ARGS=\"{' '.join(args)}\"", file=open(out_path + ".run", "w"))
print("환경변수:", ", ".join(env), "| 변경:", " ".join(o.split("=", 1)[0] + ("=***" if "KEY" in o or "SECRET" in o else "=" + o.split("=", 1)[1]) for o in overrides))
PY
# shellcheck disable=SC1091
source "$BACKUP_DIR/app.env.run"

OLD="$NAME-before-$TS"
sudo docker stop -t 20 "$NAME" >/dev/null
sudo docker rename "$NAME" "$OLD"
# shellcheck disable=SC2086
sudo docker run -d --name "$NAME" --restart "$RESTART" --network "$NETWORK" $PORT_ARGS \
  --env-file "$BACKUP_DIR/app.env" "$IMAGE" >/dev/null

PORT="$(sudo docker port "$NAME" 8010/tcp 2>/dev/null | head -n 1 | sed -E 's/.*:([0-9]+)$/\1/')"
for _ in $(seq 45); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:${PORT:-8010}/health")" = 200 ]; then
    sudo docker rm "$OLD" >/dev/null
    echo "교체 완료: $NAME ← $IMAGE (원래 설정 백업: $BACKUP_DIR/$NAME.$TS.json, 원래 이미지 $OLD_IMAGE_ID)"
    sudo docker exec "$NAME" sh -c 'env | grep -E "^OHLCV_SYNC_(TICKERS|START_YEAR)="'
    exit 0
  fi
  sleep 2
done

echo "새 컨테이너가 응답하지 않아 원래대로 되돌립니다." >&2
sudo docker logs --tail 30 "$NAME" >&2 || true
sudo docker rm -f "$NAME" >/dev/null 2>&1 || true
sudo docker rename "$OLD" "$NAME"
sudo docker start "$NAME" >/dev/null
exit 1
