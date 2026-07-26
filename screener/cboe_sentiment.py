"""
CBOE 情緒指標（免費近似版）
- VIX：水平 + 近幾日方向
- 指數/個股 Put/Call：SPY、QQQ、IWM 近月 OI 近似
"""
from datetime import datetime, timedelta
from pathlib import Path
import json
import yfinance as yf
from screener.common import get_logger

logger = get_logger(__name__)

CACHE_PATH = Path("data/cboe_sentiment.json")
CACHE_MINUTES = 30


def _pc_label(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    if ratio >= 1.2:
        return "偏防禦／偏空"
    if ratio >= 1.0:
        return "中性偏防禦"
    if ratio >= 0.7:
        return "中性偏多"
    return "偏多"


def _vix_level_label(vix: float | None) -> str:
    if vix is None:
        return "—"
    if vix >= 30:
        return "恐懼"
    if vix >= 25:
        return "偏恐懼"
    if vix >= 20:
        return "中性"
    if vix >= 15:
        return "中性偏多"
    return "貪婪"


def _vix_direction(change_pct: float | None) -> str:
    if change_pct is None:
        return "—"
    if change_pct >= 10:
        return "急升"
    if change_pct >= 3:
        return "上升"
    if change_pct <= -10:
        return "急跌"
    if change_pct <= -3:
        return "回落"
    return "平穩"


def _safe_float(x):
    try:
        v = float(x)
        if v != v:
            return None
        return v
    except Exception:
        return None


def _put_call_from_ticker(ticker: str) -> float | None:
    try:
        t = yf.Ticker(ticker)
        expiries = t.options
        if not expiries:
            return None
        chain = t.option_chain(expiries[0])
        call_oi = 0
        put_oi = 0
        if chain.calls is not None and not chain.calls.empty:
            call_oi = int(chain.calls["openInterest"].fillna(0).sum())
        if chain.puts is not None and not chain.puts.empty:
            put_oi = int(chain.puts["openInterest"].fillna(0).sum())
        if call_oi <= 0:
            return None
        return round(put_oi / call_oi, 2)
    except Exception as e:
        logger.warning(f"P/C {ticker} 失敗: {e}")
        return None


def _get_vix_with_direction() -> tuple[float | None, float | None, str, str]:
    """
    回傳: (vix, change_pct, level_label, direction_label)
    """
    try:
        hist = yf.Ticker("^VIX").history(period="10d")
        if hist is None or hist.empty:
            return None, None, "—", "—"
        vix = _safe_float(hist["Close"].iloc[-1])
        if vix is None:
            return None, None, "—", "—"
        change_pct = None
        if len(hist) >= 2:
            prev = _safe_float(hist["Close"].iloc[-2])
            if prev and prev > 0:
                change_pct = (vix - prev) / prev * 100
        level = _vix_level_label(vix)
        direction = _vix_direction(change_pct)
        return vix, change_pct, level, direction
    except Exception as e:
        logger.warning(f"VIX 失敗: {e}")
        return None, None, "—", "—"


def fetch_cboe_sentiment() -> dict:
    vix, vix_chg, vix_level, vix_dir = _get_vix_with_direction()

    spy_pc = _put_call_from_ticker("SPY")
    qqq_pc = _put_call_from_ticker("QQQ")
    index_vals = [x for x in (spy_pc, qqq_pc) if x is not None]
    index_pc = round(sum(index_vals) / len(index_vals), 2) if index_vals else None
    equity_pc = _put_call_from_ticker("IWM")  # 個股情緒近似

    ix_l = _pc_label(index_pc)
    eq_l = _pc_label(equity_pc)

    if vix is not None:
        vix_label = f"{vix_level} · {vix_dir}"
    else:
        vix_label = "—"

    # 短版（狀態列）
    short_parts = []
    if vix is not None:
        short_parts.append(f"VIX {vix:.1f}·{vix_level}{'' if vix_dir == '—' else '·' + vix_dir}")
    if index_pc is not None:
        short_parts.append(f"指數P/C {index_pc}·{ix_l}")
    if equity_pc is not None:
        short_parts.append(f"個股P/C {equity_pc}·{eq_l}")
    summary_short = " ｜ ".join(short_parts) if short_parts else "暫無數據"

    return {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "vix": round(vix, 2) if vix is not None else None,
        "vix_change_pct": round(vix_chg, 2) if vix_chg is not None else None,
        "vix_level": vix_level,
        "vix_direction": vix_dir,
        "vix_label": vix_label,
        "index_pc": index_pc,
        "index_pc_label": ix_l,
        "equity_pc": equity_pc,
        "equity_pc_label": eq_l,
        "summary": summary_short,
        "summary_short": summary_short,
    }


def save_cboe_cache(data: dict):
    Path("data").mkdir(exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cboe_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        t = datetime.strptime(
            data.get("scan_time", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S"
        )
        if datetime.now() - t > timedelta(minutes=CACHE_MINUTES):
            return None
        return data
    except Exception:
        return None


def get_cboe_sentiment(force: bool = False) -> dict:
    if not force:
        cached = load_cboe_cache()
        if cached:
            return cached
    data = fetch_cboe_sentiment()
    save_cboe_cache(data)
    return data