# Lambda/API — SAM으로 Lambda와 API Gateway 연결

## 1. 타깃과 API

| 타깃 | 로컬/AWS 경로 | 메서드 | AWS 인증 | 기본 스택명 |
|---|---|---|---|---|
| member | `/members/{member_id}` | GET | JWT | `stock-coin-trade-member-practice` |
| quant | `/quant/prices?symbol=005930&limit=30` | GET | 공개 읽기 실습 | `stock-coin-trade-quant-practice` |
| ohlcv | `/ohlcv/summary` | GET | 공개 읽기 실습 | `stock-coin-trade-ohlcv-practice` |
| session | `/internal/session-check?sid=...` | GET | JWT | `stock-coin-trade-session-practice` |
| knowledge | `/knowledge/search` | POST | 공개 읽기 실습 | `stock-coin-trade-knowledge-practice` |

회원과 세션 진단 API는 Cognito 또는 OIDC JWT issuer/audience가 없으면 배포할 수 없게 구성했습니다. 공개 읽기 예제도 운영 전에는 JWT·IAM·Lambda Authorizer 중 하나를 적용하고 제한·모니터링을 추가합니다.

## 2. Python 구성

각 `lambda/<target>/`은 다음 구조입니다.

- `lambda_*.py`: API Gateway event 파싱과 HTTP 응답
- `*_service.py`: Flask에 의존하지 않는 DB 함수
- `requirements.txt`: 해당 함수의 최소 의존성
- `event.json`: `sam local invoke` 입력

## 3. AWS 접속 설정

`working/env/lambda.env`에 EC2 사설 IP로 연결하는 DB URL과 VPC 값을 넣습니다.
이 파일에는 비밀번호가 있으므로 Git에 커밋하지 않습니다. 현재 SAM 템플릿은 URL을
`NoEcho` CloudFormation 파라미터로 받고 Lambda 환경 변수에 전달합니다.
Secrets Manager ARN을 받는 구성은 아닙니다.

OHLCV는 `LAMBDA_OHLCV_DATABASE_URL`, `VPC_ID`, `VPC_SUBNET_IDS`가 필요합니다.
ALB까지 만들려면 `LAMBDA_OHLCV_CREATE_ALB='true'`로 설정합니다. HTTPS에는
`LAMBDA_OHLCV_CERTIFICATE_ARN`도 넣습니다. `pg-stock`은 EC2 사설 IP의
55432 포트에 연결돼 있어야 합니다.

## 4. 로컬 API Gateway 경로 테스트

터미널 1:

```bash
cd /home/ubuntu/stock-coin-trade/working
scripts/sam-build.sh member
scripts/sam-local-start-api.sh member 3001
```

터미널 2:

```bash
curl --fail-with-body http://127.0.0.1:3001/members/1
```

다른 예:

```bash
scripts/sam-local-start-api.sh quant 3001
curl --fail-with-body 'http://127.0.0.1:3001/quant/prices?symbol=005930&limit=30'
```

`sam local start-api`는 관리형 JWT Authorizer의 동작을 완전히 대체하지 않습니다. 배포 후 유효·만료·누락 토큰을 각각 다시 검사합니다.

## 5. 타깃별 AWS 배포

```bash
scripts/sam-deploy.sh member
```

OHLCV Lambda, HTTP API, ALB를 배포하려면 다음 명령을 실행합니다.

```bash
scripts/sam-deploy.sh ohlcv
```

OHLCV 템플릿은 Lambda SG를 직접 생성합니다. 기존 VPC에 ALB용 두 번째
서브넷을 생성하며, 기본 CIDR은 `172.31.1.0/24`입니다. 최초 배포 시 해당 CIDR이
비어 있어야 합니다.

각 타깃은 별도 build 디렉터리, `samconfig` 환경과 CloudFormation 스택을 사용하므로 다른 타깃을 교체하지 않습니다. 배포 후 스크립트가 `Outputs`의 `ApiUrl`을 표시합니다.

## 6. 배포 API 확인

공개 읽기 예제:

```bash
API_URL="$(aws cloudformation describe-stacks \
  --stack-name stock-coin-trade-quant-practice \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)"
curl --fail-with-body "$API_URL/quant/prices?symbol=005930&limit=30"
```

OHLCV 공개 조회 확인:

```bash
ALB_URL="$(aws cloudformation describe-stacks \
  --stack-name stock-coin-trade-ohlcv-practice \
  --query 'Stacks[0].Outputs[?OutputKey==`AlbUrl`].OutputValue' \
  --output text)"
# ALB 기본 DNS용 자체 서명 인증서를 명시적으로 신뢰합니다.
curl --fail-with-body --cacert env/ohlcv-alb-selfsigned-cert.pem "$ALB_URL/ohlcv/health"
curl --fail-with-body --cacert env/ohlcv-alb-selfsigned-cert.pem "$ALB_URL/ohlcv/summary"
```

ALB의 80 포트는 HTTPS 443으로 리다이렉트합니다. 인증서는 자체 서명이라 일반
브라우저와 기본 `curl` 신뢰 저장소에는 포함되지 않습니다. 인증서 파일 없이
테스트할 때만 `curl -k`를 사용할 수 있습니다. 인증서와 개인키는
`working/env/ohlcv-alb-selfsigned-*.pem`에 0600 권한으로 보관하며 Git에서 제외됩니다.
ACM에 가져온 인증서는 자동 갱신되지 않으므로 만료일인 2027-09-28 전에 갱신해야 합니다.

JWT 보호 API:

```bash
curl --fail-with-body \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_URL/members/1"
```

로그:

```bash
sam logs --stack-name stock-coin-trade-member-practice \
  --name DatabasePracticeFunction --tail
```

## 7. 삭제

실습 리소스를 남기지 않을 때 타깃의 설정 환경과 스택을 삭제합니다.

```bash
sam delete \
  --stack-name stock-coin-trade-member-practice \
  --config-file template/samconfig.toml \
  --config-env member
```
