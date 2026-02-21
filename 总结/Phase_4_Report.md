# 报告第四阶段：执行层（硬风控与双重副驾驶）开发完成
# Phase 4 Report: Execution Layer (Hard Risk Control) Completed

## 进展摘要 / Progress Summary

系统第四阶段的“防御塔”已经竣工，我们编写了 `execution_risk.py`。这个模块是保障本金安全的生命线。无论大模型输出何种指令，都必须经过这套不可逾越的本地硬规则的审查与压制。
Phase 4's "defense towers" are completed via the newly written `execution_risk.py`. This module is the lifeline for capital preservation. Regardless of the LLM's directives, they MUST be scrutinized and suppressed by this impassable set of local hard rules.

## 具体完成事项 / Completed Items

### 1. 仓位暴露天花板 (Position Sizing Ceiling)
- **机制 (Mechanism)**: 
  - 强制规定：单次建仓的最大资金使用量，绝对不允许超过模拟总账户量（例如 $100,000）的 `10%`。(Mandatory rule: The maximum capital allocated for a single position must never exceed 10% of the total simulated account equity.)
- **效果 (Effect)**: 
  - 无论 DeepSeek 如何自信，你永远不会在一只票上被过度套牢。(No matter how confident DeepSeek is, you will never be over-leveraged on a single stock.)

### 2. 双重副驾驶拦截器 (Dual Co-pilot Interceptor)
- **机制 (Mechanism)**: 
  - 即使接收到了大模型的 `BUY` 指令，依然要检查本地通过 AkShare/Pandas 计算出的硬指标（即第二阶段的数据）。例如，如果本地 `RSI >= 70`（严重超买），拦截器会无情驳回大模型，并强制将状态重写为 `HOLD`。(Even if a `BUY` directive is received from the LLM, local hard metrics calculated via AkShare/Pandas (from Phase 2) are checked. For example, if local `RSI >= 70` (severe overbought), the interceptor ruthlessly rejects the LLM and forcefully rewrites the status to `HOLD`.)
- **效果 (Effect)**: 
  - 防治人工智能发生“追大高”的惨剧。(Prevents the AI from blindly "chasing the peak".)

### 3. 止损防线与利润保卫战 (Stop-Loss line & Profit Protection)
- **硬止损 (Hard Stop-Loss)**: 
  - 买入后，任何时刻只要现价跌破买入成本价的 `8%`，系统不仅无视模型信号，还会立即拉响本土最高阶警报 `SELL_ALL`。(After buying, if the current price drops 8% below the cost price at any moment, the system not only ignores model signals but immediately sounds the highest local alarm `SELL_ALL`.)
- **动态移动止损 (Trailing Stop for Profit)**: 
  - 根据您的实战建议已部署：只要该笔持仓曾获得超过 `10%` 的最高盈利，系统即刻锁定利润。启动移动止损针，若价格从最高点回撤超过 `5%`，直接触发 `SELL_ALL` 平仓逃顶。(Deployed based on your combat experience: As long as the position has achieved a peak profit of over 10%, the system locks the profit. A trailing stop is activated, and if the price drops by more than 5% from its highest peak, it triggers a `SELL_ALL` to escape the top.)

## 下一步计划 (Next Steps)
准备进军视觉工程 **第五阶段：“半自动”可视化监控中心** / Ready to advance into visual engineering **Phase 5: "Semi-Auto" Visual Monitoring Center**.
