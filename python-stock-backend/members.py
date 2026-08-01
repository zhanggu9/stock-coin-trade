import bcrypt
import requests
from flask import Blueprint, jsonify, request, session

from db import session_scope
from models import HoldCrypto, Member, StockPosition, UpbitMarket
from stock_market import current_price

member_bp = Blueprint("member", __name__, url_prefix="/api/member")
INITIAL_ASSET = 10_000_000


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


@member_bp.get("/investor-rankings")
def investor_rankings():
    """현금·주식·코인 평가액을 합산한 모의투자 공개 수익 랭킹."""
    with session_scope() as db:
        members = db.query(Member).all()
        totals = {member.member_id: float(member.asset) for member in members}

        for position in db.query(StockPosition).all():
            try:
                value = position.quantity * current_price(position.symbol)
            except Exception:
                value = position.quantity * position.avg_price
            totals[position.member_id] = totals.get(position.member_id, 0) + value

        crypto_rows = db.query(HoldCrypto, UpbitMarket).join(
            UpbitMarket, HoldCrypto.upbit_market_id == UpbitMarket.upbit_market_id
        ).all()
        codes = sorted({market.market_code for _, market in crypto_rows})
        prices = {}
        if codes:
            try:
                response = requests.get("https://api.upbit.com/v1/ticker", params={"markets": ",".join(codes)}, timeout=3)
                response.raise_for_status()
                prices = {row["market"]: float(row["trade_price"]) for row in response.json()}
            except Exception:
                pass
        for holding, market in crypto_rows:
            totals[holding.member_id] = totals.get(holding.member_id, 0) + holding.buy_crypto_count * prices.get(market.market_code, holding.buy_average)

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
        return jsonify({"rankings": rankings[:10]})


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

        member = Member(username=username, email=email, password=_hash_password(password), asset=10_000_000)
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
