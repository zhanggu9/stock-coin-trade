"""운영 중인 모의투자 서비스에 안전하게 추가할 수 있는 예제 투자자 데이터."""

import logging
import os
from datetime import datetime, timedelta

import bcrypt

from db import session_scope
from models import HoldCrypto, Member, StockOrder, StockPosition, UpbitMarket
from stock_market import BASE_PRICES, STOCKS

LOGGER = logging.getLogger(__name__)
DEMO_EMAIL_DOMAIN = "@sample-investor.local"
DEMO_PASSWORD = "123456"
INITIAL_ASSET = 10_000_000

DEMO_NAMES = (
    "김가온", "이도윤", "박서연", "최민준", "정하린", "윤지후", "한예린", "오현우", "서유진", "강시우",
    "임나연", "조태윤", "신채원", "권도현", "문서진", "배지민", "송예준", "남유나", "류건우", "안수빈",
    "노재현", "장다은", "백준서", "허지안", "전민서", "고은찬", "황유진", "차도윤", "양하은", "서건호",
)

CRYPTO_MARKETS = {
    "KRW-BTC": ("비트코인", "Bitcoin", 150_000_000),
    "KRW-ETH": ("이더리움", "Ethereum", 5_000_000),
    "KRW-XRP": ("리플", "XRP", 3_100),
    "KRW-SOL": ("솔라나", "Solana", 240_000),
    "KRW-ADA": ("에이다", "Cardano", 1_150),
    "KRW-DOGE": ("도지코인", "Dogecoin", 260),
    "KRW-AVAX": ("아발란체", "Avalanche", 36_000),
    "KRW-LINK": ("체인링크", "Chainlink", 28_000),
    "KRW-DOT": ("폴카닷", "Polkadot", 7_500),
    "KRW-TRX": ("트론", "TRON", 410),
}


def _demo_email(index: int) -> str:
    return f"sample-investor-{index:02d}{DEMO_EMAIL_DOMAIN}"


def _get_or_create_market(db, code: str) -> UpbitMarket:
    market = db.query(UpbitMarket).filter(UpbitMarket.market_code == code).first()
    if market:
        return market
    korean_name, english_name, _ = CRYPTO_MARKETS[code]
    market = UpbitMarket(market_code=code, korean_name=korean_name, english_name=english_name)
    db.add(market)
    db.flush()
    return market


def _portfolio_for(index: int) -> tuple[list[tuple[str, int, int]], list[tuple[str, int, float]]]:
    """각 투자자에게 서로 다른 2개 주식과 2개 코인 포지션을 만든다."""
    symbols = list(STOCKS)
    coin_codes = list(CRYPTO_MARKETS)
    stock_allocations = (1_650_000, 1_250_000)
    crypto_allocations = (900_000, 700_000)
    stocks = []
    coins = []

    for offset, allocation in enumerate(stock_allocations):
        symbol = symbols[(index * 3 + offset * 5) % len(symbols)]
        base = BASE_PRICES[symbol]
        # 투자자마다 평균 매입가가 달라 수익·손실 사례가 함께 나타난다.
        avg_price = int(base * (0.86 + ((index + offset * 2) % 8) * 0.04))
        quantity = max(1, allocation // avg_price)
        stocks.append((symbol, quantity, avg_price))

    for offset, allocation in enumerate(crypto_allocations):
        code = coin_codes[(index * 2 + offset * 3) % len(coin_codes)]
        base_price = CRYPTO_MARKETS[code][2]
        avg_price = base_price * (0.80 + ((index + offset * 3) % 9) * 0.05)
        coins.append((code, allocation, avg_price))
    return stocks, coins


def seed_demo_investors() -> int:
    """30개의 샘플 투자자와 보유 주식·코인을 추가한다.

    같은 이메일이 이미 있으면 해당 계정은 그대로 두므로 재기동·재배포해도
    중복 생성하거나 사용자가 변경한 샘플 포트폴리오를 덮어쓰지 않는다.
    """
    if os.environ.get("DEMO_SEED_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return 0

    try:
        with session_scope() as db:
            password_hash = bcrypt.hashpw(DEMO_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            added = 0
            now = datetime.now()
            for index, name in enumerate(DEMO_NAMES, start=1):
                if db.query(Member).filter(Member.email == _demo_email(index)).first():
                    continue

                stocks, coins = _portfolio_for(index - 1)
                stock_cost = sum(quantity * avg_price for _, quantity, avg_price in stocks)
                crypto_cost = sum(amount for _, amount, _ in coins)
                member = Member(
                    username=name,
                    email=_demo_email(index),
                    password=password_hash,
                    asset=max(300_000, INITIAL_ASSET - stock_cost - crypto_cost),
                )
                db.add(member)
                db.flush()

                for order_index, (symbol, quantity, avg_price) in enumerate(stocks):
                    db.add(StockPosition(
                        member_id=member.member_id,
                        symbol=symbol,
                        quantity=quantity,
                        avg_price=avg_price,
                    ))
                    db.add(StockOrder(
                        member_id=member.member_id,
                        symbol=symbol,
                        name=STOCKS[symbol]["name"],
                        order_type="BUY",
                        quantity=quantity,
                        price=avg_price,
                        amount=quantity * avg_price,
                        source="DEMO_SEED",
                        created_at=now - timedelta(days=8 + index + order_index * 4),
                    ))

                for code, amount, avg_price in coins:
                    market = _get_or_create_market(db, code)
                    db.add(HoldCrypto(
                        member_id=member.member_id,
                        upbit_market_id=market.upbit_market_id,
                        buy_average=avg_price,
                        buy_crypto_count=round(amount / avg_price, 8),
                        buy_total_krw=amount,
                    ))
                added += 1
        if added:
            LOGGER.info("Added %s sample investor portfolios.", added)
        return added
    except Exception:
        # 시드 실패가 서비스 기동 자체를 막지 않도록 하되, 원인은 컨테이너 로그에 남긴다.
        LOGGER.exception("Unable to seed sample investor portfolios")
        return 0
