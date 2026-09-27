(async () => {
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[char]);
  const columnSpecGroups = window.SCHEMA_COLUMN_SPECS || [];
  const renderColumnSpecTable = specTable => {
    const searchText = [specTable.physical, specTable.logical, specTable.role, specTable.note, ...specTable.columns.flatMap(column => Object.values(column))].join(' ').toLowerCase();
    return `<section class="column-table-spec" data-column-table data-spec-search="${escapeHtml(searchText)}">
      <header><div><code>${escapeHtml(specTable.physical)}</code><h4>${escapeHtml(specTable.logical)}</h4></div><p>${escapeHtml(specTable.role)}</p><span>${specTable.columns.length} columns</span></header>
      ${specTable.note ? `<p class="column-table-note">${escapeHtml(specTable.note)}</p>` : ''}
      <div class="spec-table-wrap"><table class="column-detail-table"><thead><tr><th>논리명</th><th>물리명</th><th>데이터형</th><th>크기</th><th>Key</th><th>NULL</th><th>Default</th><th>설명</th></tr></thead><tbody>${specTable.columns.map(column => `<tr><td>${escapeHtml(column.logical)}</td><td><code>${escapeHtml(column.physical)}</code></td><td><code>${escapeHtml(column.type)}</code></td><td>${escapeHtml(column.size)}</td><td><span class="column-key${column.key === '-' ? ' is-none' : ''}">${escapeHtml(column.key)}</span></td><td><span class="column-null ${column.nullable === 'Y' ? 'allows' : 'required'}">${column.nullable}</span></td><td><code>${escapeHtml(column.defaultValue)}</code></td><td>${escapeHtml(column.description)}</td></tr>`).join('')}</tbody></table></div>
    </section>`;
  };
  const renderColumnSpecs = () => columnSpecGroups.map((group, index) => {
    const fieldCount = group.tables.reduce((total, item) => total + item.columns.length, 0);
    return `<details class="column-db-spec" data-column-db="${escapeHtml(group.key)}" ${index === 0 ? 'open' : ''}><summary><span><b>${escapeHtml(group.label)}</b><small>${escapeHtml(group.dbms)} · ${escapeHtml(group.database)}</small></span><em>${group.tables.length} tables · ${fieldCount} fields</em></summary><div class="column-db-body">${group.tables.map(renderColumnSpecTable).join('')}</div></details>`;
  }).join('');
  const totalTableCount = columnSpecGroups.reduce((total, group) => total + group.tables.length, 0);
  const totalFieldCount = columnSpecGroups.reduce((total, group) => total + group.tables.reduce((sum, item) => sum + item.columns.length, 0), 0);
  const quantErd = `erDiagram
    MARKET_DATA {
      string symbol PK
      datetime trade_time PK
      decimal close
      bigint volume
    }
    MARKET_DATA_2025 {
      string symbol PK
      datetime trade_time PK
    }
    MARKET_DATA_2026 {
      string symbol PK
      datetime trade_time PK
    }
    MARKET_DATA_DEFAULT {
      string symbol PK
      datetime trade_time PK
    }
    STRATEGY {
      bigint strategy_id PK
      string name
      jsonb parameters
    }
    TRADE_LOG {
      bigint trade_id PK
      bigint strategy_id FK
      string side
      decimal pnl
    }
    PERFORMANCE_METRIC {
      bigint strategy_id PK, FK
      date start_date PK
      date end_date PK
      decimal total_return
    }
    FACTOR_RETURN {
      date factor_date PK
      decimal market_excess
    }
    FACTOR_EXPOSURE {
      string symbol PK
      string model PK
      string factor_name PK
      decimal loading
    }
    MARKET_DATA ||--o| MARKET_DATA_2025 : partitions
    MARKET_DATA ||--o| MARKET_DATA_2026 : partitions
    MARKET_DATA ||--o| MARKET_DATA_DEFAULT : partitions
    STRATEGY ||--o{ TRADE_LOG : records
    STRATEGY ||--o{ PERFORMANCE_METRIC : measures
    MARKET_DATA }o..o{ FACTOR_EXPOSURE : input
    FACTOR_RETURN }o..o{ FACTOR_EXPOSURE : input`;
  const stockErd = `erDiagram
    TICKER {
      string ticker_code PK
      string name
      string market
    }
    OHLCV {
      string ticker_code PK, FK
      date trade_date PK
      decimal close
      bigint volume
    }
    SYNC_STATUS {
      string ticker_code PK
      int data_year PK
      string status
    }
    DATA_QUALITY_ISSUE {
      string ticker_code PK
      date trade_date PK
      string reason PK
    }
    DAILY_BATCH_RUN {
      date batch_date PK
      string status
    }
    SUMMARY_SNAPSHOT {
      int snapshot_id PK
      bigint ohlcv_rows
    }
    YEARLY_SUMMARY {
      int data_year PK
      bigint row_count
    }
    MARKET_SUMMARY {
      string market PK
      int ticker_count
    }
    TICKER ||--o{ OHLCV : has
    TICKER ||..o{ SYNC_STATUS : tracks
    TICKER ||..o{ DATA_QUALITY_ISSUE : validates
    DAILY_BATCH_RUN ||..o{ SYNC_STATUS : updates
    OHLCV }o..|| SUMMARY_SNAPSHOT : aggregates
    OHLCV }o..o{ YEARLY_SUMMARY : aggregates
    TICKER }o..o{ MARKET_SUMMARY : aggregates`;
  const serviceErd = `erDiagram
    MEMBER {
      bigint member_id PK
      string email UK
      string username
      decimal asset
    }
    STOCK_POSITION {
      bigint member_id PK, FK
    }
    STOCK_ORDER {
      bigint order_id PK
      bigint member_id FK
    }
    HOLD_CRYPTO {
      bigint member_id PK, FK
      bigint market_id PK, FK
    }
    CRYPTO_ORDER {
      bigint order_id PK
      bigint member_id FK
    }
    UPBIT_MARKET {
      bigint market_id PK
      string market_code UK
    }
    ALTERNATIVE_POSITION {
      bigint member_id PK, FK
    }
    ALTERNATIVE_ORDER {
      bigint order_id PK
      bigint member_id FK
    }
    KIS_PRACTICE_ACCOUNT {
      bigint member_id PK, FK
    }
    HTS_WATCH_MEMO {
      bigint member_id PK, FK
    }
    API_KEY {
      bigint api_key_id PK
      bigint member_id FK
    }
    API_USAGE_LOG {
      bigint usage_id PK
      bigint member_id FK
    }
    SYSTEM_ERROR_LOG {
      bigint error_id PK
      bigint member_id FK
    }
    MEMBER ||--o{ STOCK_POSITION : owns
    MEMBER ||--o{ STOCK_ORDER : places
    MEMBER ||--o{ HOLD_CRYPTO : owns
    MEMBER ||--o{ CRYPTO_ORDER : places
    UPBIT_MARKET ||--o{ HOLD_CRYPTO : identifies
    MEMBER ||--o{ ALTERNATIVE_POSITION : owns
    MEMBER ||--o{ ALTERNATIVE_ORDER : places
    MEMBER ||--o| KIS_PRACTICE_ACCOUNT : practices
    MEMBER ||--o{ HTS_WATCH_MEMO : writes
    MEMBER ||--o{ API_KEY : issues
    MEMBER ||--o{ API_USAGE_LOG : generates
    MEMBER ||--o{ SYSTEM_ERROR_LOG : relates`;
  const vectorErd = `erDiagram
    QDRANT_COLLECTION {
      string name PK
      string embedding_model
      string persistence
    }
    QDRANT_POINT {
      uuid point_id PK
      vector embedding
      string document
      string title
      string category
    }
    REDIS_SESSION {
      string sid PK
      bigint member_id
      boolean permanent
      int ttl_seconds
    }
    QDRANT_COLLECTION ||--o{ QDRANT_POINT : contains`;
  const quantLogicalErd = `erDiagram
    MARKET_DATA["시장 데이터"] {
      string 종목코드 PK
      datetime 거래시각 PK
      decimal 종가
      bigint 거래량
    }
    MARKET_DATA_2025["2025년 시장 데이터 파티션"] {
      string 종목코드 PK
      datetime 거래시각 PK
    }
    MARKET_DATA_2026["2026년 시장 데이터 파티션"] {
      string 종목코드 PK
      datetime 거래시각 PK
    }
    MARKET_DATA_DEFAULT["기본 시장 데이터 파티션"] {
      string 종목코드 PK
      datetime 거래시각 PK
    }
    STRATEGY["전략"] {
      bigint 전략번호 PK
      string 전략명
      jsonb 전략조건
    }
    TRADE_LOG["거래 로그"] {
      bigint 거래번호 PK
      bigint 전략번호 FK
      string 매매구분
      decimal 손익
    }
    PERFORMANCE_METRIC["성과 지표"] {
      bigint 전략번호 PK, FK
      date 시작일 PK
      date 종료일 PK
      decimal 총수익률
    }
    FACTOR_RETURN["팩터 수익률"] {
      date 팩터기준일 PK
      decimal 시장초과수익률
    }
    FACTOR_EXPOSURE["팩터 노출도"] {
      string 종목코드 PK
      string 모델명 PK
      string 팩터명 PK
      decimal 노출계수
    }
    MARKET_DATA ||--o| MARKET_DATA_2025 : 파티션
    MARKET_DATA ||--o| MARKET_DATA_2026 : 파티션
    MARKET_DATA ||--o| MARKET_DATA_DEFAULT : 파티션
    STRATEGY ||--o{ TRADE_LOG : 기록
    STRATEGY ||--o{ PERFORMANCE_METRIC : 측정
    MARKET_DATA }o..o{ FACTOR_EXPOSURE : 분석입력
    FACTOR_RETURN }o..o{ FACTOR_EXPOSURE : 분석입력`;
  const stockLogicalErd = `erDiagram
    TICKER["종목"] {
      string 종목코드 PK
      string 종목명
      string 시장구분
    }
    OHLCV["일별 시세"] {
      string 종목코드 PK, FK
      date 거래일 PK
      decimal 종가
      bigint 거래량
    }
    SYNC_STATUS["수집 상태"] {
      string 종목코드 PK
      int 데이터연도 PK
      string 처리상태
    }
    DATA_QUALITY_ISSUE["데이터 품질 이슈"] {
      string 종목코드 PK
      date 거래일 PK
      string 이슈사유 PK
    }
    DAILY_BATCH_RUN["일일 배치 실행"] {
      date 배치일자 PK
      string 처리상태
    }
    SUMMARY_SNAPSHOT["전체 요약 스냅샷"] {
      int 스냅샷번호 PK
      bigint 시세건수
    }
    YEARLY_SUMMARY["연도별 요약"] {
      int 데이터연도 PK
      bigint 행건수
    }
    MARKET_SUMMARY["시장별 요약"] {
      string 시장구분 PK
      int 종목수
    }
    TICKER ||--o{ OHLCV : 보유
    TICKER ||..o{ SYNC_STATUS : 추적
    TICKER ||..o{ DATA_QUALITY_ISSUE : 검증
    DAILY_BATCH_RUN ||..o{ SYNC_STATUS : 갱신
    OHLCV }o..|| SUMMARY_SNAPSHOT : 집계
    OHLCV }o..o{ YEARLY_SUMMARY : 집계
    TICKER }o..o{ MARKET_SUMMARY : 집계`;
  const serviceLogicalErd = `erDiagram
    MEMBER["회원"] {
      bigint 회원번호 PK
      string 이메일 UK
      string 사용자명
      decimal 자산
    }
    STOCK_POSITION["주식 포지션"] {
      bigint 회원번호 PK, FK
    }
    STOCK_ORDER["주식 주문"] {
      bigint 주문번호 PK
      bigint 회원번호 FK
    }
    HOLD_CRYPTO["보유 암호화폐"] {
      bigint 회원번호 PK, FK
      bigint 마켓번호 PK, FK
    }
    CRYPTO_ORDER["암호화폐 주문"] {
      bigint 주문번호 PK
      bigint 회원번호 FK
    }
    UPBIT_MARKET["업비트 마켓"] {
      bigint 마켓번호 PK
      string 마켓코드 UK
    }
    ALTERNATIVE_POSITION["대체자산 포지션"] {
      bigint 회원번호 PK, FK
    }
    ALTERNATIVE_ORDER["대체자산 주문"] {
      bigint 주문번호 PK
      bigint 회원번호 FK
    }
    KIS_PRACTICE_ACCOUNT["KIS 연습 계좌"] {
      bigint 회원번호 PK, FK
    }
    HTS_WATCH_MEMO["관심종목 메모"] {
      bigint 회원번호 PK, FK
    }
    API_KEY["API 키"] {
      bigint API키번호 PK
      bigint 회원번호 FK
    }
    API_USAGE_LOG["API 사용 이력"] {
      bigint 사용이력번호 PK
      bigint 회원번호 FK
    }
    SYSTEM_ERROR_LOG["시스템 오류 이력"] {
      bigint 오류번호 PK
      bigint 회원번호 FK
    }
    MEMBER ||--o{ STOCK_POSITION : 보유
    MEMBER ||--o{ STOCK_ORDER : 주문
    MEMBER ||--o{ HOLD_CRYPTO : 보유
    MEMBER ||--o{ CRYPTO_ORDER : 주문
    UPBIT_MARKET ||--o{ HOLD_CRYPTO : 식별
    MEMBER ||--o{ ALTERNATIVE_POSITION : 보유
    MEMBER ||--o{ ALTERNATIVE_ORDER : 주문
    MEMBER ||--o| KIS_PRACTICE_ACCOUNT : 연습
    MEMBER ||--o{ HTS_WATCH_MEMO : 작성
    MEMBER ||--o{ API_KEY : 발급
    MEMBER ||--o{ API_USAGE_LOG : 생성
    MEMBER ||--o{ SYSTEM_ERROR_LOG : 연관`;
  const vectorLogicalErd = `erDiagram
    QDRANT_COLLECTION["Qdrant 컬렉션"] {
      string 컬렉션명 PK
      string 임베딩모델
      string 영속화방식
    }
    QDRANT_POINT["Qdrant 포인트"] {
      uuid 포인트번호 PK
      vector 임베딩벡터
      string 문서본문
      string 문서제목
      string 분류
    }
    REDIS_SESSION["Redis 로그인 세션"] {
      string 세션식별자 PK
      bigint 회원번호
      boolean 영구세션여부
      int 만료초
    }
    QDRANT_COLLECTION ||--o{ QDRANT_POINT : 포함`;
  const erdDefinitions = {
    quant: { physical: quantErd, logical: quantLogicalErd },
    stock: { physical: stockErd, logical: stockLogicalErd },
    service: { physical: serviceErd, logical: serviceLogicalErd },
    knowledge: { physical: vectorErd, logical: vectorLogicalErd },
  };
  const erdCard = (key, title) => `
    <article class="erd-card" data-erd-key="${key}" data-erd-mode="physical" data-erd-title="${title}">
      <div class="erd-card-head">
        <h3>${title}</h3>
        <div class="erd-card-actions">
          <div class="erd-toggle" role="group" aria-label="${title} 보기 방식">
            <button type="button" class="is-active" data-erd-mode="physical" aria-pressed="true">물리 ERD · 영문</button>
            <button type="button" data-erd-mode="logical" aria-pressed="false">논리 ERD · 한글</button>
          </div>
          <button type="button" class="erd-zoom" aria-label="${title} 크게 보기" title="크게 보기">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"></circle><path d="m15.5 15.5 5 5M10.5 7.5v6M7.5 10.5h6"></path></svg>
          </button>
        </div>
      </div>
      <div class="erd-canvas" aria-live="polite"></div>
    </article>`;
  const section = document.getElementById('quant-schema');
  document.getElementById('quant-dataset')?.remove();
  document.getElementById('system-erd')?.remove();
  if (!section) return;
  section.outerHTML = `
    <section id="quant-schema" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><span data-stack-summary hidden></span><header><b>01</b><div><h2>데이터 저장소 카탈로그</h2><p>실행 중인 Docker 구성과 코드 설정을 기준으로 RDB·VectorDB·Redis 상태를 구분합니다.</p></div></header><div class="guide-body"><div class="schema-version"><b>기준일 2026-09-27</b><span>실행 DB introspection + DDL + Docker Compose 기준</span></div><div class="store-catalog">
      <article class="is-active"><span>RDB · 운영 중</span><h3>PostgreSQL 16 · quant_research</h3><p>Quant 전용 OHLCV, 전략, 체결, 성과, 팩터 데이터입니다. <code>postgres-quant-data</code> 볼륨과 <code>QUANT_DATABASE_URL</code>을 사용합니다.</p><small>내부 5432 · 외부 미공개</small></article>
      <article class="is-active"><span>RDB · 외부 네트워크</span><h3>PostgreSQL · pg-stock</h3><p>국내주식 원본 일봉, 수집 상태, 품질 이슈와 집계 스냅샷을 보관하며 Quant 연구 DB와 분리됩니다.</p><small>OHLCV_DATABASE_URL · 12시간 배치</small></article>
      <article class="is-active"><span>RDB · 운영 중</span><h3>MariaDB 11.4 · mockinv</h3><p>회원, 웹 모의주문·포지션, KIS 연습 데이터, API 사용 이력과 오류 로그를 처리합니다.</p><small>local-db 프로필 · 내부 3306</small></article>
      <article class="is-memory"><span>VectorDB · 인메모리</span><h3>Qdrant · market_knowledge</h3><p>투자 지식 문서와 임베딩을 검색합니다. 현재 <code>QDRANT_URL=:memory:</code>이므로 재시작 시 시드로 재구성됩니다.</p><small>paraphrase-multilingual-MiniLM-L12-v2</small></article>
      <article class="is-session"><span>Session Store · 운영 중</span><h3>Redis 7.4 · 로그인 세션</h3><p>Flask-Session이 로그인 사용자의 <code>member_id</code>를 서버 측에 저장합니다. 브라우저에는 서명된 임의 세션 ID만 전달합니다.</p><small>DB 0 · TTL 7일 · AOF 볼륨</small></article>
    </div><div class="stack-flow schema-stack"><span>Browser</span><i>→</i><span>Nginx</span><i>→</i><span>Flask</span><i>→</i><span>Redis Session</span><i>+</i><span>PostgreSQL / MariaDB</span><i>↔</i><span>Qdrant RAG</span></div>
    <section class="external-db-access" aria-labelledby="external-db-title"><header><span>EC2 EXTERNAL TCP</span><h3 id="external-db-title">외부 DB 접속 정보</h3><p>접속 허용 원본은 보안 그룹의 <code>DB_EXTERNAL_ALLOWED_CIDR</code> 한 곳으로 제한합니다. 비밀번호와 API Key는 EC2 <code>.env</code>에서만 확인합니다.</p></header><div>
      <article class="is-ready"><b>MariaDB · 접속 가능</b><code>st.edumgt.co.kr:3306</code><dl><dt>Database</dt><dd><code>MARIADB_DATABASE</code></dd><dt>User</dt><dd><code>MARIADB_USER</code></dd><dt>Password</dt><dd><code>MARIADB_PASSWORD</code></dd></dl></article>
      <article class="is-ready"><b>Quant PostgreSQL · 접속 가능</b><code>st.edumgt.co.kr:5432</code><dl><dt>Database</dt><dd><code>QUANT_DB_NAME</code></dd><dt>User</dt><dd><code>QUANT_DB_USER</code></dd><dt>Password</dt><dd><code>QUANT_DB_PASSWORD</code></dd></dl></article>
      <article><b>OHLCV PostgreSQL · 사용 불가</b><code>OHLCV_EXTERNAL_PORT=55432</code><p><code>OHLCV_EXTERNAL_STATUS=unavailable</code><br>EC2 컨테이너가 준비된 뒤 공개합니다.</p></article>
      <article><b>Redis · 미기동</b><code>REDIS_EXTERNAL_PORT=6379</code><p><code>REDIS_EXTERNAL_STATUS=not_deployed</code><br>인증 구성 전에는 공개하지 않습니다.</p></article>
      <article><b>Qdrant · 인메모리</b><code>QDRANT_EXTERNAL_PORT=6333</code><p><code>QDRANT_EXTERNAL_STATUS=in_memory</code><br>영속 서버와 API Key 구성 후 공개합니다.</p></article>
    </div><footer><b>외부 호스트</b><code>DB_EXTERNAL_HOST=st.edumgt.co.kr</code><b>허용 범위</b><code>DB_EXTERNAL_ALLOWED_CIDR</code></footer></section></div></section>
    <section id="quant-erd-doc" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><header><b>02</b><div><h2>전체 데이터 ERD</h2><p>동일한 구조를 물리 ERD의 영문 명칭과 논리 ERD의 한글 명칭으로 전환해 볼 수 있습니다.</p></div></header><div class="guide-body erd-doc-grid">${erdCard('quant', 'PostgreSQL Quant ERD')}${erdCard('stock', 'PostgreSQL pg-stock ERD')}${erdCard('service', 'MariaDB 서비스 ERD')}${erdCard('knowledge', 'Qdrant · Redis ERD')}</div></section>
    <section id="quant-table-spec" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><header><b>03</b><div><h2>DBMS별 전체 컬럼 명세서</h2><p>논리명과 물리 컬럼, 데이터형·크기·키·NULL·기본값·업무 의미를 테이블 단위로 확인합니다.</p></div></header><div class="guide-body spec-groups">
      <div class="column-spec-toolbar"><label><span>테이블·컬럼 검색</span><input type="search" id="column-spec-search" placeholder="예: member_id, 거래일, nullable"></label><div><b>${totalTableCount}</b> tables <i>·</i> <b>${totalFieldCount}</b> fields</div></div>
      <p id="column-spec-empty" class="column-spec-empty" hidden>검색 조건에 맞는 테이블이나 컬럼이 없습니다.</p>
      ${renderColumnSpecs()}
    </div></section>
    <section id="quant-data-policy" class="quant-card quant-guide-card schema-doc" data-quant-tab="schema"><header><b>04</b><div><h2>데이터 흐름·운영 원칙</h2><p>저장소 간 경계, 영속성, 백업과 민감정보 원칙입니다.</p></div></header><div class="guide-body"><div class="schema-details"><article><h3>Quant 연구 흐름</h3><p><code>market_data</code> 조회 → 전략 계산 → <code>strategies</code> 생성 → 체결·성과 저장 순서입니다. 팩터 분석 결과는 <code>factor_exposures</code>에 기록합니다.</p></article><article><h3>주식 원본 흐름</h3><p><code>pg-stock</code>은 최초 적재 후 12시간마다 증분 upsert하고 같은 배치에서 집계 스냅샷을 갱신합니다. 기본 실행 시각은 06:20·18:20(Asia/Seoul)이며 Quant DB와 자동 복제하거나 FK로 연결하지 않습니다.</p></article><article><h3>인증·AI 흐름</h3><p>로그인 세션은 Redis에 7일 TTL로 저장하고, 회원 원본은 MariaDB에서 조회합니다. 투자 문서는 임베딩해 Qdrant에서 검색하며 민감정보는 payload에 넣지 않습니다.</p></article></div><div class="policy-strip"><span><b>PostgreSQL</b>named volume · pg_dump</span><span><b>MariaDB</b>named volume · mariadb-dump</span><span><b>Qdrant</b>현재 인메모리 · 재시드</span><span><b>Redis</b>AOF · 7일 세션 TTL</span></div><div class="guide-warning"><b>네트워크 원칙</b><span>DB와 Redis 포트를 인터넷에 공개하지 않고 내부 Docker 네트워크 또는 사설 연결만 사용합니다.</span></div></div></section>
    <div id="erd-modal" class="erd-modal" role="dialog" aria-modal="true" aria-labelledby="erd-modal-title" hidden>
      <div class="erd-modal-dialog">
        <header><div><h2 id="erd-modal-title">ERD 크게 보기</h2><span id="erd-modal-mode"></span></div><div class="erd-modal-header-actions"><div class="erd-modal-tools" role="group" aria-label="ERD 확대·축소"><button type="button" data-modal-zoom-out aria-label="축소" title="축소 (-)">−</button><output id="erd-modal-zoom">100%</output><button type="button" data-modal-zoom-in aria-label="확대" title="확대 (+)">+</button><button type="button" data-modal-zoom-fit title="화면 맞춤 (0)">화면 맞춤</button></div><button type="button" class="erd-modal-close" aria-label="ERD 크게 보기 닫기">×</button></div></header>
        <div class="erd-modal-canvas" aria-live="polite"></div>
      </div>
    </div>`;
  const specSearch = document.getElementById('column-spec-search');
  const specEmpty = document.getElementById('column-spec-empty');
  specSearch?.addEventListener('input', () => {
    const query = specSearch.value.trim().toLowerCase();
    let visibleCount = 0;
    document.querySelectorAll('[data-column-db]').forEach(group => {
      let groupVisible = 0;
      group.querySelectorAll('[data-column-table]').forEach(item => {
        const visible = !query || item.dataset.specSearch.includes(query);
        item.hidden = !visible;
        if (visible) groupVisible += 1;
      });
      group.hidden = groupVisible === 0;
      if (query && groupVisible) group.open = true;
      visibleCount += groupVisible;
    });
    specEmpty.hidden = visibleCount !== 0;
  });
  if (window.mermaid) {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base' });
    let renderSequence = 0;
    const renderErd = async (card, mode) => {
      const key = card.dataset.erdKey;
      const definition = erdDefinitions[key]?.[mode];
      if (!definition) return;
      const canvas = card.querySelector('.erd-canvas');
      const buttons = card.querySelectorAll('[data-erd-mode]');
      buttons.forEach(button => {
        const active = button.dataset.erdMode === mode;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
        button.disabled = true;
      });
      card.dataset.erdMode = mode;
      canvas.setAttribute('aria-busy', 'true');
      try {
        const id = `erd-${key}-${mode}-${++renderSequence}`;
        const { svg, bindFunctions } = await window.mermaid.render(id, definition);
        canvas.innerHTML = svg;
        bindFunctions?.(canvas);
      } catch (error) {
        canvas.textContent = 'ERD를 표시하지 못했습니다.';
        console.error(error);
      } finally {
        canvas.setAttribute('aria-busy', 'false');
        buttons.forEach(button => { button.disabled = false; });
      }
    };
    const cards = document.querySelectorAll('#quant-erd-doc [data-erd-key]');
    for (const card of cards) await renderErd(card, 'physical');
    cards.forEach(card => {
      card.querySelectorAll('[data-erd-mode]').forEach(button => {
        button.addEventListener('click', () => renderErd(card, button.dataset.erdMode));
      });
    });
    const modal = document.getElementById('erd-modal');
    const modalCanvas = modal.querySelector('.erd-modal-canvas');
    const modalTitle = document.getElementById('erd-modal-title');
    const modalMode = document.getElementById('erd-modal-mode');
    const modalClose = modal.querySelector('.erd-modal-close');
    const modalZoomOut = modal.querySelector('[data-modal-zoom-out]');
    const modalZoomIn = modal.querySelector('[data-modal-zoom-in]');
    const modalZoomFit = modal.querySelector('[data-modal-zoom-fit]');
    const modalZoomOutput = document.getElementById('erd-modal-zoom');
    let zoomTrigger = null;
    let modalRenderToken = 0;
    let modalZoom = 1;
    const setModalZoom = (nextZoom, center = true) => {
      const stage = modalCanvas.querySelector('.erd-modal-stage');
      if (!stage) return;
      const previousZoom = modalZoom;
      modalZoom = Math.max(1, Math.min(3, Math.round(nextZoom * 4) / 4));
      const centerX = modalCanvas.scrollLeft + modalCanvas.clientWidth / 2;
      const centerY = modalCanvas.scrollTop + modalCanvas.clientHeight / 2;
      stage.style.width = `${modalZoom * 100}%`;
      stage.style.height = `${modalZoom * 100}%`;
      modalZoomOutput.value = `${Math.round(modalZoom * 100)}%`;
      modalZoomOutput.textContent = modalZoomOutput.value;
      modalZoomOut.disabled = modalZoom <= 1;
      modalZoomIn.disabled = modalZoom >= 3;
      requestAnimationFrame(() => {
        if (center && previousZoom) {
          const ratio = modalZoom / previousZoom;
          modalCanvas.scrollLeft = centerX * ratio - modalCanvas.clientWidth / 2;
          modalCanvas.scrollTop = centerY * ratio - modalCanvas.clientHeight / 2;
        } else {
          modalCanvas.scrollLeft = Math.max(0, (modalCanvas.scrollWidth - modalCanvas.clientWidth) / 2);
          modalCanvas.scrollTop = Math.max(0, (modalCanvas.scrollHeight - modalCanvas.clientHeight) / 2);
        }
      });
    };
    const closeModal = () => {
      if (modal.hidden) return;
      modalRenderToken += 1;
      modal.hidden = true;
      modalCanvas.replaceChildren();
      modalZoom = 1;
      modalZoomOutput.value = '100%';
      modalZoomOutput.textContent = '100%';
      document.body.classList.remove('erd-modal-open');
      zoomTrigger?.focus();
      zoomTrigger = null;
    };
    const openModal = async card => {
      const key = card.dataset.erdKey;
      const mode = card.dataset.erdMode;
      const definition = erdDefinitions[key]?.[mode];
      if (!definition) return;
      zoomTrigger = card.querySelector('.erd-zoom');
      modalTitle.textContent = card.dataset.erdTitle;
      modalMode.textContent = mode === 'physical' ? '물리 ERD · 영문' : '논리 ERD · 한글';
      modal.hidden = false;
      document.body.classList.add('erd-modal-open');
      modalClose.focus();
      modalCanvas.setAttribute('aria-busy', 'true');
      modalCanvas.textContent = 'ERD를 확대하는 중입니다…';
      const token = ++modalRenderToken;
      try {
        const id = `erd-modal-${key}-${mode}-${++renderSequence}`;
        const { svg, bindFunctions } = await window.mermaid.render(id, definition);
        if (token !== modalRenderToken) return;
        modalCanvas.innerHTML = `<div class="erd-modal-stage">${svg}</div>`;
        const stage = modalCanvas.querySelector('.erd-modal-stage');
        bindFunctions?.(stage);
        modalZoom = 1;
        setModalZoom(key === 'service' ? 2 : 1.5, false);
      } catch (error) {
        if (token === modalRenderToken) modalCanvas.textContent = '확대 ERD를 표시하지 못했습니다.';
        console.error(error);
      } finally {
        if (token === modalRenderToken) modalCanvas.setAttribute('aria-busy', 'false');
      }
    };
    cards.forEach(card => card.querySelector('.erd-zoom').addEventListener('click', () => openModal(card)));
    modalZoomOut.addEventListener('click', () => setModalZoom(modalZoom - .25));
    modalZoomIn.addEventListener('click', () => setModalZoom(modalZoom + .25));
    modalZoomFit.addEventListener('click', () => setModalZoom(1, false));
    modalCanvas.addEventListener('wheel', event => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      setModalZoom(modalZoom + (event.deltaY < 0 ? .25 : -.25));
    }, { passive: false });
    modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
    document.addEventListener('keydown', event => {
      if (modal.hidden) return;
      if (event.key === 'Escape') closeModal();
      if (event.key === '+' || event.key === '=') { event.preventDefault(); setModalZoom(modalZoom + .25); }
      if (event.key === '-') { event.preventDefault(); setModalZoom(modalZoom - .25); }
      if (event.key === '0') { event.preventDefault(); setModalZoom(1, false); }
      if (event.key === 'Tab') {
        const controls = [modalZoomOut, modalZoomIn, modalZoomFit, modalClose].filter(button => !button.disabled);
        const current = controls.indexOf(document.activeElement);
        const direction = event.shiftKey ? -1 : 1;
        const next = current < 0 ? 0 : (current + direction + controls.length) % controls.length;
        event.preventDefault();
        controls[next].focus();
      }
    });
  }
})();
