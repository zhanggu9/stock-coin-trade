# working/ — SAM 활용 · Lambda/API 실습 파일

프런트 문서(`/sam-guide-1.html` → `-2` → `-3` → `/lambda-db-practice.html`)와 짝을 이룹니다.

1. [`SAM.md`](SAM.md) — SAM 소개, 설치, 검증, 빌드와 단일 로컬 호출 (프런트: SAM 활용 1·2)
2. [`LAMBDA_API.md`](LAMBDA_API.md) — DB Python을 Lambda로 만들고 API Gateway에 연결·배포 (프런트: SAM 활용 3, Lambda/API)

## 디렉터리

| 경로 | 내용 |
|---|---|
| `scripts/` | SAM 설치·빌드·로컬 invoke·local API·타깃별 배포 |
| `lambda/` | 5개 타깃의 핸들러, 서비스 함수, 이벤트와 requirements |
| `template/` | Secrets Manager·VPC·HttpApi·ApiUrl Output이 포함된 SAM 템플릿 |
| `env/` | 비밀값 없는 로컬 자리표시자와 Secret ARN 예시 |
| `sql/` | Lambda 서비스 함수가 사용하는 읽기 SQL |

실제 비밀번호, DB URL, API Key는 커밋하지 않습니다. 로컬 파일은 자리표시자만 유지하고 AWS 배포에서는 Secrets Manager ARN을 입력합니다.

## 현재 EC2와 예제의 차이

| 타깃 | 현재 상태 | 예제 실행 조건 |
|---|---|---|
| member | MariaDB 실행 중 | 로컬 Compose 네트워크 또는 AWS에서 도달 가능한 MariaDB 필요 |
| quant | PostgreSQL 실행 중 | 로컬 Compose 네트워크 또는 AWS에서 도달 가능한 PostgreSQL 필요 |
| ohlcv | pg-stock 미실행 | `postgresql_default` 네트워크와 `pg-stock` 준비 필요 |
| session | Redis 미배포 | Redis/ElastiCache와 Redis 세션 백엔드 배포 후 사용 |
| knowledge | 애플리케이션 인메모리 Qdrant | 별도 Qdrant 서버와 컬렉션·벡터 차원 준비 필요 |

따라서 현재 바로 연결 가능한 예제는 `member`, `quant`이며 나머지는 해당 저장소를 먼저 준비해야 합니다.
