# QuantFlow Architecture

## 整體設計

QuantFlow 採用模組化設計，主要分為以下層：

- **Data Layer**：`build_universe.py` 負責股票清單管理
- **Feature Layer**：`features.py` 負責技術指標計算
- **Filter Layer**：`filters.py` 負責動態過濾
- **Merge Layer**：`merge.py` 負責整合與排名
- **Notification Layer**：`notifier.py` 負責 Discord 通知

## 主要流程

1. `build_universe.py` 建立或更新股票清單
2. `merge.py` 觸發掃描
3. `filters.py` 過濾股票
4. `notifier.py` 發送結果通知

## 配置

所有主要參數集中在 `params.json`，方便調整。