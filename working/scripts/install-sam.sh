#!/usr/bin/env bash
# AWS SAM CLI 설치 (Linux). CPU 아키텍처를 자동 감지한다.
# 참고: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
set -euo pipefail

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)         SUFFIX="x86_64" ;;
  aarch64|arm64)  SUFFIX="arm64"  ;;
  *) echo "지원하지 않는 아키텍처: $ARCH" >&2; exit 1 ;;
esac

ZIP="aws-sam-cli-linux-${SUFFIX}.zip"
curl -L "https://github.com/aws/aws-sam-cli/releases/latest/download/${ZIP}" -o "$ZIP"
unzip -o "$ZIP" -d sam-installation
# 최초 설치는 install, 이미 있으면 --update.
sudo ./sam-installation/install || sudo ./sam-installation/install --update
sam --version
