#!/usr/bin/env bash
set -euo pipefail

# EC2 인스턴스의 저장소 루트에서 실행한다.
python3 -m py_compile python-stock-backend/*.py
docker compose up -d --build --remove-orphans
docker compose ps
