import json
import os
from datetime import datetime, timedelta

from QuantConnect import Globals, Resolution, SubscriptionTransportMedium
from QuantConnect.Algorithm import QCAlgorithm
from QuantConnect.Data import SubscriptionDataSource
from QuantConnect.Python import PythonData


class OHLCVJsonData(PythonData):
    """Read one API OHLCV record per JSON Lines row."""

    def get_source(self, config, date, is_live):
        source = os.path.join(Globals.data_folder, "ohlcv.jsonl")
        return SubscriptionDataSource(source, SubscriptionTransportMedium.LOCAL_FILE)

    def reader(self, config, line, date, is_live):
        line = line.strip()
        if not line:
            return None
        try:
            record = json.loads(line)
            data_time = datetime.strptime(record["trade_date"][:10], "%Y-%m-%d")
            open_price = float(record["open"])
            high_price = float(record["high"])
            low_price = float(record["low"])
            close_price = float(record["close"])
            volume = float(record["volume"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

        data = OHLCVJsonData()
        data.symbol = config.symbol
        data.time = data_time
        data.end_time = data_time + timedelta(days=1)
        data.value = close_price
        data["open"] = open_price
        data["high"] = high_price
        data["low"] = low_price
        data["close"] = close_price
        data["volume"] = volume
        adjusted = record.get("adj_close")
        if adjusted is not None:
            try:
                data["adj_close"] = float(adjusted)
            except (TypeError, ValueError):
                pass
        return data


class OHLCVJsonBacktest(QCAlgorithm):
    """Simple buy-and-hold baseline over daily OHLCV from the Open API."""

    def initialize(self):
        ticker_code = (os.getenv("TICKER_CODE") or "UNKNOWN").strip().upper()
        ticker_name = (os.getenv("TICKER_NAME") or ticker_code).strip()[:80]
        initial_cash = float(os.getenv("INITIAL_CASH") or "1000000")

        data_path = os.path.join(Globals.data_folder, "ohlcv.jsonl")
        dates = []
        with open(data_path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    dates.append(datetime.strptime(record["trade_date"][:10], "%Y-%m-%d"))
        if len(dates) < 2:
            raise ValueError("ohlcv.jsonl must contain at least two daily OHLCV records")

        first_day = min(dates)
        last_day = max(dates)
        end_exclusive = last_day + timedelta(days=1)
        self.set_start_date(first_day.year, first_day.month, first_day.day)
        self.set_end_date(end_exclusive.year, end_exclusive.month, end_exclusive.day)
        self.set_cash(initial_cash)

        self.ticker_code = ticker_code
        self.ticker_name = ticker_name
        custom_symbol = f"OHLCV_{ticker_code}"
        self.target = self.add_data(OHLCVJsonData, custom_symbol, Resolution.DAILY).symbol
        self.bought = False

    def on_data(self, data):
        if self.target not in data:
            return
        point = data[self.target]
        close_price = float(point.value)
        self.plot(self.ticker_name, "Close", close_price)
        if self.bought or close_price <= 0:
            return
        quantity = int(self.portfolio.cash / close_price)
        if quantity <= 0:
            self.debug(
                f"{self.ticker_name}({self.ticker_code}): initial cash is insufficient for one unit at {close_price:,.2f}"
            )
            self.bought = True
            return
        self.market_order(self.target, quantity)
        self.bought = True
        self.debug(f"{self.ticker_name}({self.ticker_code}) buy & hold: {quantity} shares at {close_price:,.2f}")
