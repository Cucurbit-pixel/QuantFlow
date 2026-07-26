from abc import ABC, abstractmethod
import os


class OptionsDataSource(ABC):
    """期權鏈數據源介面（方便日後換 Tradier / 付費 API）"""

    @abstractmethod
    def get_spot(self, ticker: str) -> float | None:
        pass

    @abstractmethod
    def get_expirations(self, ticker: str) -> list[str]:
        pass

    @abstractmethod
    def get_chain(self, ticker: str, expiry: str) -> dict:
        """
        回傳:
        {
          "calls": [ {strike, volume, open_interest, bid, ask, last}, ... ],
          "puts":  [ ... ]
        }
        """
        pass

    def get_chains(self, ticker: str, max_expiries: int = 2) -> dict:
        """
        回傳:
        {
          "ticker": str,
          "spot": float | None,
          "chains": { "YYYY-MM-DD": {"calls": [...], "puts": [...]} }
        }
        """
        spot = self.get_spot(ticker)
        expiries = self.get_expirations(ticker)[:max_expiries]
        chains = {}
        for exp in expiries:
            try:
                chains[exp] = self.get_chain(ticker, exp)
            except Exception:
                continue
        return {"ticker": ticker, "spot": spot, "chains": chains}


def get_options_source() -> OptionsDataSource:
    """依環境變數選擇數據源，預設 yfinance"""
    source = os.getenv("OPTIONS_SOURCE", "yfinance").lower()
    if source == "yfinance":
        from screener.options.yfinance_source import YFinanceOptionsSource
        return YFinanceOptionsSource()
    # 之後可加:
    # if source == "tradier":
    #     from screener.options.tradier_source import TradierOptionsSource
    #     return TradierOptionsSource()
    from screener.options.yfinance_source import YFinanceOptionsSource
    return YFinanceOptionsSource()