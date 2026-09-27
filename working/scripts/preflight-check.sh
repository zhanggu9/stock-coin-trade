#!/usr/bin/env bash
# 설치 여부와 아키텍처를 먼저 확인한다. 정상 출력되면 설치 단계를 건너뛴다.
set -uo pipefail
echo "arch   : $(uname -m)"
if command -v sam >/dev/null 2>&1; then sam --version; else echo "sam    : 미설치 → scripts/install-sam.sh"; fi
if command -v aws >/dev/null 2>&1; then aws --version; else echo "aws    : 미설치 (배포에 필요)"; fi
if command -v docker >/dev/null 2>&1; then
  docker --version
  docker info >/dev/null 2>&1 && echo "docker : daemon ready" || echo "docker : daemon unavailable"
else
  echo "docker : 미설치 (sam build --use-container / sam local에 필요)"
fi
for network in stock-coin-trade_internal postgresql_default; do
  docker network inspect "$network" >/dev/null 2>&1 && echo "network: $network" || true
done
