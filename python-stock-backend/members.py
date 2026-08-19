import bcrypt
import requests
import threading
import time
from flask import Blueprint, jsonify, request, session

from sqlalchemy import text

from db import engine, session_scope
from models import HoldCrypto, HtsWatchMemo, Member, StockPosition, UpbitMarket
from alternatives import get_positions as get_alternative_positions, position_value
from stock_market import cached_price

member_bp = Blueprint("member", __name__, url_prefix="/api/member")
INITIAL_ASSET = 100_000_000
RANKING_CACHE_TTL = 30
_ranking_cache = {"ts": 0.0, "data": None}
_ranking_cache_lock = threading.Lock()
_crypto_price_cache = {"ts": 0.0, "prices": {}}


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


@member_bp.get("/me")
def me():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"loggedIn": False})
    with session_scope() as db:
        member = db.get(Member, member_id)
        if not member:
            return jsonify({"loggedIn": False})
        return jsonify({"loggedIn": True, "username": member.username, "asset": member.asset})


@member_bp.get("/hts-memos")
def get_hts_memos():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401
    with session_scope() as db:
        rows = (db.query(HtsWatchMemo)
                .filter(HtsWatchMemo.member_id == member_id)
                .order_by(HtsWatchMemo.updated_at.desc()).all())
        return jsonify({"memos": [{"symbol": row.symbol, "memo": row.memo,
                                   "updatedAt": row.updated_at.isoformat() if row.updated_at else None}
                                  for row in rows]})


@member_bp.put("/hts-memos/<symbol>")
def save_hts_memo(symbol):
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 20:
        return jsonify({"error": "올바른 종목코드가 아닙니다."}), 400
    memo = str((request.get_json(silent=True) or {}).get("memo", "")).strip()
    if len(memo) > 500:
        return jsonify({"error": "메모는 500자까지 입력할 수 있습니다."}), 400
    with session_scope() as db:
        row = db.query(HtsWatchMemo).filter(
            HtsWatchMemo.member_id == member_id, HtsWatchMemo.symbol == symbol
        ).first()
        if not memo:
            if row:
                db.delete(row)
            return jsonify({"symbol": symbol, "memo": "", "deleted": True})
        if row:
            row.memo = memo
        else:
            row = HtsWatchMemo(member_id=member_id, symbol=symbol, memo=memo)
            db.add(row)
        db.flush()
        return jsonify({"symbol": row.symbol, "memo": row.memo,
                        "updatedAt": row.updated_at.isoformat() if row.updated_at else None})


def ensure_member_tables() -> None:
    """기존 DB에도 배포 시 HTS 개인 메모 기능을 안전하게 추가한다."""
    statement = """CREATE TABLE IF NOT EXISTS hts_watch_memo (
      hts_watch_memo_id BIGINT AUTO_INCREMENT PRIMARY KEY,
      member_id BIGINT NOT NULL,
      symbol VARCHAR(20) NOT NULL,
      memo TEXT NOT NULL,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uq_hts_watch_memo_member_symbol (member_id, symbol),
      CONSTRAINT fk_hts_watch_memo_member FOREIGN KEY (member_id) REFERENCES member(member_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    with engine.begin() as conn:
        conn.execute(text(statement))


@member_bp.get("/portfolio-analysis")
def portfolio_analysis():
    """현재 평가액을 바탕으로 한 교육용 자산배분 요약과 비개인화 조언."""
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}), 401

    with session_scope() as db:
        member = db.get(Member, member_id)
        if not member:
            return jsonify({"error": "UNAUTHORIZED"}), 401
        stock_value = sum(position.quantity * (cached_price(position.symbol) or position.avg_price)
                          for position in db.query(StockPosition).filter(StockPosition.member_id == member_id))
        crypto_rows = db.query(HoldCrypto, UpbitMarket).join(
            UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id
        ).filter(HoldCrypto.member_id == member_id).all()
        codes = sorted({market.market_code for _, market in crypto_rows})
        prices = {}
        if codes:
            try:
                response = requests.get("https://api.upbit.com/v1/ticker", params={"markets": ",".join(codes)}, timeout=1.5)
                response.raise_for_status()
                prices = {row["market"]: float(row["trade_price"]) for row in response.json()}
            except Exception:
                prices = _crypto_price_cache.get("prices", {})
        crypto_value = sum(holding.buy_crypto_count * prices.get(market.market_code, holding.buy_average)
                           for holding, market in crypto_rows)
        alternatives = get_alternative_positions(db, member_id)
        alternative_value = sum(row["evalAmount"] for row in alternatives)
        values = [
            {"name": "현금", "value": round(member.asset), "color": "#64748B"},
            {"name": "주식", "value": round(stock_value), "color": "#2563EB"},
            {"name": "코인", "value": round(crypto_value), "color": "#7C3AED"},
            {"name": "대체자산", "value": round(alternative_value), "color": "#D97706"},
        ]
        total = sum(item["value"] for item in values)
        for item in values:
            item["weight"] = round(item["value"] / total * 100, 1) if total else 0

    weights = {item["name"]: item["weight"] for item in values}
    invested = 100 - weights["현금"]
    advice = []
    if not total or invested == 0:
        advice.append("아직 투자 자산이 없습니다. 상품별 변동성과 주문 단위를 먼저 살펴본 뒤 소액으로 연습해 보세요.")
    else:
        largest = max(values, key=lambda item: item["weight"])
        if largest["weight"] >= 65:
            advice.append(f"{largest['name']} 비중이 {largest['weight']}%로 높습니다. 자산군을 나누면 한 시장의 변동 영향이 줄어들 수 있습니다.")
        if weights["코인"] >= 30:
            advice.append("코인 비중이 높은 편입니다. 변동성이 큰 자산이므로 주문 규모와 손실 가능 범위를 함께 점검해 보세요.")
        if weights["대체자산"] >= 35:
            advice.append("대체자산에는 선물·옵션처럼 증거금과 만기 구조가 있는 상품이 포함될 수 있습니다. 현금 여유와 계약 조건을 확인하세요.")
        if weights["현금"] >= 50:
            advice.append("현금 비중이 높아 변동성 방어 여력은 큽니다. 투자 목적과 기간에 맞는 분할 진입 계획을 세워볼 수 있습니다.")
        if len(advice) == 0:
            advice.append("자산군이 비교적 나뉘어 있습니다. 각 상품의 변동성·유동성·주문 단위를 주기적으로 점검해 비중을 관리하세요.")
    return jsonify({"totalAsset": round(total), "allocation": values, "advice": advice,
                    "notice": "모의투자 교육용 분석이며 개인별 투자 권유가 아닙니다."})


@member_bp.get("/investor-rankings")
def investor_rankings():
    """현금·주식·코인 평가액을 합산한 모의투자 공개 수익 랭킹."""
    now = time.time()
    with _ranking_cache_lock:
        if _ranking_cache["data"] and now - _ranking_cache["ts"] < RANKING_CACHE_TTL:
            return jsonify(_ranking_cache["data"])

    with session_scope() as db:
        members = db.query(Member).all()
        totals = {member.member_id: float(member.asset) for member in members}

        for position in db.query(StockPosition).all():
            # 랭킹 패널은 즉시 보여야 하므로 외부 시세 호출을 기다리지 않는다.
            # 이미 조회한 최신 시세가 없으면 매입단가로 평가한다.
            value = position.quantity * (cached_price(position.symbol) or position.avg_price)
            totals[position.member_id] = totals.get(position.member_id, 0) + value

        crypto_rows = db.query(HoldCrypto, UpbitMarket).join(
            UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id
        ).all()
        codes = sorted({market.market_code for _, market in crypto_rows})
        prices = {}
        if codes and now - _crypto_price_cache["ts"] < RANKING_CACHE_TTL:
            prices = _crypto_price_cache["prices"]
        elif codes:
            try:
                response = requests.get("https://api.upbit.com/v1/ticker", params={"markets": ",".join(codes)}, timeout=1)
                response.raise_for_status()
                prices = {row["market"]: float(row["trade_price"]) for row in response.json()}
                _crypto_price_cache.update({"ts": now, "prices": prices})
            except Exception:
                pass
        for holding, market in crypto_rows:
            totals[holding.member_id] = totals.get(holding.member_id, 0) + holding.buy_crypto_count * prices.get(market.market_code, holding.buy_average)

        for member in members:
            totals[member.member_id] = totals.get(member.member_id, 0) + position_value(db, member.member_id)

        rankings = []
        for member in members:
            total_asset = round(totals.get(member.member_id, 0))
            profit = total_asset - INITIAL_ASSET
            rankings.append({
                "username": member.username or "익명 투자자",
                "totalAsset": total_asset,
                "profit": profit,
                "profitRate": round(profit / INITIAL_ASSET * 100, 2),
            })
        rankings.sort(key=lambda row: row["profitRate"], reverse=True)
        for rank, row in enumerate(rankings[:10], start=1):
            row["rank"] = rank
        result = {"rankings": rankings[:10], "cachedForSeconds": RANKING_CACHE_TTL}
        with _ranking_cache_lock:
            _ranking_cache.update({"ts": now, "data": result})
        return jsonify(result)


@member_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "이메일과 비밀번호를 입력해주세요."}), 400

    with session_scope() as db:
        member = db.query(Member).filter(Member.email == email).first()
        if not member or not _check_password(password, member.password):
            return jsonify({"error": "아이디 또는 비밀번호가 맞지 않습니다."}), 401

        session.clear()
        session["member_id"] = member.member_id
        session.permanent = True
        return jsonify({"username": member.username, "asset": member.asset})


@member_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    password2 = body.get("password2") or ""

    if not username:
        return jsonify({"field": "username", "error": "이름을 입력해주세요."}), 400
    if not email or "@" not in email:
        return jsonify({"field": "email", "error": "올바른 이메일을 입력해주세요."}), 400
    if not password:
        return jsonify({"field": "password", "error": "비밀번호를 입력해주세요."}), 400
    if not password2:
        return jsonify({"field": "password2", "error": "비밀번호 확인을 입력해주세요."}), 400
    if password != password2:
        return jsonify({"field": "password2", "error": "패스워드가 일치하지 않습니다."}), 400

    with session_scope() as db:
        if db.query(Member).filter(Member.email == email).first():
            return jsonify({"field": "email", "error": "이미 존재하는 회원입니다."}), 400

        member = Member(username=username, email=email, password=_hash_password(password), asset=INITIAL_ASSET)
        db.add(member)
        db.flush()
        session.clear()
        session["member_id"] = member.member_id
        session.permanent = True
        return jsonify({"username": username})


@member_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})
