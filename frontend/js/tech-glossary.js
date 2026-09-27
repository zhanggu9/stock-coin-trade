/* 기술 용어 모달 사전 — Data Base / API 문서 공용
 * 본문 텍스트에서 리소스·기술 스택 이름을 찾아 클릭 가능한 용어로 바꾸고,
 * 클릭하면 설명 모달을 띄운다. <pre>·<code>·링크·표 그리드·SVG 안은 건드리지 않는다.
 * 사용: <script src="/js/tech-glossary.js" data-glossary-root="main"></script>
 */
(() => {
  const L = (label, url) => ({ label, url });
  const AWS = 'https://docs.aws.amazon.com/';

  // key: { t: 표시 이름, a: 별칭(정규식용 문자열), c: 분류, d: 설명(HTML 허용), l: 링크 }
  const GLOSSARY = {
    sam: { t: 'AWS SAM', a: ['AWS SAM', 'SAM'], c: 'AWS · 배포', d: 'Serverless Application Model. CloudFormation을 확장한 오픈소스 규격으로, <b>AWS::Serverless::Function</b> 같은 짧은 선언을 Lambda·API Gateway·IAM 역할 등 실제 리소스로 변환(Transform)합니다. 템플릿 규격(serverless-application-model)과 터미널 도구(SAM CLI)는 별개 저장소입니다.', l: [L('SAM 개발자 가이드', AWS + 'serverless-application-model/latest/developerguide/'), L('이 사이트: SAM 활용 1', '/sam-guide-1.html')] },
    samcli: { t: 'SAM CLI', a: ['SAM CLI'], c: 'AWS · 도구', d: '<b>sam</b> 명령을 제공하는 CLI입니다. <b>init</b>(프로젝트 생성) → <b>validate</b>(템플릿 검사) → <b>build</b>(의존성 설치·패키징) → <b>local invoke / start-api</b>(Docker로 로컬 실행) → <b>deploy</b>(CloudFormation 배포) → <b>logs</b> → <b>delete</b> 흐름을 한 도구로 묶습니다.', l: [L('SAM CLI 명령 레퍼런스', AWS + 'serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html')] },
    transform: { t: 'Transform (SAM 변환)', a: ['Transform'], c: 'AWS · 배포', d: '템플릿 상단의 <b>Transform: AWS::Serverless-2016-10-31</b> 선언입니다. CloudFormation이 이 매크로를 보고 SAM 리소스를 표준 CloudFormation 리소스로 펼칩니다. 이 줄이 없으면 <b>AWS::Serverless::*</b> 타입을 인식하지 못합니다.', l: [L('SAM 템플릿 구조', AWS + 'serverless-application-model/latest/developerguide/sam-specification-template-anatomy.html')] },
    cfn: { t: 'CloudFormation', a: ['CloudFormation'], c: 'AWS · 배포', d: 'AWS 리소스를 YAML/JSON 템플릿으로 선언하고 <b>스택</b> 단위로 생성·변경·삭제하는 서비스입니다. SAM 배포는 결국 CloudFormation 스택 작업이며, 실패 시 자동 롤백됩니다. <b>Outputs</b>에 API URL 같은 값을 내보내 다른 도구에서 읽습니다.', l: [L('CloudFormation 사용자 가이드', AWS + 'AWSCloudFormation/latest/UserGuide/')] },
    changeset: { t: 'Changeset (변경 세트)', a: ['changeset', 'Changeset', '변경 세트'], c: 'AWS · 배포', d: '배포 전에 CloudFormation이 "무엇을 추가·수정·교체·삭제할지" 미리 계산한 목록입니다. <b>sam deploy</b>의 <b>confirm_changeset = true</b>는 이 목록을 보여주고 y/N를 묻습니다. CI에서는 <b>--no-confirm-changeset</b>으로 끕니다.', l: [L('Change sets', AWS + 'AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-changesets.html')] },
    lambda: { t: 'AWS Lambda', a: ['AWS Lambda', 'Lambda'], c: 'AWS · 컴퓨팅', d: '서버 없이 함수 코드만 올려 이벤트(HTTP 요청, 스케줄 등)에 따라 실행하는 서비스입니다. 실행 시간과 메모리로 과금되며, 함수마다 <b>Runtime</b>(예: python3.12), <b>Handler</b>(파일.함수), <b>Timeout</b>, <b>MemorySize</b>, 실행 역할(IAM)을 가집니다. 이 저장소에서는 DB 조회 Python 함수를 Lambda로 분리하는 실습을 합니다.', l: [L('Lambda Python 핸들러', AWS + 'lambda/latest/dg/python-handler.html'), L('이 사이트: Lambda/API 실습', '/lambda-db-practice.html')] },
    coldstart: { t: 'Cold start', a: ['cold start', 'Cold start', '콜드 스타트'], c: 'AWS · 컴퓨팅', d: '한동안 호출이 없던 Lambda가 새 실행 환경을 만들며 코드를 처음 로드하는 과정입니다. 이때 모듈 최상단 코드(DB 엔진 생성, Secret 읽기)가 실행되므로 첫 호출이 느리고, 설정 오류도 이 시점에 드러납니다. 이후 warm 호출은 같은 환경을 재사용합니다.', l: [L('Lambda 실행 환경', AWS + 'lambda/latest/dg/lambda-runtime-environment.html')] },
    apigw: { t: 'API Gateway', a: ['API Gateway', 'HTTP API', 'HttpApi', 'REST API'], c: 'AWS · 네트워크', d: 'HTTPS 엔드포인트를 만들어 요청을 Lambda 등으로 전달하는 관리형 서비스입니다. SAM에서 <b>Events.Type: HttpApi</b>(API Gateway v2, 저렴·단순)나 <b>Type: Api</b>(REST API v1, 기능 많음)로 선언하면 라우트·통합·호출 권한이 함께 만들어집니다. 응답의 statusCode·headers·body 형식을 핸들러가 맞춰야 합니다.', l: [L('SAM HttpApi 이벤트', AWS + 'serverless-application-model/latest/developerguide/sam-property-function-httpapi.html')] },
    secrets: { t: 'Secrets Manager', a: ['Secrets Manager', 'Secret ARN'], c: 'AWS · 보안', d: 'DB 비밀번호·API 키 같은 비밀값을 암호화해 저장하고 IAM 권한으로 읽게 하는 서비스입니다. 템플릿과 환경변수에는 값이 아니라 <b>ARN</b>만 두고, 코드가 실행 시 JSON을 읽습니다. VPC 안의 Lambda가 접근하려면 VPC Endpoint 또는 NAT가 필요합니다.', l: [L('Secrets Manager', AWS + 'secretsmanager/latest/userguide/'), L('이 사이트: 키 적재·연결 가이드', '/learning/aws-ssm-key-management.html')] },
    iam: { t: 'IAM', a: ['IAM'], c: 'AWS · 보안', d: 'Identity and Access Management. 누가(사용자·역할) 무엇을(액션) 어떤 리소스에 할 수 있는지 정하는 권한 체계입니다. Lambda는 <b>실행 역할</b>로 Secrets Manager 읽기·로그 쓰기·VPC ENI 생성을 하고, SAM 배포 시 <b>CAPABILITY_IAM</b>은 이런 역할을 템플릿이 만들도록 허용합니다.', l: [L('IAM 사용자 가이드', AWS + 'IAM/latest/UserGuide/')] },
    vpc: { t: 'VPC', a: ['VPC'], c: 'AWS · 네트워크', d: 'Virtual Private Cloud. 계정 안의 격리된 가상 네트워크입니다. DB가 private 서브넷에 있으면 Lambda도 같은 VPC에 넣어야 접근할 수 있는데, 그 순간 Lambda는 인터넷·AWS API에 직접 나갈 수 없게 되어 NAT 또는 VPC Endpoint가 필요해집니다.', l: [L('Lambda VPC 연결', AWS + 'lambda/latest/dg/configuration-vpc.html')] },
    subnet: { t: '서브넷 (Subnet)', a: ['서브넷', 'Subnet', 'private subnet', 'private 서브넷'], c: 'AWS · 네트워크', d: 'VPC를 가용영역(AZ)별로 나눈 IP 대역입니다. 인터넷 게이트웨이 경로가 있으면 <b>public</b>, 없으면 <b>private</b>입니다. Lambda·DB는 보통 private 서브넷 두 개 이상(AZ 분산)에 둡니다. SAM 템플릿의 <b>VpcSubnetIds</b> 파라미터가 이 값입니다.', l: [L('VPC 서브넷', AWS + 'vpc/latest/userguide/configure-subnets.html')] },
    sg: { t: '보안 그룹 (Security Group)', a: ['보안 그룹', 'Security Group', 'SG'], c: 'AWS · 네트워크', d: '인스턴스·Lambda·DB에 붙는 상태 저장 방화벽입니다. 규칙은 "어디서(SG 또는 CIDR) 어떤 포트로"입니다. 권장 구성은 <b>Lambda SG</b>는 인바운드 없음, <b>DB SG</b>는 Lambda SG에서 오는 DB 포트(3306/5432/6379)만 허용입니다.', l: [L('보안 그룹', AWS + 'vpc/latest/userguide/vpc-security-groups.html')] },
    vpce: { t: 'VPC Endpoint', a: ['VPC Endpoint', 'VPC 엔드포인트', 'Interface Endpoint'], c: 'AWS · 네트워크', d: 'VPC 안에서 인터넷을 거치지 않고 AWS 서비스(Secrets Manager, S3 등)에 닿게 하는 사설 진입점입니다. 인터페이스 엔드포인트는 서브넷에 ENI를 만들며 시간당 과금됩니다. NAT보다 저렴하지만 서비스마다 하나씩 필요합니다.', l: [L('Secrets Manager VPC Endpoint', AWS + 'secretsmanager/latest/userguide/vpc-endpoint-overview.html')] },
    nat: { t: 'NAT Gateway', a: ['NAT Gateway', 'NAT'], c: 'AWS · 네트워크', d: 'private 서브넷의 리소스가 인터넷으로 나갈 수 있게 해 주는 관리형 주소 변환 장치입니다. 시간당 + 처리량 과금이라 실습에서는 비용 주의 대상입니다. Secrets Manager만 필요하면 VPC Endpoint가 더 저렴합니다.', l: [L('NAT Gateway', AWS + 'vpc/latest/userguide/vpc-nat-gateway.html')] },
    cw: { t: 'CloudWatch', a: ['CloudWatch Logs', 'CloudWatch'], c: 'AWS · 운영', d: '로그·지표·알람 서비스입니다. Lambda의 print/logging 출력은 <b>/aws/lambda/&lt;함수명&gt;</b> 로그 그룹에 쌓이고, <b>sam logs</b>가 이를 읽습니다. 보존 기간(RetentionInDays)을 두지 않으면 영구 보관되며, Errors 지표에 알람을 걸어 장애를 감지합니다.', l: [L('Lambda 로그', AWS + 'lambda/latest/dg/monitoring-cloudwatchlogs.html')] },
    cognito: { t: 'Amazon Cognito', a: ['Cognito'], c: 'AWS · 보안', d: '사용자 가입·로그인과 토큰 발급을 맡는 관리형 인증 서비스입니다. <b>User Pool</b>이 OIDC issuer 역할을 하고, 앱 클라이언트 ID가 audience가 되어 API Gateway JWT Authorizer의 검증 기준이 됩니다.', l: [L('Cognito User Pools', AWS + 'cognito/latest/developerguide/cognito-user-identity-pools.html')] },
    jwt: { t: 'JWT', a: ['JWT Authorizer', 'JWT'], c: '보안 · 인증', d: 'JSON Web Token. 발급자(issuer)가 서명한 클레임 묶음으로, <b>Authorization: Bearer &lt;token&gt;</b> 헤더로 전달합니다. API Gateway HTTP API는 issuer·audience만 설정하면 서명·만료를 자동 검증해 Lambda 앞에서 401을 돌려줍니다.', l: [L('HTTP API JWT Authorizer', AWS + 'apigateway/latest/developerguide/http-api-jwt-authorizer.html')] },
    bearer: { t: 'Bearer 토큰', a: ['Bearer'], c: '보안 · 인증', d: 'HTTP <b>Authorization: Bearer &lt;토큰&gt;</b> 형식입니다. "토큰을 가진(bearer) 쪽을 신뢰"하므로 토큰 유출이 곧 권한 유출입니다. HTTPS에서만 쓰고 로그·URL에 남기지 않습니다.', l: [L('RFC 6750', 'https://datatracker.ietf.org/doc/html/rfc6750')] },
    oidc: { t: 'OIDC', a: ['OIDC'], c: '보안 · 인증', d: 'OpenID Connect. OAuth 2.0 위에 "누가 로그인했는가"를 표준화한 프로토콜입니다. Cognito·Google 등이 issuer가 되어 JWT를 발급하며, GitHub Actions도 OIDC로 AWS 역할을 맡아 액세스 키 없이 배포할 수 있습니다.', l: [L('GitHub OIDC → AWS', 'https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services')] },
    s3: { t: 'Amazon S3', a: ['S3'], c: 'AWS · 스토리지', d: '객체 스토리지입니다. SAM은 배포 아티팩트(zip)를 S3 버킷에 올린 뒤 CloudFormation이 가져가게 하며, <b>resolve_s3 = true</b>가 이 버킷을 자동 생성합니다. DB 백업 파일의 오프사이트 보관처로도 흔히 씁니다.', l: [L('S3 사용자 가이드', AWS + 'AmazonS3/latest/userguide/')] },
    ecr: { t: 'Amazon ECR', a: ['ECR'], c: 'AWS · 컨테이너', d: 'Docker 이미지를 저장하는 관리형 레지스트리입니다. 이 저장소의 <b>docker-compose.prod.yml</b>은 ECR 이미지를 참조하도록 되어 있고, 현재 EC2 배포는 소스를 rsync해 인스턴스에서 직접 빌드하는 방식을 씁니다.', l: [L('ECR', AWS + 'AmazonECR/latest/userguide/')] },
    ec2: { t: 'Amazon EC2', a: ['EC2'], c: 'AWS · 컴퓨팅', d: '가상 서버입니다. 이 프로젝트의 운영 환경은 EC2 한 대 위에서 Docker Compose로 frontend(nginx)·python-backend·MariaDB·PostgreSQL·Redis·pg-stock을 실행하며, GitHub Actions가 main 푸시 시 SSH로 재빌드합니다.', l: [L('이 사이트: DB 백업 정책', '/db-backup-policy.html')] },
    eip: { t: 'Elastic IP', a: ['Elastic IP'], c: 'AWS · 네트워크', d: '인스턴스를 재시작·교체해도 유지되는 고정 공인 IPv4 주소입니다. 도메인 A 레코드와 배포 스크립트의 접속 대상이 이 주소를 가리킵니다.', l: [L('Elastic IP', AWS + 'AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html')] },
    rds: { t: 'Amazon RDS', a: ['RDS'], c: 'AWS · 데이터베이스', d: '관리형 관계형 DB(MariaDB·PostgreSQL 등)입니다. EC2 안의 Docker DB 대신 RDS로 옮기면 백업·패치·다중 AZ를 AWS가 맡고, Lambda는 같은 VPC의 SG 규칙만으로 접근합니다. 비용은 올라갑니다.', l: [L('RDS', AWS + 'AmazonRDS/latest/UserGuide/')] },
    elasticache: { t: 'ElastiCache', a: ['ElastiCache'], c: 'AWS · 데이터베이스', d: '관리형 Redis/Memcached입니다. 세션 저장소를 AWS로 옮길 때의 대상이며, TLS 연결은 <b>rediss://</b> URL을 씁니다.', l: [L('ElastiCache', AWS + 'AmazonElastiCache/latest/dg/')] },
    docker: { t: 'Docker', a: ['Docker'], c: '인프라 · 컨테이너', d: '애플리케이션을 이미지로 묶어 격리된 컨테이너로 실행하는 도구입니다. SAM은 <b>sam build --use-container</b>와 <b>sam local</b>에서 Lambda와 같은 이미지를 띄우기 위해 Docker 데몬을 요구합니다. 이 저장소의 모든 서비스도 Docker 컨테이너입니다.', l: [L('Docker 문서', 'https://docs.docker.com/')] },
    compose: { t: 'Docker Compose', a: ['Docker Compose', 'docker compose', 'Compose'], c: '인프라 · 컨테이너', d: '여러 컨테이너를 <b>docker-compose.yml</b> 한 파일로 정의·기동하는 도구입니다. 서비스명(mariadb, postgres, redis)이 곧 컨테이너 간 DNS 이름이고, 같은 네트워크(<b>stock-coin-trade_internal</b>)에 붙은 컨테이너끼리만 그 이름으로 통신합니다. 오버레이 파일(ssl, pg-stock)을 -f로 겹쳐 씁니다.', l: [L('Compose 문서', 'https://docs.docker.com/compose/')] },
    volume: { t: 'Docker 볼륨', a: ['볼륨', 'Volume'], c: '인프라 · 컨테이너', d: '컨테이너가 지워져도 남는 데이터 저장 영역입니다. DB 데이터 디렉터리(mariadb-data, postgres-quant-data, pg-stock-data)가 볼륨이며, 백업은 볼륨 파일 복사가 아니라 덤프 도구로 논리 백업을 뜹니다.', l: [L('Volumes', 'https://docs.docker.com/storage/volumes/')] },
    nginx: { t: 'nginx', a: ['nginx', 'Nginx'], c: '인프라 · 웹 서버', d: '정적 파일 서빙과 리버스 프록시를 맡는 웹 서버입니다. 이 프로젝트의 frontend 컨테이너가 nginx이며, HTML/JS를 서빙하고 <b>/api/</b>를 python-backend로 프록시합니다. 이미지에 파일이 구워지므로 수정 후에는 재빌드가 필요합니다.', l: [L('nginx 문서', 'https://nginx.org/en/docs/')] },
    healthcheck: { t: '헬스체크', a: ['헬스체크', 'Healthcheck', 'healthcheck'], c: '인프라 · 운영', d: '서비스가 살아 있는지 주기적으로 확인하는 검사입니다. Compose의 <b>healthcheck</b>는 depends_on 순서 제어에 쓰이고, 배포 워크플로의 헬스체크는 재기동 후 HTTP 200을 확인해 실패 시 배포를 실패로 표시합니다.', l: [L('Compose healthcheck', 'https://docs.docker.com/reference/compose-file/services/#healthcheck')] },
    postgres: { t: 'PostgreSQL', a: ['PostgreSQL', 'Postgres', 'psql'], c: '데이터베이스', d: '오픈소스 관계형 DB입니다. 이 프로젝트는 두 인스턴스를 씁니다. <b>quant_research</b>(전략·체결·팩터)와 <b>pg-stock</b>(국내주식 OHLCV). Python에서는 SQLAlchemy + psycopg로 접속하고, 백업은 <b>pg_dump</b>, 접속 도구는 <b>psql</b>입니다.', l: [L('PostgreSQL 문서', 'https://www.postgresql.org/docs/'), L('이 사이트: OHLCV DB', '/ohlcv-db.html')] },
    pgvector: { t: 'pgvector', a: ['pgvector'], c: '데이터베이스', d: 'PostgreSQL에 벡터 타입과 유사도 검색을 추가하는 확장입니다. Qdrant 같은 전용 벡터 DB 대신 기존 PostgreSQL 안에서 임베딩을 저장·검색할 때 씁니다.', l: [L('pgvector', 'https://github.com/pgvector/pgvector')] },
    mariadb: { t: 'MariaDB', a: ['MariaDB', 'MySQL'], c: '데이터베이스', d: 'MySQL 호환 오픈소스 관계형 DB입니다. 이 프로젝트의 서비스 DB(<b>mockinv</b>: 회원·포지션·모의주문·감사 로그)이며, Python에서는 <b>mysql+pymysql://</b> URL로 접속합니다. 백업은 <b>mysqldump</b>입니다.', l: [L('MariaDB 문서', 'https://mariadb.com/kb/en/documentation/'), L('이 사이트: DB 스키마', '/quant.html?tab=schema')] },
    redis: { t: 'Redis', a: ['Redis'], c: '데이터베이스', d: '메모리 기반 키-값 저장소입니다. 이 프로젝트에서는 Flask 로그인 세션을 <b>stock-coin-trade:session:&lt;sid&gt;</b> 키로 저장하고 7일 TTL을 둡니다. Lambda session 타깃은 이 키의 TTL을 조회합니다.', l: [L('Redis 문서', 'https://redis.io/docs/')] },
    ttl: { t: 'TTL', a: ['TTL'], c: '데이터베이스', d: 'Time To Live. 키가 자동 만료되기까지 남은 시간(초)입니다. Redis <b>TTL key</b>는 남은 초를, -1은 만료 없음, -2는 키 없음을 뜻합니다. 세션 만료·캐시 수명 관리에 씁니다.', l: [L('Redis TTL', 'https://redis.io/docs/latest/commands/ttl/')] },
    qdrant: { t: 'Qdrant', a: ['Qdrant'], c: '데이터베이스 · 벡터', d: '임베딩 벡터를 저장하고 유사도(코사인 등)로 검색하는 벡터 DB입니다. 컬렉션마다 벡터 차원이 고정됩니다. 현재 애플리케이션은 인메모리 모드를 쓰므로 Lambda에서 접근하려면 별도 서버가 필요합니다.', l: [L('Qdrant 문서', 'https://qdrant.tech/documentation/')] },
    embedding: { t: '임베딩 (Embedding)', a: ['임베딩'], c: 'AI · 검색', d: '문장·문서를 의미를 담은 고정 길이 숫자 벡터로 바꾼 것입니다. 비슷한 뜻의 문서는 가까운 벡터가 되어, Qdrant·pgvector에서 "유사한 문서 찾기"가 가능해집니다. 모델을 바꾸면 차원이 달라져 컬렉션을 다시 만들어야 합니다.', l: [L('Qdrant: 벡터와 임베딩', 'https://qdrant.tech/documentation/concepts/vectors/')] },
    sqlalchemy: { t: 'SQLAlchemy', a: ['SQLAlchemy'], c: 'Python · DB', d: 'Python DB 툴킷입니다. <b>create_engine(URL)</b>으로 커넥션 풀을 만들고 <b>text()</b>로 파라미터 바인딩 SQL을 실행합니다. URL 스킴(mysql+pymysql, postgresql+psycopg)이 드라이버를 정합니다. Lambda에서는 엔진을 핸들러 밖에서 한 번만 만듭니다.', l: [L('SQLAlchemy 문서', 'https://docs.sqlalchemy.org/')] },
    psycopg: { t: 'psycopg', a: ['psycopg'], c: 'Python · DB', d: 'PostgreSQL용 Python 드라이버(3.x)입니다. SQLAlchemy URL <b>postgresql+psycopg://</b>가 이 드라이버를 씁니다. 바이너리 휠이 있어 <b>sam build --use-container</b>로 Lambda 환경에 맞게 설치합니다.', l: [L('psycopg 3', 'https://www.psycopg.org/psycopg3/docs/')] },
    pymysql: { t: 'PyMySQL', a: ['PyMySQL', 'pymysql'], c: 'Python · DB', d: '순수 Python으로 작성된 MySQL/MariaDB 드라이버입니다. 네이티브 빌드가 없어 Lambda 패키징이 쉽고, SQLAlchemy URL <b>mysql+pymysql://</b> 또는 직접 <b>pymysql.connect()</b>로 씁니다.', l: [L('PyMySQL', 'https://pymysql.readthedocs.io/')] },
    boto3: { t: 'boto3', a: ['boto3'], c: 'Python · AWS', d: 'AWS 공식 Python SDK입니다. Lambda 런타임에 기본 포함되어 있어 requirements에 넣지 않아도 되며, <b>client("secretsmanager").get_secret_value()</b>처럼 서비스를 호출합니다. 자격증명은 실행 역할에서 자동으로 얻습니다.', l: [L('boto3 문서', 'https://boto3.amazonaws.com/v1/documentation/api/latest/index.html')] },
    flask: { t: 'Flask', a: ['Flask'], c: 'Python · 웹', d: '이 프로젝트 python-backend의 웹 프레임워크입니다. <b>/api/*</b> 라우트와 로그인 세션을 처리합니다. Lambda 실습은 Flask에 의존하지 않는 서비스 함수를 분리해 핸들러에서 재사용하는 방식으로 진행합니다.', l: [L('Flask 문서', 'https://flask.palletsprojects.com/')] },
    apscheduler: { t: 'APScheduler', a: ['APScheduler'], c: 'Python · 스케줄', d: 'Python 프로세스 안에서 주기 작업을 실행하는 스케줄러입니다. python-backend가 OHLCV 수집·집계 같은 정기 작업을 이 방식으로 돌립니다. 프로세스가 죽으면 작업도 멈추므로 운영에서는 systemd timer나 EventBridge와 비교해 선택합니다.', l: [L('APScheduler', 'https://apscheduler.readthedocs.io/')] },
    python: { t: 'Python 런타임', a: ['python3.14', 'python3.12', 'python3.11', 'Python 3.11', 'Python 3.12'], c: 'Python', d: 'Lambda 함수가 실행될 Python 버전입니다. 템플릿의 <b>Runtime</b>과 <b>sam build --use-container</b>가 받는 빌드 이미지가 이 값으로 정해집니다. 로컬 개발 버전과 달라도 되지만, 네이티브 휠(psycopg 등)은 런타임 버전에 맞게 빌드돼야 합니다.', l: [L('Lambda Python 런타임', AWS + 'lambda/latest/dg/lambda-python.html')] },
    pytest: { t: 'pytest', a: ['pytest'], c: 'Python · 테스트', d: 'Python 테스트 러너입니다. <b>sam init</b> 템플릿의 <b>tests/unit</b>은 핸들러를 직접 import해 이벤트를 넣고 응답을 검사합니다. Docker 없이 빠르게 돌릴 수 있어 로직 검증에 먼저 씁니다.', l: [L('pytest', 'https://docs.pytest.org/')] },
    gha: { t: 'GitHub Actions', a: ['GitHub Actions'], c: 'CI/CD', d: 'GitHub 저장소 이벤트(push 등)로 워크플로를 실행하는 CI/CD입니다. 이 저장소의 <b>deploy-ec2.yml</b>은 main 푸시 시 rsync + docker compose로 EC2를 갱신합니다. Lambda 배포는 OIDC 역할 + <b>sam deploy</b>를 쓰는 별도 워크플로로 설계합니다.', l: [L('GitHub Actions 문서', 'https://docs.github.com/actions')] },
    rsync: { t: 'rsync', a: ['rsync'], c: '인프라 · 도구', d: '변경된 파일만 전송하는 동기화 도구입니다. 배포 워크플로가 SSH 위에서 rsync로 소스를 EC2에 올리며, <b>--exclude</b>로 .env·키 파일·node_modules를 제외합니다.', l: [L('rsync', 'https://rsync.samba.org/documentation.html')] },
    ssh: { t: 'SSH', a: ['SSH'], c: '인프라 · 도구', d: '암호화된 원격 셸입니다. 배포는 GitHub Secrets에 저장한 개인 키로 EC2에 접속해 명령을 실행합니다. 헬스체크도 인스턴스 내부에서 localhost로 수행합니다.', l: [L('OpenSSH', 'https://www.openssh.com/manual.html')] },
    letsencrypt: { t: "Let's Encrypt / certbot", a: ["Let's Encrypt", 'certbot', 'Certbot'], c: '인프라 · TLS', d: '무료 TLS 인증서 발급 기관과 그 자동화 도구입니다. <b>docker-compose.ssl.yml</b> 오버레이가 80 포트로 ACME 검증을 받고 443으로 서비스하며, 인증서 갱신용 webroot를 볼륨으로 공유합니다.', l: [L('certbot', 'https://certbot.eff.org/')] },
    https: { t: 'HTTPS / TLS', a: ['HTTPS', 'TLS'], c: '네트워크 · 보안', d: 'HTTP를 TLS로 암호화한 것입니다. API Gateway URL은 기본 HTTPS이고, EC2 서비스는 nginx + Let\'s Encrypt로 HTTPS를 제공합니다. Bearer 토큰·비밀번호는 HTTPS에서만 전송합니다.', l: [L('MDN: HTTPS', 'https://developer.mozilla.org/docs/Glossary/HTTPS')] },
    cors: { t: 'CORS', a: ['CORS'], c: '네트워크 · 보안', d: 'Cross-Origin Resource Sharing. 브라우저가 다른 출처(도메인·포트)의 API를 부를 때 서버가 <b>Access-Control-Allow-Origin</b> 등으로 허용해야 하는 규칙입니다. 공개 OHLCV API는 허용 출처를 명시하고, 회원 API는 최소 출처만 허용합니다.', l: [L('MDN: CORS', 'https://developer.mozilla.org/docs/Web/HTTP/CORS')] },
    rest: { t: 'REST', a: ['REST'], c: 'API 설계', d: 'HTTP 메서드(GET/POST/PUT/DELETE)와 경로(자원)로 API를 표현하는 설계 방식입니다. 이 프로젝트의 <b>/api/quant/...</b>, Lambda의 <b>/members/{member_id}</b>가 REST 스타일 경로이며, 상태 코드(200/400/401/404/500)로 결과를 구분합니다.', l: [L('MDN: REST', 'https://developer.mozilla.org/docs/Glossary/REST')] },
    openapi: { t: 'Open API / OpenAPI', a: ['Open API', 'OpenAPI', 'Swagger'], c: 'API 설계', d: '<b>Open API</b>는 외부에 공개된 API를 뜻하고, <b>OpenAPI(Swagger)</b>는 API 경로·파라미터·응답을 기술하는 표준 명세 형식입니다. 이 사이트의 OHLCV Open API 문서는 공개 읽기 API의 명세를 보여줍니다.', l: [L('OpenAPI 명세', 'https://spec.openapis.org/oas/latest.html'), L('이 사이트: OHLCV Open API', '/ohlcv-openapi.html')] },
    json: { t: 'JSON', a: ['JSON'], c: '데이터 형식', d: 'JavaScript Object Notation. API 요청·응답, Lambda 이벤트, Secret 값, CloudFormation Outputs 등 거의 모든 곳의 데이터 교환 형식입니다. Python에서는 <b>json.dumps/loads</b>, 셸에서는 <b>python3 -m json.tool</b>로 정리해 봅니다.', l: [L('MDN: JSON', 'https://developer.mozilla.org/docs/Glossary/JSON')] },
    yaml: { t: 'YAML', a: ['YAML'], c: '데이터 형식', d: '들여쓰기로 구조를 표현하는 설정 형식입니다. SAM/CloudFormation 템플릿, docker-compose, GitHub Actions 워크플로가 모두 YAML입니다. 탭 대신 공백을 쓰고, <b>sam validate --lint</b>가 문법과 리소스 규칙을 함께 검사합니다.', l: [L('YAML 스펙', 'https://yaml.org/spec/')] },
    csv: { t: 'CSV', a: ['CSV'], c: '데이터 형식', d: '쉼표로 구분한 표 형식 텍스트입니다. OHLCV 데이터의 내보내기·가져오기, 외부 시세 파일 적재에 쓰입니다. 인코딩(UTF-8)과 날짜 형식을 맞추는 것이 적재 오류의 대부분을 막습니다.', l: [L('RFC 4180', 'https://datatracker.ietf.org/doc/html/rfc4180')] },
    ohlcv: { t: 'OHLCV', a: ['OHLCV'], c: '금융 데이터', d: 'Open·High·Low·Close·Volume. 한 기간(일봉·분봉)의 시가·고가·저가·종가·거래량입니다. 캔들 차트와 대부분의 기술적 지표의 원천 데이터이며, 이 프로젝트는 <b>pg-stock</b> PostgreSQL에 국내주식 일봉을 저장합니다.', l: [L('이 사이트: OHLCV DB', '/ohlcv-db.html')] },
    curl: { t: 'curl', a: ['curl'], c: '도구', d: '터미널에서 HTTP 요청을 보내는 도구입니다. <b>-s</b>(조용히), <b>-o /dev/null -w \'%{http_code}\'</b>(상태 코드만), <b>--fail-with-body</b>(4xx/5xx면 실패 종료 + 본문 출력), <b>-H "Authorization: Bearer …"</b>(헤더)를 자주 씁니다.', l: [L('curl 매뉴얼', 'https://curl.se/docs/manpage.html')] },
    pgdump: { t: 'pg_dump / mysqldump', a: ['pg_dump', 'mysqldump'], c: '데이터베이스 · 백업', d: 'PostgreSQL·MariaDB의 논리 백업 도구입니다. 실행 중인 DB에서 일관된 SQL/아카이브 덤프를 만들며, 복원은 <b>psql</b>/<b>pg_restore</b>, <b>mysql</b>로 합니다. 이 프로젝트는 systemd timer가 컨테이너 안에서 덤프를 떠 보존 일수만큼 유지합니다.', l: [L('pg_dump', 'https://www.postgresql.org/docs/current/app-pgdump.html'), L('이 사이트: DB 백업 정책', '/db-backup-policy.html')] },
    systemd: { t: 'systemd timer', a: ['systemd timer', 'systemd', '타이머'], c: '인프라 · 운영', d: 'Linux systemd의 예약 실행 단위입니다. <b>.service</b>(무엇을 실행)와 <b>.timer</b>(언제)를 짝으로 두며, cron보다 로그(journalctl)와 실패 추적이 쉽습니다. EC2의 DB 백업이 이 방식으로 돌아갑니다.', l: [L('systemd.timer', 'https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html')] },
    aggrid: { t: 'AG Grid', a: ['AG Grid', 'ag-Grid', 'AG-Grid'], c: '프런트엔드', d: '대용량 표를 정렬·필터·가상 스크롤로 보여주는 JavaScript 그리드 라이브러리입니다. OHLCV DB 페이지가 조회 결과를 이 그리드로 렌더링합니다.', l: [L('AG Grid', 'https://www.ag-grid.com/javascript-data-grid/')] },
    mermaid: { t: 'Mermaid', a: ['Mermaid'], c: '프런트엔드', d: '텍스트로 다이어그램(ER·플로차트·시퀀스)을 그리는 라이브러리입니다. DB 스키마 페이지의 ERD가 Mermaid 문법으로 작성되어 브라우저에서 SVG로 렌더링됩니다.', l: [L('Mermaid', 'https://mermaid.js.org/')] },
    tailwind: { t: 'Tailwind CSS', a: ['Tailwind'], c: '프런트엔드', d: '유틸리티 클래스 기반 CSS 프레임워크입니다. 일부 페이지가 CDN 빌드를 불러와 레이아웃에 씁니다.', l: [L('Tailwind CSS', 'https://tailwindcss.com/docs')] },
  };

  const ROOT_SEL = document.currentScript?.dataset.glossaryRoot || 'main';
  const SKIP_SEL = 'pre, code, script, style, textarea, input, select, button, a, svg, .mermaid, .ag-root-wrapper, .tg-term, .tg-modal, [data-no-glossary], h1, .lambda-hero, .lambda-code header, .sam-transcript';
  const SKIP_TAGS = new Set(['PRE', 'CODE', 'SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'BUTTON', 'A', 'SVG', 'H1']);

  // 별칭 → key 매핑, 긴 별칭 우선 정규식
  const aliasMap = new Map();
  Object.entries(GLOSSARY).forEach(([k, g]) => (g.a || [g.t]).forEach(a => aliasMap.set(a, k)));
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const aliases = [...aliasMap.keys()].sort((x, y) => y.length - x.length);
  const RE = new RegExp('(?<![A-Za-z0-9_./:-])(' + aliases.map(esc).join('|') + ')(?![A-Za-z0-9_./:-])', 'g');

  const found = new Set();           // 페이지에서 발견된 key
  const seenPerSection = new WeakMap(); // section → Set(key) : 섹션당 첫 등장만 표시

  function sectionOf(el) {
    return el.closest('section, article, .quant-card, .backup-card, .api-spec-card, .lambda-step-content') || el.closest(ROOT_SEL) || document.body;
  }

  function markTextNode(node) {
    const text = node.nodeValue;
    if (!text || text.length < 2) return;
    RE.lastIndex = 0;
    if (!RE.test(text)) return;
    RE.lastIndex = 0;
    const parent = node.parentElement;
    if (!parent || parent.closest(SKIP_SEL)) return;
    const section = sectionOf(parent);
    let seen = seenPerSection.get(section);
    if (!seen) { seen = new Set(); seenPerSection.set(section, seen); }
    const frag = document.createDocumentFragment();
    let last = 0, m;
    while ((m = RE.exec(text))) {
      const key = aliasMap.get(m[1]);
      found.add(key);
      if (seen.has(key)) continue;          // 이 섹션에서 이미 표시함
      seen.add(key);
      frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'tg-term'; b.dataset.tg = key;
      b.title = GLOSSARY[key].t + ' — 클릭하면 설명';
      b.textContent = m[1];
      frag.appendChild(b);
      last = m.index + m[1].length;
    }
    if (last === 0) return;
    frag.appendChild(document.createTextNode(text.slice(last)));
    parent.replaceChild(frag, node);
  }

  function scan(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        const p = n.parentElement;
        if (!p || SKIP_TAGS.has(p.tagName)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(markTextNode);
    updateIndexButton();
  }

  // ── 모달 ──────────────────────────────────────────
  let modal, lastFocus;
  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'tg-modal'; modal.hidden = true;
    modal.innerHTML = `
      <div class="tg-backdrop" data-tg-close></div>
      <div class="tg-dialog" role="dialog" aria-modal="true" aria-labelledby="tg-title">
        <header><span class="tg-cat" id="tg-cat"></span><h2 id="tg-title"></h2><button type="button" class="tg-close" data-tg-close aria-label="닫기">×</button></header>
        <div class="tg-body" id="tg-body"></div>
        <div class="tg-links" id="tg-links"></div>
        <div class="tg-related" id="tg-related"></div>
      </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target.closest('[data-tg-close]')) close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !modal.hidden) close(); });
    modal.addEventListener('click', e => { const t = e.target.closest('[data-tg-open]'); if (t) open(t.dataset.tgOpen); });
    return modal;
  }
  function open(key) {
    const g = GLOSSARY[key]; if (!g) return;
    ensureModal();
    lastFocus = document.activeElement;
    modal.querySelector('#tg-cat').textContent = g.c;
    modal.querySelector('#tg-title').textContent = g.t;
    modal.querySelector('#tg-body').innerHTML = `<p>${g.d}</p>`;
    modal.querySelector('#tg-links').innerHTML = (g.l || []).map(x => `<a href="${x.url}" ${x.url.startsWith('/') ? '' : 'target="_blank" rel="noopener noreferrer"'}>${x.label}${x.url.startsWith('/') ? '' : ' ↗'}</a>`).join('');
    const related = [...found].filter(k => k !== key).sort((a, b) => GLOSSARY[a].t.localeCompare(GLOSSARY[b].t, 'ko'));
    modal.querySelector('#tg-related').innerHTML = related.length
      ? `<small>이 페이지의 다른 용어</small><div>${related.map(k => `<button type="button" data-tg-open="${k}">${GLOSSARY[k].t}</button>`).join('')}</div>` : '';
    modal.hidden = false;
    document.body.classList.add('tg-open');
    modal.querySelector('.tg-close').focus();
  }
  function close() {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('tg-open');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  // ── 페이지 용어 목록 버튼 ─────────────────────────
  let indexBtn;
  function updateIndexButton() {
    if (!found.size) return;
    if (!indexBtn) {
      indexBtn = document.createElement('button');
      indexBtn.type = 'button'; indexBtn.className = 'tg-index-btn';
      indexBtn.addEventListener('click', () => {
        ensureModal();
        lastFocus = document.activeElement;
        modal.querySelector('#tg-cat').textContent = '이 페이지';
        modal.querySelector('#tg-title').textContent = '기술 용어 사전';
        modal.querySelector('#tg-body').innerHTML = '<p>본문에서 점선 밑줄이 있는 용어를 클릭하면 설명을 볼 수 있습니다. 아래는 이 페이지에 등장하는 용어 전체입니다.</p>';
        modal.querySelector('#tg-links').innerHTML = '';
        const keys = [...found].sort((a, b) => GLOSSARY[a].c.localeCompare(GLOSSARY[b].c, 'ko') || GLOSSARY[a].t.localeCompare(GLOSSARY[b].t, 'ko'));
        const groups = {};
        keys.forEach(k => (groups[GLOSSARY[k].c] ||= []).push(k));
        modal.querySelector('#tg-related').innerHTML = Object.entries(groups).map(([c, ks]) =>
          `<small>${c}</small><div>${ks.map(k => `<button type="button" data-tg-open="${k}">${GLOSSARY[k].t}</button>`).join('')}</div>`).join('');
        modal.hidden = false; document.body.classList.add('tg-open');
        modal.querySelector('.tg-close').focus();
      });
      document.body.appendChild(indexBtn);
    }
    indexBtn.innerHTML = `<i class="fa-solid fa-book" aria-hidden="true"></i> 용어 사전 <b>${found.size}</b>`;
  }

  // ── 시작 + 동적 콘텐츠 감시 ───────────────────────
  function start() {
    const root = document.querySelector(ROOT_SEL) || document.body;
    scan(root);
    document.addEventListener('click', e => {
      const t = e.target.closest('.tg-term'); if (t) { e.preventDefault(); open(t.dataset.tg); }
    });
    let timer;
    new MutationObserver(muts => {
      if (!muts.some(m => m.addedNodes.length)) return;
      clearTimeout(timer); timer = setTimeout(() => scan(root), 250);
    }).observe(root, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();

  window.TechGlossary = { open, close, terms: GLOSSARY };
})();
