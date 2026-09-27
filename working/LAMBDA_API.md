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

## 3. Secrets Manager

SAM 템플릿에는 비밀번호를 넣지 않습니다. Secret JSON은 타깃별로 다음 키를 사용합니다.

```json
{"DATABASE_URL":"mysql+pymysql://USER:PASSWORD@DB_ENDPOINT:3306/mockinv"}
{"QUANT_DATABASE_URL":"postgresql+psycopg://USER:PASSWORD@DB_ENDPOINT:5432/quant_research"}
{"OHLCV_DATABASE_URL":"postgresql+psycopg://USER:PASSWORD@DB_ENDPOINT:5432/admin"}
{"REDIS_URL":"rediss://REDIS_ENDPOINT:6379/0"}
{"QDRANT_URL":"https://QDRANT_ENDPOINT","QDRANT_API_KEY":"SECRET"}
```

배포 시에는 값이 아니라 Secret ARN을 입력합니다. Lambda 환경변수에는 ARN만 들어가며, 핸들러가 cold start에서 Secret JSON을 읽습니다. 실행 역할에는 해당 Secret 읽기 권한만 부여합니다. 로컬에서는 `env/local-env.json`의 직접 URL을 우선 사용합니다.

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

첫 실행의 guided 질문에서 다음을 입력합니다.

- `DatabaseSecretArn` 등 타깃의 Secret ARN
- `VpcSecurityGroupIds`: Lambda 전용 SG
- `VpcSubnetIds`: private subnet 두 개 이상
- member/session은 `JwtIssuer`, `JwtAudience`

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
