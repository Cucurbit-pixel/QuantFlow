def save_scan_result(filtered: list):
    """把掃描結果存成 JSON"""
    Path("data").mkdir(exist_ok=True)

    from screener.market_calendar import get_scan_data_date_info
    date_info = get_scan_data_date_info()

    result = {
        "scan_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": date_info["data_date"],
        "data_date_display": date_info["display"],
        "market_closed": date_info["is_closed"],
        "count": len(filtered),
        "stocks": filtered
    }

    with open("data/latest_scan.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"已儲存掃描結果（數據日：{date_info['display']}，{len(filtered)} 隻）")