# SAM 활용

SAM의 개념과 기본 명령을 익히는 과정입니다. Lambda/API Gateway 구성은 `LAMBDA_API.md`에서 이어집니다.

## 1. 설치 확인

```bash
cd /home/ubuntu/stock-coin-trade/working
scripts/preflight-check.sh
```

`sam --version`이 없을 때만 설치합니다.

```bash
scripts/install-sam.sh
```

`sam build --use-container`와 `sam local`에는 실행 중인 Docker가 필요합니다. AWS 배포에는 AWS CLI 자격증명과 리전 설정이 추가로 필요합니다.

## 2. SAM 구성 이해

- `Transform: AWS::Serverless-2016-10-31`: SAM 변환 활성화
- `AWS::Serverless::Function`: Lambda 함수 선언
- `CodeUri`, `Runtime`, `Handler`: 코드 위치와 Python 진입점
- `Events.HttpApi`: API Gateway 경로·메서드 연결
- `Outputs.ApiUrl`: 배포 후 호출할 기본 URL 출력

예제 템플릿은 `template/template-*.yaml`에 있습니다.

## 3. 검증과 빌드

타깃은 `member`, `quant`, `ohlcv`, `session`, `knowledge` 중 하나입니다.

```bash
scripts/sam-build.sh member
```

스크립트는 다음 두 명령을 실행하고 타깃별 빌드 디렉터리를 사용합니다.

```bash
sam validate --lint --template-file template/template-member.yaml
sam build --use-container \
  --template-file template/template-member.yaml \
  --build-dir .aws-sam/member
```

## 4. 단일 이벤트 호출

먼저 `env/local-env.json`의 `USER`, `PASSWORD` 자리표시자를 로컬 전용 값으로 바꿉니다. 파일을 실제 비밀값과 함께 커밋하지 않습니다.

```bash
scripts/sam-local-invoke.sh member
```

SAM 컨테이너는 호스트의 `127.0.0.1`이 아니라 Docker 서비스명으로 접근합니다. 기본 네트워크는 다음과 같습니다.

- member·quant·session·knowledge: `stock-coin-trade_internal`
- ohlcv: `postgresql_default`

다른 네트워크를 쓰면 `SAM_DOCKER_NETWORK`로 지정합니다.

```bash
SAM_DOCKER_NETWORK=my-network scripts/sam-local-invoke.sh member
```

## 5. 다음 과정

단일 핸들러 호출이 성공하면 `LAMBDA_API.md`의 `sam local start-api`와 AWS 배포로 진행합니다.
