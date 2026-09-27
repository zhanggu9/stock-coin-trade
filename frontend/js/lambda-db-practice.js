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
      scriptTarget: 'member', route: '/members/{member_id}', testPath: '/members/1', method: 'GET',
      template: 'working/template/template-member.yaml', lambdaDir: 'working/lambda/member', secretParam: 'DatabaseSecretArn', secretEnv: 'DATABASE_SECRET_ARN', directEnv: 'DATABASE_URL', apiLogicalId: 'PracticeHttpApi',
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
      scriptTarget: 'quant', route: '/quant/prices', testPath: '/quant/prices?symbol=005930&limit=30', method: 'GET',
      template: 'working/template/template-quant.yaml', lambdaDir: 'working/lambda/quant', secretParam: 'QuantSecretArn', secretEnv: 'QUANT_SECRET_ARN', directEnv: 'QUANT_DATABASE_URL',
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
      scriptTarget: 'ohlcv', route: '/ohlcv/summary', testPath: '/ohlcv/summary', method: 'GET',
      template: 'working/template/template-ohlcv.yaml', lambdaDir: 'working/lambda/ohlcv', secretParam: 'OhlcvSecretArn', secretEnv: 'OHLCV_SECRET_ARN', directEnv: 'OHLCV_DATABASE_URL',
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
      scriptTarget: 'session', route: '/internal/session-check', testPath: '/internal/session-check?sid=test-session-id', method: 'GET',
      template: 'working/template/template-session.yaml', lambdaDir: 'working/lambda/session', secretParam: 'RedisSecretArn', secretEnv: 'REDIS_SECRET_ARN', directEnv: 'REDIS_URL',
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
      scriptTarget: 'knowledge', route: '/knowledge/search', testPath: '/knowledge/search', method: 'POST',
      template: 'working/template/template-knowledge.yaml', lambdaDir: 'working/lambda/knowledge', secretParam: 'QdrantSecretArn', secretEnv: 'QDRANT_SECRET_ARN', directEnv: 'QDRANT_URL',
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
  const transcriptBlock = (title, text) => `<section class="lambda-code sam-transcript"><header><span>${escapeHtml(title)}</span></header><pre><code>${escapeHtml(text)}</code></pre></section>`;
  const errorPanel = items => `<aside class="sam-errors"><header><i>!</i> 예상 오류와 해결</header>${items.map(item => `
    <div class="sam-err"><b>${escapeHtml(item.title)}</b><code>${escapeHtml(item.output)}</code><p><span>원인</span>${escapeHtml(item.cause)}</p><p class="fix"><span>해결</span>${escapeHtml(item.fix)}</p></div>`).join('')}</aside>`;
  const stepLayout = (intro, main, transcript, errors) => `${intro}<div class="sam-split"><div class="sam-split-code">${main}${transcript}</div>${errorPanel(errors)}</div>`;
  const sourceLinks = target => target.files.map(file => {
    const backendPath = file.startsWith('database/') ? `https://github.com/edumgt/stock-coin-trade/blob/main/${file}` : `${REPO}${file}`;
    return `<a href="${backendPath}" target="_blank" rel="noopener noreferrer">${escapeHtml(file)}</a>`;
  }).join('');
  const samTemplate = target => `# 저장소 파일: ${target.template}\n# 핵심 발췌이며 JWT/VPC 등 전체 선언은 위 파일에서 확인\nAWSTemplateFormatVersion: '2010-09-09'\nTransform: AWS::Serverless-2016-10-31\nParameters:\n  ${target.secretParam}:\n    Type: String\nResources:\n  DatabasePracticeFunction:\n    Type: AWS::Serverless::Function\n    Properties:\n      Runtime: python3.11\n      Handler: ${target.handler.split(' · ')[0].replace('.py', '')}.lambda_handler\n      CodeUri: ../lambda/${target.scriptTarget}/\n      Timeout: 15\n      MemorySize: 512\n      Policies:\n        - AWSSecretsManagerGetSecretValuePolicy:\n            SecretArn: !Ref ${target.secretParam}\n      Environment:\n        Variables:\n          ${target.secretEnv}: !Ref ${target.secretParam}\n          ${target.directEnv}: "" # sam local의 env 파일만 덮어씀\n      Events:\n        Api:\n          Type: HttpApi\n          Properties:${target.apiLogicalId ? `\n            ApiId: !Ref ${target.apiLogicalId}` : ''}\n            Path: ${target.route}\n            Method: ${target.method}\nOutputs:\n  ApiUrl:\n    Value: !Sub 'https://\${${target.apiLogicalId || 'ServerlessHttpApi'}}.execute-api.\${AWS::Region}.\${AWS::URLSuffix}'`;
  const localCurl = target => target.method === 'POST'
    ? `curl --fail-with-body -X POST http://127.0.0.1:3001${target.testPath} \\\n  -H 'content-type: application/json' \\\n  --data '{"vector":[0.01,0.02,0.03]}'`
    : `curl --fail-with-body "http://127.0.0.1:3001${target.testPath}"`;

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
    const intro = text => `<div class="lambda-explain">${text}</div>`;
    if (index === 0) return stepLayout(
      intro(`<b>목표:</b> 현재 Python 파일에서 DB 연결과 Flask 의존 경계를 찾습니다. 선택한 실습 구현은 <code>${escapeHtml(target.lambdaDir)}</code>에 있습니다.`),
      `${codeBlock('현재 소스 패턴', target.source)}${codeBlock('저장소에서 확인할 명령', `rg -n "create_engine|Redis.from_url|QdrantClient|session_scope" python-stock-backend\nfind ${target.lambdaDir} -maxdepth 1 -type f -print\nsed -n '1,220p' ${target.template}`)}`,
      transcriptBlock('실행 결과 예시', `$ find ${target.lambdaDir} -maxdepth 1 -type f -print\n${target.lambdaDir}/event.json\n${target.lambdaDir}/requirements.txt\n${target.lambdaDir}/${target.handler.split(' · ')[0]}\n\n확인 대상: ${target.files.join(', ')}`),
      [
        { title: '검색 결과가 없음', output: 'rg: no matches found', cause: '저장소 루트가 아닌 디렉터리에서 실행했거나 검색 이름이 다릅니다.', fix: 'repo 루트로 이동한 뒤 위 명령을 실행하고 선택 대상의 파일 목록을 확인합니다.' },
        { title: 'Docker 호스트명을 AWS에서도 사용', output: 'Name or service not known: mariadb', cause: 'Compose 서비스명은 해당 Docker 네트워크 안에서만 해석됩니다.', fix: 'AWS 배포 시 RDS/Aurora·ElastiCache·외부 Qdrant의 실제 엔드포인트로 바꿉니다.' },
      ]
    );
    if (index === 1) return stepLayout(
      intro('<b>핵심:</b> Flask의 <code>request</code>와 <code>jsonify</code>를 서비스 계층에서 제거하고 일반 Python 값만 입출력합니다.'),
      `${codeBlock('분리할 서비스 함수', target.service)}${codeBlock('정적 문법 확인', `python3 -m py_compile ${target.lambdaDir}/*.py`)}`,
      transcriptBlock('성공 시 실행내역', `$ python3 -m py_compile ${target.lambdaDir}/*.py\n# 출력 없음, 종료 코드 0\n\n완료 조건: Flask 앱 생성 없이 서비스 모듈을 import할 수 있음`),
      [
        { title: 'Flask 컨텍스트 오류', output: 'RuntimeError: Working outside of request context', cause: '서비스 함수가 request, session 또는 jsonify를 직접 사용합니다.', fix: '핸들러에서 입력을 꺼내 평범한 str/int/dict로 서비스 함수에 전달합니다.' },
        { title: '모듈 import 실패', output: "ModuleNotFoundError: No module named '...'", cause: '함수 디렉터리에 모듈이 없거나 requirements.txt에 의존성이 빠졌습니다.', fix: '같은 Lambda CodeUri 안에 모듈을 두고 STEP 5에서 컨테이너 빌드합니다.' },
      ]
    );
    if (index === 2) return stepLayout(
      intro(`<b>핸들러:</b> SAM의 Handler는 <code>${escapeHtml(target.handler.replace(' · ', '.'))}</code>입니다. 클라이언트는 warm start에서 재사용하도록 모듈 전역에 둡니다.`),
      codeBlock(target.handler, target.handlerCode),
      transcriptBlock('단일 이벤트 실행 명령', `$ ./working/scripts/sam-build.sh ${target.scriptTarget}\n$ ./working/scripts/sam-local-invoke.sh ${target.scriptTarget}\n\n호출 이벤트: ${target.lambdaDir}/event.json\n함수 논리 ID: DatabasePracticeFunction`),
      [
        { title: 'Handler를 찾지 못함', output: 'Runtime.ImportModuleError: Unable to import module', cause: '템플릿 Handler의 파일명/함수명과 실제 코드가 다릅니다.', fix: `${target.template}의 Handler와 ${target.lambdaDir} 파일을 함께 확인합니다.` },
        { title: '환경변수 없음', output: `KeyError: '${target.directEnv}'`, cause: 'local-env.json에 직접 접속 URL이 없고 Secret ARN도 유효하지 않습니다.', fix: '로컬은 working/env/local-env.json을 채우고 AWS는 Secrets Manager ARN을 파라미터로 전달합니다.' },
      ]
    );
    if (index === 3) return stepLayout(
      intro(`<b>API 계약:</b> 실제 템플릿은 <code>${target.method} ${escapeHtml(target.route)}</code>를 선언합니다. 입력 위치와 실패 상태 코드를 먼저 고정합니다.`),
      `${codeBlock(`${target.lambdaDir}/event.json`, target.event)}${codeBlock('템플릿에서 확인할 항목', `Events:\n  Api:\n    Type: HttpApi\n    Properties:\n      Path: ${target.route}\n      Method: ${target.method}`)}`,
      transcriptBlock('검증 명령과 기대 결과', `$ sam validate --lint --template-file ${target.template}\n${target.template} is a valid SAM Template\n\npathParameters → 경로 값\nqueryStringParameters → 쿼리 값\nbody → JSON 문자열`),
      [
        { title: '로컬 API 404', output: '404 Not Found', cause: 'curl 경로 또는 HTTP 메서드가 템플릿 Events와 다릅니다.', fix: `${target.method} ${target.route} 계약과 testPath를 맞춥니다.` },
        { title: 'API Gateway 502', output: 'Malformed Lambda proxy response', cause: 'statusCode가 숫자가 아니거나 body가 문자열이 아닙니다.', fix: '응답을 statusCode, headers, JSON 문자열 body 구조로 반환합니다.' },
      ]
    );
    if (index === 4) return stepLayout(
      intro('<b>컨테이너 빌드:</b> 이 저장소의 스크립트는 템플릿 검증 후 Lambda와 같은 Linux 빌드 이미지를 사용합니다. 산출물은 타깃별 <code>working/.aws-sam</code> 아래에 생깁니다.'),
      `${codeBlock(`${target.lambdaDir}/requirements.txt`, target.requirements)}${codeBlock('repo 루트에서 실행', `./working/scripts/preflight-check.sh\n./working/scripts/sam-build.sh ${target.scriptTarget}\n\n# 결과\nworking/.aws-sam/${target.scriptTarget}/template.yaml`)}`,
      transcriptBlock('이 저장소에서 확인한 실행내역', `$ ./working/scripts/preflight-check.sh\nSAM CLI, version 1.162.1\nDocker version 29.4.3\ndocker : daemon ready\n\n$ ./working/scripts/sam-build.sh ${target.scriptTarget}\nBuild Succeeded\nBuilt template: .../working/.aws-sam/${target.scriptTarget}/template.yaml`),
      [
        { title: 'Docker daemon 연결 실패', output: 'Error: Building functions requires Docker', cause: 'Docker 미설치 또는 daemon이 꺼져 있습니다.', fix: 'preflight-check.sh에서 docker : daemon ready를 먼저 확인합니다.' },
        { title: '빌드 이미지가 docker images에 안 보임', output: 'docker images | grep sam  # 결과 없음', cause: 'SAM/BuildKit 캐시는 중간 빌드 캐시로 관리되어 일반 이미지 목록에 항상 남지 않을 수 있습니다.', fix: 'docker image ls -a와 docker buildx du를 확인하고, 실제 산출물은 working/.aws-sam/<target>에서 확인합니다.' },
        { title: '네이티브 패키지 빌드 실패', output: 'Failed building wheel for psycopg', cause: '호스트 OS에서 빌드했거나 패키지 버전/아키텍처가 맞지 않습니다.', fix: '반드시 sam-build.sh의 --use-container 경로를 사용합니다.' },
      ]
    );
    if (index === 5) return stepLayout(
      intro(`<b>SAM 연결:</b> ${escapeHtml(target.network)}. 로컬 URL은 env 파일로, AWS 비밀값은 Secrets Manager로 분리합니다.`),
      codeBlock(`${target.template} · 핵심 발췌`, samTemplate(target)),
      transcriptBlock('AWS 배포 전 확인', `$ sam validate --lint --template-file ${target.template}\n$ aws secretsmanager describe-secret --secret-id <SECRET_ARN>\n$ aws ec2 describe-subnets --subnet-ids <PRIVATE_SUBNET_IDS>\n$ aws ec2 describe-security-groups --group-ids <LAMBDA_SG_ID>\n\n주의: 실제 ARN, 비밀번호, API key는 HTML이나 Git에 기록하지 않습니다.`),
      [
        { title: 'Secret 권한 거부', output: 'AccessDeniedException: secretsmanager:GetSecretValue', cause: 'Lambda 실행 역할 정책 또는 Secret 리소스 ARN이 다릅니다.', fix: `실행 역할에 ${target.secretParam}의 ARN만 읽도록 권한을 부여합니다.` },
        { title: 'DB 연결 시간 초과', output: 'OperationalError: connection timed out', cause: 'private subnet 라우팅, Lambda SG, DB SG 또는 포트 허용이 맞지 않습니다.', fix: 'DB SG inbound의 source를 Lambda SG로 지정하고 subnet/route/NAT 요구를 점검합니다.' },
      ]
    );
    if (index === 6) return stepLayout(
      intro('<b>로컬 HTTP 검증:</b> 터미널 1에서 API를 실행하고 터미널 2에서 실제 경로를 호출합니다. <code>local-env.json</code>의 예시 비밀번호는 실제 값으로 교체해야 합니다.'),
      `${codeBlock('터미널 1 · 서버 시작', `./working/scripts/sam-build.sh ${target.scriptTarget}\n./working/scripts/sam-local-start-api.sh ${target.scriptTarget} 3001`)}${codeBlock('터미널 2 · HTTP 호출', localCurl(target))}`,
      transcriptBlock(target.scriptTarget === 'member' ? 'MariaDB member 실측 실행내역' : '정상 실행 시 출력 예시', target.scriptTarget === 'member'
        ? `$ curl -i http://127.0.0.1:3013/members/1\nHTTP/1.1 200 OK\n{"member_id":1,"username":"이코인","email":"jj@jj.com","asset":98190003}\n\n$ curl -i http://127.0.0.1:3013/members/not-a-number\nHTTP/1.1 400 BAD REQUEST`
        : `$ ${localCurl(target)}\nHTTP 200\ncontent-type: application/json\n{ ... 선택한 저장소의 조회 결과 ... }`),
      [
        { title: 'Docker network 없음', output: 'Docker network not found: stock-coin-trade_internal', cause: '대상 DB Compose가 실행되지 않았거나 OHLCV용 네트워크가 없습니다.', fix: 'DB 컨테이너를 먼저 실행하거나 SAM_DOCKER_NETWORK를 올바른 네트워크로 지정합니다.' },
        { title: '로컬 JWT 경고', output: "Authorizer 'PracticeJwtAuthorizer' ... was not found, skipping", cause: 'SAM local start-api가 일부 JWT authorizer 검증을 로컬에서 수행하지 않습니다.', fix: '로컬에서는 handler/API 계약을 확인하고 JWT 401/403은 배포된 API Gateway에서 별도로 검증합니다.' },
        { title: 'DB 인증 실패', output: 'Access denied / password authentication failed', cause: 'working/env/local-env.json이 예시 자격 증명 상태입니다.', fix: 'Git에 커밋하지 않는 로컬 값으로 교체하고 URL 인코딩도 확인합니다.' },
      ]
    );
    return stepLayout(
      intro('<b>AWS 배포:</b> guided 배포에서 Secret ARN, VPC, JWT 값을 입력하고 CloudFormation Output의 API URL과 CloudWatch 로그까지 확인합니다. 이 단계는 유효한 AWS 자격 증명과 실제 인프라가 필요합니다.'),
      `${codeBlock('빌드와 guided 배포', `aws sts get-caller-identity\n./working/scripts/sam-deploy.sh ${target.scriptTarget}\n\n# 생성 스택\nstock-coin-trade-${target.scriptTarget}-practice`)}${codeBlock('Output·호출·로그', `API_URL="$(aws cloudformation describe-stacks \\\n  --stack-name stock-coin-trade-${target.scriptTarget}-practice \\\n  --query 'Stacks[0].Outputs[?OutputKey==\x60ApiUrl\x60].OutputValue' \\\n  --output text)"\n\n# JWT 보호 API는 Authorization 헤더 추가\ncurl --fail-with-body "$API_URL${target.testPath}"\nsam logs --stack-name stock-coin-trade-${target.scriptTarget}-practice \\\n  --name DatabasePracticeFunction --tail`)}`,
      transcriptBlock('정상 배포 시 확인할 실행내역', `CloudFormation stack changeset\nCREATE_COMPLETE  AWS::Lambda::Function\nCREATE_COMPLETE  AWS::ApiGatewayV2::Api\nCREATE_COMPLETE  AWS::CloudFormation::Stack\n\nOutputs\nApiUrl  https://<api-id>.execute-api.<region>.amazonaws.com\n\n※ 이 저장소에서는 로컬 빌드·member DB/API 호출까지 실측했습니다. AWS 배포 완료로 오해하지 않도록 클라우드 결과는 기대 형태로 표시합니다.`),
      [
        { title: 'AWS 자격 증명 오류', output: 'Unable to locate credentials / InvalidClientTokenId', cause: '선택 profile의 access key 또는 세션 토큰이 없거나 만료됐습니다.', fix: 'aws sts get-caller-identity가 성공하는 profile/region으로 다시 실행합니다.' },
        { title: 'CloudFormation 롤백', output: 'ROLLBACK_COMPLETE', cause: '필수 파라미터, IAM 권한, subnet/SG 또는 Secret ARN이 유효하지 않습니다.', fix: 'Events와 describe-stack-events를 확인하고 원인을 수정한 뒤 실패 스택을 정리하여 재배포합니다.' },
        { title: 'API 401/403 또는 5xx', output: '401 Unauthorized / 503 Service Unavailable', cause: 'JWT issuer/audience 또는 Lambda→DB 네트워크/Secret이 맞지 않습니다.', fix: '401/403은 authorizer 설정을, 5xx는 sam logs와 Lambda timeout/VPC/DB 로그를 순서대로 확인합니다.' },
      ]
    );
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
