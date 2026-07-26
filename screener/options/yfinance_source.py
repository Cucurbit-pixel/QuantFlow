import yfinance as yf
from screener.options.base import OptionsDataSource
from screener.common import get_logger

logger = get_logger(__name__)


def _rows_to_contracts(df) -> list:
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.iterrows():
        out.append({
            "strike": float(row.get("strike") or 0),
            "volume": int(row.get("volume") or 0),
            "open_interest": int(row.get("openInterest") or 0),
            "bid": float(row.get("bid") or 0) if row.get("bid") is not None else None,
            "ask": float(row.get("ask") or 0) if row.get("ask") is not None else None,
            "last": float(row.get("lastPrice") or 0) if row.get("lastPrice") is not None else None,
        })
    return out


class YFinanceOptionsSource(OptionsDataSource):
    def get_spot(self, ticker: str) -> float | None:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist is None or hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"yfinance spot {ticker}: {e}")
            return None

    def get_expirations(self, ticker: str) -> list[str]:
        try:
            opts = yf.Ticker(ticker).options
            return list(opts) if opts else []
        except Exception as e:
            logger.warning(f"yfinance expiries {ticker}: {e}")
            return []

    def get_chain(self, ticker: str, expiry: str) -> dict:
        try:
            chain = yf.Ticker(ticker).option_chain(expiry)
            return {
                "calls": _rows_to_contracts(chain.calls),
                "puts": _rows_to_contracts(chain.puts),
            }
        except Exception as e:
            logger.warning(f"yfinance chain {ticker} {expiry}: {e}")
            return {"calls": [], "puts": []}