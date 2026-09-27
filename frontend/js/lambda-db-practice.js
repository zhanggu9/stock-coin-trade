(() => {
  const REPO = 'https://github.com/edumgt/stock-coin-trade/blob/main/python-stock-backend/';
  const STORAGE_KEY = 'lambda-db-practice-v1';
  const steps = [
    ['Python 소스 찾기', '스키마와 현재 DB Python 파일의 연결을 확인합니다.'],
    ['서비스 함수 분리', 'Flask 요청 객체와 DB 작업을 분리합니다.'],
    ['Lambda 핸들러', 'event와 context를 받는 Lambda 진입점을 만듭니다.'],
    ['API 경로·이벤트', 'API Gateway의 경로·메서드와 입력 위치를 정합니다.'],
    ['의존성·빌드', '함수 패키지를 최소화하고 SAM으로 빌드합니다.'],
    ['환경·VPC·SAM', '비밀값, 네트워크와 HttpApi 이벤트를 선언합니다.'],
    ['로컬 HTTP 검증', 'SAM local start-api로 실제 경로를 호출합니다.'],
    ['배포·API 운영', 'API URL, 로그, 인증과 DB 연결을 점검합니다.'],
  ];

  const targets = {
    mariadb: {
      short: 'MariaDB', title: 'MariaDB 서비스 DB', role: '회원·포지션·모의주문·감사 로그',
      files: ['db.py', 'members.py', 'models.py'], handler: 'lambda_member.py · lambda_handler',
      trigger: 'API Gateway HTTP API', env: 'DATABASE_URL · MEMBER_SECRET_ARN', color: '#0d6a9e',
      warning: 'Compose의 mariadb 호스트명은 Lambda에서 해석되지 않습니다. AWS에서 접근 가능한 RDS/Aurora 엔드포인트와 private subnet 연결이 필요합니다.',
      requirements: 'SQLAlchemy==2.0.35\nPyMySQL==1.1.1',
      source: `# members.py의 현재 패턴\nwith session_scope() as db:\n    member = db.query(Member).filter(Member.email == email).first()\n    return jsonify({"username": member.username})`,
      service: `# member_service.py\nfrom sqlalchemy import text\n\ndef get_member(engine, member_id: int) -> dict | None:\n    sql = text("""\n        SELECT member_id, username, email, asset\n        FROM member WHERE member_id=:member_id\n    """)\n    with engine.connect() as conn:\n        row = conn.execute(sql, {"member_id": member_id}).mappings().first()\n    return dict(row) if row else None`,
      handlerCode: `import json\nimport os\nfrom sqlalchemy import create_engine\nfrom member_service import get_member\n\nengine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)\n\ndef response(status, body):\n    return {"statusCode": status, "headers": {"content-type": "application/json"},\n            "body": json.dumps(body, ensure_ascii=False, default=str)}\n\ndef lambda_handler(event, context):\n    raw_id = (event.get("pathParameters") or {}).get("member_id", "")\n    if not raw_id.isdigit():\n        return response(400, {"message": "member_id가 필요합니다."})\n    member = get_member(engine, int(raw_id))\n    return response(200, member) if member else response(404, {"message": "회원 없음"})`,
      event: `{"requestContext":{"http":{"method":"GET"}},"pathParameters":{"member_id":"1"}}`,
      network: 'Lambda private subnet → RDS/Aurora MariaDB 또는 RDS Proxy · DB SG는 Lambda SG의 3306만 허용',
    },
    quant: {
      short: 'Quant PG', title: 'PostgreSQL Quant DB', role: 'OHLCV·전략·체결·성과·팩터',
      files: ['quant.py', 'database/quant-postgres.sql'], handler: 'lambda_quant.py · lambda_handler',
      trigger: 'API Gateway HTTP API', env: 'QUANT_DATABASE_URL', color: '#3157a4',
      warning: 'quant.py 전체를 복사하지 말고 조회·계산 함수를 나눕니다. Lambda 호출마다 SQLAlchemy engine을 만들지 말고 모듈 전역에서 재사용합니다.',
      requirements: 'SQLAlchemy==2.0.35\npsycopg[binary]==3.2.3',
      source: `# quant.py의 현재 패턴\n@quant_bp.get("/market-data")\ndef market_data():\n    symbol = request.args.get("symbol", "005930")\n    with _db().connect() as conn:\n        rows = conn.execute(text(SQL), {"symbol": symbol})`,
      service: `# quant_service.py\nfrom sqlalchemy import text\n\nSQL = text("""\n  SELECT symbol, trade_time, close, volume\n  FROM market_data WHERE symbol=:symbol\n  ORDER BY trade_time DESC LIMIT :limit\n""")\n\ndef recent_prices(engine, symbol: str, limit: int) -> list[dict]:\n    with engine.connect() as conn:\n        rows = conn.execute(SQL, {"symbol": symbol, "limit": limit})\n        return [dict(row) for row in rows.mappings()]`,
      handlerCode: `import json\nimport os\nfrom sqlalchemy import create_engine\nfrom quant_service import recent_prices\n\nengine = create_engine(os.environ["QUANT_DATABASE_URL"], pool_pre_ping=True)\n\ndef lambda_handler(event, context):\n    query = event.get("queryStringParameters") or {}\n    symbol = query.get("symbol", "005930").strip().upper()[:20]\n    limit = max(1, min(int(query.get("limit", 30)), 100))\n    rows = recent_prices(engine, symbol, limit)\n    return {"statusCode": 200, "headers": {"content-type": "application/json"},\n            "body": json.dumps({"rows": rows}, ensure_ascii=False, default=str)}`,
      event: `{"queryStringParameters":{"symbol":"005930","limit":"30"}}`,
      network: 'Lambda private subnet → PostgreSQL/RDS Proxy · DB SG는 Lambda SG의 5432만 허용',
    },
    stock: {
      short: 'pg-stock', title: 'PostgreSQL pg-stock', role: '국내주식 일봉·품질·수집 상태·집계',
      files: ['ohlcv_db.py', 'ohlcv_sync.py', 'ohlcv_aggregate.py'], handler: 'lambda_ohlcv_summary.py · lambda_handler',
      trigger: 'API Gateway 또는 EventBridge', env: 'OHLCV_DATABASE_URL', color: '#146f79',
      warning: 'pg-stock은 현재 외부 Docker 네트워크의 DB입니다. Lambda에서는 Docker DNS 이름 pg-stock 대신 VPC에서 도달 가능한 DB 엔드포인트가 필요합니다.',
      requirements: 'SQLAlchemy==2.0.35\npsycopg[binary]==3.2.3',
      source: `# ohlcv_db.py의 현재 패턴\n@ohlcv_db_bp.get("/summary")\ndef summary():\n    with _db().connect() as conn:\n        totals = conn.execute(text("""\n          SELECT * FROM ohlcv_summary_snapshot WHERE snapshot_id=1\n        """))`,
      service: `# ohlcv_service.py\nfrom sqlalchemy import text\n\nSUMMARY_SQL = text("""\n  SELECT ohlcv_rows, ticker_count, first_date, last_date, refreshed_at\n  FROM ohlcv_summary_snapshot WHERE snapshot_id=1\n""")\n\ndef load_summary(engine) -> dict:\n    with engine.connect() as conn:\n        row = conn.execute(SUMMARY_SQL).mappings().one()\n    return dict(row)`,
      handlerCode: `import json\nimport os\nfrom sqlalchemy import create_engine\nfrom ohlcv_service import load_summary\n\nengine = create_engine(os.environ["OHLCV_DATABASE_URL"], pool_pre_ping=True)\n\ndef lambda_handler(event, context):\n    summary = load_summary(engine)\n    return {"statusCode": 200, "headers": {"content-type": "application/json"},\n            "body": json.dumps(summary, ensure_ascii=False, default=str)}`,
      event: `{"requestContext":{"http":{"method":"GET","path":"/ohlcv/summary"}}}`,
      network: 'Lambda private subnet → pg-stock PostgreSQL · 배치 전환 시 EventBridge Scheduler와 중복 실행 방지 키 유지',
    },
    redis: {
      short: 'Redis', title: 'Redis 로그인 세션', role: 'Flask 로그인 서버 세션·7일 TTL',
      files: ['app.py', 'members.py'], handler: 'lambda_session_check.py · lambda_handler',
      trigger: 'API Gateway 내부 진단 API', env: 'REDIS_URL · REDIS_SESSION_KEY_PREFIX', color: '#a23636',
      warning: 'Flask-Session 쿠키 서명과 SID 교체 규칙을 그대로 유지해야 합니다. 첫 연습에서는 로그인 재작성보다 Redis 연결·TTL 확인용 읽기 함수를 Lambda로 분리하세요.',
      requirements: 'redis==5.2.1',
      source: `# app.py의 현재 세션 구성\napp.config["SESSION_TYPE"] = "redis"\napp.config["SESSION_REDIS"] = Redis.from_url(os.environ["REDIS_URL"])\napp.config["SESSION_KEY_PREFIX"] = "stock-coin-trade:session:"`,
      service: `# session_service.py\ndef session_ttl(client, prefix: str, sid: str) -> int:\n    if not sid or len(sid) > 256:\n        raise ValueError("올바르지 않은 SID")\n    return client.ttl(f"{prefix}{sid}")`,
      handlerCode: `import json\nimport os\nfrom redis import Redis\nfrom session_service import session_ttl\n\nclient = Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3)\nprefix = os.environ.get("REDIS_SESSION_KEY_PREFIX", "stock-coin-trade:session:")\n\ndef lambda_handler(event, context):\n    sid = (event.get("queryStringParameters") or {}).get("sid", "")\n    try:\n        ttl = session_ttl(client, prefix, sid)\n    except ValueError as exc:\n        return {"statusCode": 400, "body": json.dumps({"message": str(exc)})}\n    return {"statusCode": 200, "body": json.dumps({"exists": ttl >= 0, "ttl": ttl})}`,
      event: `{"queryStringParameters":{"sid":"signed-session-id-from-authorized-test"}}`,
      network: 'Lambda private subnet → ElastiCache/MemoryDB Redis · Redis SG는 Lambda SG의 6379만 허용',
    },
    qdrant: {
      short: 'Qdrant', title: 'Qdrant 지식 DB', role: '투자 문서·임베딩·유사도 검색',
      files: ['qdrant_service.py', 'ai.py'], handler: 'lambda_knowledge_search.py · lambda_handler',
      trigger: 'API Gateway HTTP API', env: 'QDRANT_URL · QDRANT_API_KEY', color: '#7157a6',
      warning: '현재 QDRANT_URL=:memory: 모드는 Lambda 인스턴스마다 데이터가 달라집니다. Lambda 전환 전에 영속 Qdrant 서비스와 인증 URL을 준비해야 합니다.',
      requirements: 'qdrant-client==1.17.1',
      source: `# qdrant_service.py의 현재 패턴\nQDRANT_URL = os.getenv("QDRANT_URL", ":memory:")\nCOLLECTION = "market_knowledge"\n\ndef get_client():\n    return QdrantClient(QDRANT_URL)`,
      service: `# knowledge_service.py\ndef search_knowledge(client, collection: str, vector, limit: int):\n    result = client.query_points(\n        collection_name=collection, query=vector, limit=limit, with_payload=True\n    )\n    return [{"score": point.score, "payload": point.payload}\n            for point in result.points]`,
      handlerCode: `import json\nimport os\nfrom qdrant_client import QdrantClient\n\nclient = QdrantClient(url=os.environ["QDRANT_URL"],\n                      api_key=os.environ.get("QDRANT_API_KEY"))\ncollection = os.environ.get("QDRANT_COLLECTION", "market_knowledge")\n\ndef lambda_handler(event, context):\n    body = json.loads(event.get("body") or "{}")\n    vector = body.get("vector")\n    if not isinstance(vector, list):\n        return {"statusCode": 400, "body": json.dumps({"message": "vector 필요"})}\n    result = client.query_points(collection_name=collection, query=vector, limit=5)\n    rows = [{"score": p.score, "payload": p.payload} for p in result.points]\n    return {"statusCode": 200, "body": json.dumps({"rows": rows}, ensure_ascii=False)}`,
      event: `{"body":"{\\"vector\\":[0.01,0.02,0.03]}"}`,
      network: '외부 Qdrant면 HTTPS egress 필요 · Lambda를 DB VPC에 넣었다면 private subnet의 NAT 또는 적절한 VPC 연결 확인',
    },
  };

  let saved;
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch { saved = {}; }
  const state = {
    target: saved.target && targets[saved.target] ? saved.target : 'mariadb',
    step: Number.isInteger(saved.step) ? Math.max(0, Math.min(saved.step, steps.length - 1)) : 0,
    completed: saved.completed || {},
  };
  let toastTimer;

  const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[char]);
  const save = () => localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  const doneSet = () => new Set(state.completed[state.target] || []);
  const toast = message => {
    const node = document.getElementById('lambda-toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove('show'), 1600);
  };
  const bindCopyButtons = (root = document) => {
    root.querySelectorAll('[data-copy-code]:not([data-copy-bound])').forEach(button => {
      button.dataset.copyBound = 'true';
      button.addEventListener('click', async () => {
        const text = button.closest('.lambda-code').querySelector('code').textContent;
        try { await navigator.clipboard.writeText(text); } catch {
          const area = document.createElement('textarea'); area.value = text; document.body.appendChild(area); area.select(); document.execCommand('copy'); area.remove();
        }
        toast('코드를 복사했습니다.');
      });
    });
  };
  const codeBlock = (title, code) => `<section class="lambda-code"><header><span>${escapeHtml(title)}</span><button type="button" data-copy-code>복사</button></header><pre><code>${escapeHtml(code)}</code></pre></section>`;
  const sourceLinks = target => target.files.map(file => {
    const backendPath = file.startsWith('database/') ? `https://github.com/edumgt/stock-coin-trade/blob/main/${file}` : `${REPO}${file}`;
    return `<a href="${backendPath}" target="_blank" rel="noopener noreferrer">${escapeHtml(file)}</a>`;
  }).join('');
  const samTemplate = target => `AWSTemplateFormatVersion: '2010-09-09'\nTransform: AWS::Serverless-2016-10-31\nResources:\n  DatabasePracticeFunction:\n    Type: AWS::Serverless::Function\n    Properties:\n      Runtime: python3.11\n      Handler: ${target.handler.split(' · ')[0].replace('.py', '')}.lambda_handler\n      CodeUri: lambda/\n      Timeout: 15\n      MemorySize: 512\n      Environment:\n        Variables:\n          ${target.env.split(' · ')[0]}: REPLACE_WITH_SECRET_OR_ENDPOINT\n      VpcConfig:\n        SecurityGroupIds: [sg-lambda-to-database]\n        SubnetIds: [subnet-private-a, subnet-private-b]\n      Events:\n        PracticeApi:\n          Type: HttpApi\n          Properties:\n            Path: /practice/{proxy+}\n            Method: ANY\nOutputs:\n  ApiUrl:\n    Value: !Sub "https://\${ServerlessHttpApi}.execute-api.\${AWS::Region}.\${AWS::URLSuffix}"`;

  function renderTargetList() {
    document.getElementById('lambda-target-list').innerHTML = Object.entries(targets).map(([key, target]) => `
      <button type="button" class="lambda-target${key === state.target ? ' active' : ''}" data-target="${key}" style="border-top:3px solid ${target.color}">
        <span>${escapeHtml(target.short)}</span><b>${escapeHtml(target.title)}</b><small>${escapeHtml(target.role)}</small>
      </button>`).join('');
    document.querySelectorAll('[data-target]').forEach(button => button.addEventListener('click', () => {
      state.target = button.dataset.target;
      state.step = 0;
      save();
      render();
    }));
  }

  function renderSourceMap() {
    const target = targets[state.target];
    document.getElementById('lambda-db-name').textContent = target.title;
    document.getElementById('lambda-db-role').textContent = target.role;
    document.getElementById('lambda-source-files').innerHTML = sourceLinks(target);
    document.getElementById('lambda-handler-name').textContent = target.handler;
    document.getElementById('lambda-trigger').textContent = target.trigger;
    document.getElementById('lambda-env').textContent = target.env;
    document.getElementById('lambda-target-warning').textContent = target.warning;
  }

  function stepHtml(index, target) {
    if (index === 0) return `
      <div class="lambda-explain"><b>목표:</b> ERD의 저장소가 실제로 어느 Python 모듈에서 연결되고 조회되는지 먼저 찾습니다. Lambda 파일을 만들기 전에 현재 경계를 설명할 수 있어야 합니다.</div>
      <div class="lambda-practice-grid"><article><h3>${escapeHtml(target.title)}</h3><p>${escapeHtml(target.role)}</p><div class="lambda-file-list">${sourceLinks(target)}</div></article><article><h3>확인 질문</h3><ul><li>DB 연결은 import 시점인가, 요청 시점인가?</li><li>Flask의 request·jsonify·session에 의존하는가?</li><li>읽기 함수인가, 재시도에 주의할 쓰기 함수인가?</li></ul></article></div>
      ${codeBlock('현재 소스 패턴', target.source)}`;
    if (index === 1) return `
      <div class="lambda-explain"><b>핵심:</b> Lambda 핸들러 안에 SQL과 업무 규칙을 모두 넣지 않습니다. Flask를 모르는 서비스 함수가 일반 Python 값만 받고 반환하도록 먼저 분리합니다.</div>
      ${codeBlock('분리할 서비스 함수', target.service)}
      <div class="lambda-practice-grid"><article><h3>서비스 함수 규칙</h3><ul><li><code>request</code>, <code>jsonify</code>, <code>session</code> import 금지</li><li>입력 검증 결과를 명시적 인자로 전달</li><li>DB 예외는 핸들러가 변환할 수 있게 유지</li></ul></article><article><h3>완료 조건</h3><p>로컬 Python에서 함수만 import해 테스트할 수 있고 Flask 앱 생성 없이 실행됩니다.</p></article></div>`;
    if (index === 2) return `
      <div class="lambda-explain"><b>핸들러:</b> 파일명과 함수명을 합친 <code>${escapeHtml(target.handler.replace(' · ', '.'))}</code>가 Lambda Handler 설정값입니다. DB 클라이언트는 실행 환경 재사용을 위해 모듈 전역에 둡니다.</div>
      ${codeBlock(target.handler, target.handlerCode)}
      <div class="lambda-practice-grid"><article><h3>핸들러 책임</h3><p>이벤트 파싱, 입력 검증, 서비스 호출, HTTP 응답과 오류 코드 변환만 담당합니다.</p></article><article><h3>남기지 않을 것</h3><p>Flask Blueprint 등록, 개발 서버 실행, 하드코딩된 비밀번호와 Docker 호스트명을 제거합니다.</p></article></div>`;
    if (index === 3) return `
      <div class="lambda-explain"><b>API Gateway:</b> ${escapeHtml(target.trigger)}의 경로·메서드와 이벤트에서 필요한 값의 위치를 먼저 정합니다. 없는 키를 바로 인덱싱하지 말고 <code>or {}</code>와 기본값으로 검증합니다.</div>
      ${codeBlock('events/practice.json', target.event)}
      <div class="lambda-practice-grid"><article><h3>API 이벤트</h3><ul><li>경로 값: <code>pathParameters</code></li><li>쿼리: <code>queryStringParameters</code></li><li>JSON 본문: <code>json.loads(event["body"])</code></li></ul></article><article><h3>비동기 이벤트</h3><p>EventBridge·SQS는 실패 시 재시도될 수 있으므로 쓰기 작업은 중복 실행되어도 안전한 키와 상태 전이를 사용합니다.</p></article></div>`;
    if (index === 4) return `
      <div class="lambda-explain"><b>최소 패키지:</b> 전체 백엔드 requirements를 복사하지 않고 이 함수가 import하는 패키지만 넣습니다. 네이티브 바이너리가 있으면 Lambda와 같은 Linux 환경에서 빌드합니다.</div>
      ${codeBlock('lambda/requirements.txt', target.requirements)}
      <div class="lambda-command-list"><code>sam validate</code><code>sam build --use-container</code></div>
      <div class="lambda-practice-grid"><article><h3>권장 디렉터리</h3><p><code>lambda/handler.py</code>, 서비스 모듈, <code>requirements.txt</code>, 루트 <code>template.yaml</code>로 작게 시작합니다.</p></article><article><h3>Layer 선택</h3><p>여러 함수가 같은 무거운 의존성을 공유할 때만 Layer를 고려하고, 첫 실습은 함수별 패키지가 이해하기 쉽습니다.</p></article></div>`;
    if (index === 5) return `
      <div class="lambda-explain"><b>SAM 연결:</b> ${escapeHtml(target.network)}. URL·비밀번호를 코드나 SAM 템플릿 원문에 커밋하지 않고, <code>Events.HttpApi</code>로 API Gateway 경로를 함께 선언합니다.</div>
      ${codeBlock('template.yaml · Lambda + HttpApi', samTemplate(target))}
      <div class="lambda-practice-grid"><article><h3>비밀값</h3><p>Secrets Manager 또는 배포 환경의 동적 참조를 사용하고 실행 역할에는 필요한 secret 읽기 권한만 부여합니다.</p></article><article><h3>VPC 주의</h3><p>private DB 접근을 위해 VPC에 붙이면 외부 API 접근에는 private subnet의 NAT 또는 적절한 VPC endpoint가 추가로 필요할 수 있습니다.</p></article></div>`;
    if (index === 6) return `
      <div class="lambda-explain"><b>로컬 HTTP 루프:</b> 소스를 바꿀 때마다 다시 빌드하고 <code>start-api</code>를 실행한 뒤 실제 URL로 경로·쿼리·본문을 확인합니다. 실제 비밀번호가 든 env 파일은 Git에 추가하지 않습니다.</div>
      <div class="lambda-command-list"><code>sam validate --lint</code><code>sam build --use-container</code><code>sam local invoke DatabasePracticeFunction --event events/practice.json --env-vars env.local.json</code><code>sam local start-api --port 3001 --env-vars env.local.json</code><code>curl --fail-with-body http://127.0.0.1:3001/practice/1</code></div>
      ${codeBlock('검증할 응답 형태', `{"statusCode":200,"headers":{"content-type":"application/json"},"body":"{...}"}`)}
      <div class="lambda-practice-grid"><article><h3>성공 테스트</h3><p>정상 ID·종목·벡터로 200과 JSON 직렬화를 확인합니다.</p></article><article><h3>실패 테스트</h3><p>누락 입력, 존재하지 않는 데이터, DB timeout을 각각 4xx/5xx로 구분합니다.</p></article></div>`;
    return `
      <div class="lambda-explain"><b>API 배포:</b> guided 배포로 스택·리전·권한을 확인하고 CloudFormation Output에서 API URL을 얻습니다. HTTPS 호출과 Lambda 로그 확인까지가 완료입니다.</div>
      <div class="lambda-command-list"><code>sam deploy --guided</code><code>aws cloudformation describe-stacks --stack-name db-python-practice --query 'Stacks[0].Outputs'</code><code>curl --fail-with-body "$API_URL/practice/1"</code><code>sam logs --name DatabasePracticeFunction --stack-name db-python-practice --tail</code></div>
      <div class="lambda-practice-grid"><article><h3>운영 체크</h3><ul><li>CloudWatch 오류·duration·timeout</li><li>DB 연결 수와 동시성 상한</li><li>재시도·중복 쓰기 여부</li><li>민감값 로그 노출 여부</li></ul></article><article><h3>다음 개선</h3><ul><li>RDS Proxy 또는 연결 제한</li><li>구조화 로그와 X-Ray</li><li>예약 동시성·DLQ</li><li>CI에서 sam build/test</li></ul></article></div>`;
  }

  function renderSteps() {
    const completed = doneSet();
    document.getElementById('lambda-step-list').innerHTML = steps.map(([title], index) => `
      <button type="button" class="${index === state.step ? 'active ' : ''}${completed.has(index) ? 'done' : ''}" data-step="${index}">
        <b>${index + 1}</b><span>${escapeHtml(title)}</span><i>${completed.has(index) ? '✓' : ''}</i>
      </button>`).join('');
    document.querySelectorAll('[data-step]').forEach(button => button.addEventListener('click', () => {
      state.step = Number(button.dataset.step);
      save();
      renderSteps();
      renderStepContent();
    }));
    document.getElementById('lambda-progress-text').textContent = `${completed.size} / ${steps.length}`;
    document.getElementById('lambda-progress-bar').style.width = `${completed.size / steps.length * 100}%`;
  }

  function renderStepContent() {
    const target = targets[state.target];
    const [title, summary] = steps[state.step];
    const completed = doneSet();
    const isDone = completed.has(state.step);
    document.getElementById('lambda-step-kicker').textContent = `STEP ${state.step + 1} · ${target.short}`;
    document.getElementById('lambda-step-title').textContent = title;
    document.getElementById('lambda-step-summary').textContent = summary;
    document.getElementById('lambda-step-content').innerHTML = stepHtml(state.step, target);
    const stateNode = document.getElementById('lambda-step-state');
    stateNode.textContent = isDone ? '완료' : '진행 중';
    stateNode.classList.toggle('done', isDone);
    const complete = document.getElementById('lambda-complete');
    complete.textContent = isDone ? '✓ 완료 취소' : '이 단계 완료';
    complete.classList.toggle('done', isDone);
    document.getElementById('lambda-prev').disabled = state.step === 0;
    document.getElementById('lambda-next').disabled = state.step === steps.length - 1;
    bindCopyButtons(document.getElementById('lambda-step-content'));
  }

  function render() {
    renderTargetList();
    renderSourceMap();
    renderSteps();
    renderStepContent();
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await initPage();
    bindCopyButtons(document);
    document.getElementById('lambda-prev').addEventListener('click', () => { if (state.step > 0) { state.step -= 1; save(); renderSteps(); renderStepContent(); } });
    document.getElementById('lambda-next').addEventListener('click', () => { if (state.step < steps.length - 1) { state.step += 1; save(); renderSteps(); renderStepContent(); } });
    document.getElementById('lambda-complete').addEventListener('click', () => {
      const completed = doneSet();
      if (completed.has(state.step)) completed.delete(state.step); else completed.add(state.step);
      state.completed[state.target] = [...completed].sort((a, b) => a - b);
      save(); renderSteps(); renderStepContent();
    });
    document.getElementById('lambda-reset').addEventListener('click', () => {
      if (!confirm('모든 저장소의 Lambda Practice 진행률을 초기화할까요?')) return;
      state.completed = {}; state.step = 0; save(); render(); toast('진행률을 초기화했습니다.');
    });
    render();
  });
})();
