from datetime import datetime, timedelta
import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)

# 美股主要固定假期 (月, 日)
US_HOLIDAYS_FIXED = {
    (1, 1),    # New Year's Day
    (6, 19),   # Juneteenth
    (7, 4),    # Independence Day
    (12, 25),  # Christmas
}


def _is_weekend(d: datetime) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun


def _is_fixed_holiday(d: datetime) -> bool:
    return (d.month, d.day) in US_HOLIDAYS_FIXED


def get_last_trading_day(reference: datetime = None) -> datetime:
    """
    取得最近一個美股交易日（跳過週末與常見假期）
    並用 SPY 驗證是否有成交數據
    """
    if reference is None:
        reference = datetime.now()

    d = reference.replace(hour=0, minute=0, second=0, microsecond=0)

    for _ in range(10):
        if not _is_weekend(d) and not _is_fixed_holiday(d):
            try:
                spy = yf.Ticker("SPY")
                hist = spy.history(
                    start=d.strftime("%Y-%m-%d"),
                    end=(d + timedelta(days=1)).strftime("%Y-%m-%d")
                )
                if not hist.empty:
                    return d
            except Exception:
                pass
        d -= timedelta(days=1)

    # fallback
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="10d")
        if not hist.empty:
            last = hist.index[-1].to_pydatetime().replace(tzinfo=None)
            return last.replace(hour=0, minute=0, second=0, microsecond=0)
    except Exception as e:
        logger.error(f"取得最後交易日失敗: {e}")

    return reference


def is_market_closed_today() -> bool:
    """今日是否休市（週末或假期）"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if _is_weekend(today) or _is_fixed_holiday(today):
        return True
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(
            start=today.strftime("%Y-%m-%d"),
            end=(today + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        return hist.empty
    except Exception:
        return False


def get_scan_data_date_info() -> dict:
    """
    回傳掃描應使用的數據日期資訊
    {
        "is_closed": bool,
        "data_date": "2026-07-24",
        "display": "2026-07-24（休市，使用前一交易日）"
    }
    """
    today = datetime.now()
    closed = is_market_closed_today()
    last_td = get_last_trading_day(today)

    data_date = last_td.strftime("%Y-%m-%d")
    if closed:
        display = f"{data_date}（休市，使用前一交易日）"
    else:
        if last_td.date() < today.date():
            display = f"{data_date}（使用最近交易日）"
        else:
            display = data_date

    return {
        "is_closed": closed,
        "data_date": data_date,
        "display": display
    }