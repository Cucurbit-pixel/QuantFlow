import json
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from screener.common import get_logger
from screener.options import get_options_source

logger = get_logger(__name__)

OPTIONS_CACHE = Path("data/options_alerts.json")
OI_CACHE = Path("data/oi_structure.json")
CACHE_MINUTES = 15

OPTIONS_UNIVERSE = [
    "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD",
    "META", "AMZN", "GOOGL", "AVGO", "NFLX", "CRM", "ORCL",
    "JPM", "BAC", "XOM", "COST", "UNH"
]
OI_TICKERS = ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "AMZN", "META"]


def _exp_short(exp: str) -> str:
    parts = exp.split("-")
    return f"{parts[1]}-{parts[2]}" if len(parts) == 3 else exp


def _moneyness(opt_type: str, strike: float, spot: float) -> str:
    if opt_type == "CALL":
        if strike < spot * 0.98:
            return "價內"
        if strike > spot * 1.02:
            return "價外"
        return "平價"
    if strike > spot * 1.02:
        return "價內"
    if strike < spot * 0.98:
        return "價外"
    return "平價"


def _recommend(opt_type: str, moneyness: str, strike: float, spot: float,
               call_wall: float | None, put_wall: float | None) -> tuple[str, str]:
    """
    回傳 (建議, 理由)
    賣出會標「謹慎」
    """
    near_call_wall = call_wall is not None and abs(strike - call_wall) / max(spot, 1) < 0.03
    near_put_wall = put_wall is not None and abs(strike - put_wall) / max(spot, 1) < 0.03

    if opt_type == "CALL":
        if moneyness in ("平價", "價內"):
            return "建議買入 Call", "平價/價內 Call 異動，偏多結構"
        if moneyness == "價外" and near_call_wall:
            return "建議賣出 Call（謹慎）", "價外 Call 接近 Call Wall，阻力區收權利金（風險較高）"
        return "建議買入 Call", "Call 異動，偏多結構（參考）"

    # PUT
    if moneyness in ("平價", "價內"):
        return "建議買入 Put", "平價/價內 Put 異動，偏空/保護"
    if moneyness == "價外" and near_put_wall:
        return "建議賣出 Put（謹慎）", "價外 Put 接近 Put Wall，支撐區收權利金（風險較高）"
    return "建議買入 Put", "Put 異動，偏空結構（參考）"


def _calc_max_pain(calls: list, puts: list) -> float | None:
    strikes = set()
    call_oi, put_oi = {}, {}
    for c in calls:
        k, oi = c["strike"], c["open_interest"]
        if k > 0:
            strikes.add(k)
            call_oi[k] = call_oi.get(k, 0) + oi
    for p in puts:
        k, oi = p["strike"], p["open_interest"]
        if k > 0:
            strikes.add(k)
            put_oi[k] = put_oi.get(k, 0) + oi
    if not strikes:
        return None
    best_s, best_pain = None, None
    for s in sorted(strikes):
        pain = sum(max(0.0, s - k) * oi for k, oi in call_oi.items())
        pain += sum(max(0.0, k - s) * oi for k, oi in put_oi.items())
        if best_pain is None or pain < best_pain:
            best_pain, best_s = pain, s
    return best_s


def _walls(calls: list, puts: list):
    cw_k, cw_oi = None, 0
    pw_k, pw_oi = None, 0
    total_c, total_p = 0, 0
    for c in calls:
        oi = c["open_interest"]
        total_c += oi
        if oi > cw_oi:
            cw_oi, cw_k = oi, c["strike"]
    for p in puts:
        oi = p["open_interest"]
        total_p += oi
        if oi > pw_oi:
            pw_oi, pw_k = oi, p["strike"]
    return cw_k, cw_oi, pw_k, pw_oi, total_c, total_p


def analyze_oi_structure(ticker: str) -> dict | None:
    src = get_options_source()
    data = src.get_chains(ticker, max_expiries=1)
    spot = data.get("spot")
    if not spot or not data.get("chains"):
        return None
    exp = next(iter(data["chains"]))
    chain = data["chains"][exp]
    calls, puts = chain["calls"], chain["puts"]
    cw, cw_oi, pw, pw_oi, tc, tp = _walls(calls, puts)
    mp = _calc_max_pain(calls, puts)
    pcr = round(tp / tc, 2) if tc > 0 else None
    bias = "偏空" if pcr and pcr > 1.0 else "偏多" if pcr is not None else "—"
    return {
        "ticker": ticker,
        "spot": round(spot, 2),
        "expiry": _exp_short(exp),
        "call_wall": cw,
        "call_wall_oi": cw_oi,
        "put_wall": pw,
        "put_wall_oi": pw_oi,
        "max_pain": mp,
        "put_call_oi_ratio": pcr,
        "bias": bias,
    }


def scan_ticker_options(ticker: str, min_vol: int = 200, min_vol_oi: float = 2.0) -> list:
    src = get_options_source()
    data = src.get_chains(ticker, max_expiries=2)
    spot = data.get("spot")
    if not spot:
        return []

    # 先取 wall 供建議邏輯
    call_wall = put_wall = None
    if data["chains"]:
        first = next(iter(data["chains"].values()))
        call_wall, _, put_wall, _, _, _ = _walls(first["calls"], first["puts"])

    alerts = []
    for exp, chain in data["chains"].items():
        exp_s = _exp_short(exp)
        for opt_type, contracts in [("CALL", chain["calls"]), ("PUT", chain["puts"])]:
            for c in contracts:
                vol, oi, strike = c["volume"], c["open_interest"], c["strike"]
                if vol < min_vol or oi <= 0:
                    continue
                vol_oi = round(vol / oi, 2)
                if vol_oi < min_vol_oi:
                    continue
                if vol_oi >= 4.0 and vol >= 500:
                    level = "high"
                elif vol_oi >= 2.5 and vol >= 300:
                    level = "medium"
                else:
                    level = "low"
                m = _moneyness(opt_type, strike, spot)
                rec, reason = _recommend(opt_type, m, strike, spot, call_wall, put_wall)
                alerts.append({
                    "level": level,
                    "ticker": ticker,
                    "option_type": opt_type,
                    "recommendation": rec,
                    "reason": reason,
                    "strike": strike,
                    "expiry": exp_s,
                    "vol_oi": vol_oi,
                    "volume": vol,
                    "oi": oi,
                    "moneyness": m,
                    "bias": "偏多" if opt_type == "CALL" else "偏空",
                })
    return alerts


def scan_options_unusual(tickers=None, min_vol=200, min_vol_oi=2.0, max_results=12) -> list:
    tickers = tickers or OPTIONS_UNIVERSE
    all_alerts = []
    logger.info(f"期權異動掃描 {len(tickers)} 隻...")

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(scan_ticker_options, t, min_vol, min_vol_oi): t for t in tickers}
        for fut in as_completed(futs):
            try:
                all_alerts.extend(fut.result())
            except Exception as e:
                logger.error(f"期權掃描失敗: {e}")

    all_alerts.sort(key=lambda x: x["vol_oi"], reverse=True)
    result = all_alerts[:max_results]
    logger.info(f"期權異動完成：{len(result)} 筆")
    return result


def scan_oi_structures(tickers=None) -> list:
    tickers = tickers or OI_TICKERS
    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(analyze_oi_structure, t): t for t in tickers}
        for fut in as_completed(futs):
            try:
                r = fut.result()
                if r:
                    results.append(r)
            except Exception as e:
                logger.error(f"OI 結構失敗: {e}")
    results.sort(key=lambda x: x["ticker"])
    return results


def _save(path: Path, key: str, items: list):
    Path("data").mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            key: items
        }, f, ensure_ascii=False, indent=2)


def _load(path: Path, key: str) -> list:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        t = datetime.strptime(data.get("scan_time", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
        if datetime.now() - t > timedelta(minutes=CACHE_MINUTES):
            return []
        return data.get(key, [])
    except Exception:
        return []


def load_options_cache() -> list:
    return _load(OPTIONS_CACHE, "alerts")


def load_oi_structure_cache() -> list:
    return _load(OI_CACHE, "structures")


def get_or_scan_options(force: bool = False) -> list:
    if not force:
        cached = load_options_cache()
        if cached:
            return cached
    alerts = scan_options_unusual()
    _save(OPTIONS_CACHE, "alerts", alerts)
    structures = scan_oi_structures()
    _save(OI_CACHE, "structures", structures)
    return alerts