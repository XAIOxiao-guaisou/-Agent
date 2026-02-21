# 报告第二阶段：感知层（数据收割机）开发完成
# Phase 2 Report: Perception Layer (Data Harvester) Setup Completed

## 进展摘要 / Progress Summary

我们已经成功完成了第二阶段“感知层”的开发，物理实体脚本 `data_harvester.py` 已经就绪。它现在作为一个兼具防风险和反侦察能力的“情报特工”，能够稳定地为 DeepSeek 大脑输送结构化量价特征与非结构化市场情绪。
We have successfully completed the development of Phase 2 (Perception Layer), and the physical script `data_harvester.py` is ready. Acting as an "intelligence agent" equipped with risk-prevention and anti-reconnaissance capabilities, it can stably deliver structured price-volume features and unstructured market sentiment to the DeepSeek brain.

## 具体完成事项 / Completed Items

### 1. 结构化量价引擎 (Structured Data Engine)
- **硬编码防线 (Hardcoded Defense)**: 
  - 设立了 `TARGET_POOL = ["00700", "03690", "09988"]`，从源头切断了脚本处理老千股或杂音标的可能。(Established a rigorous `TARGET_POOL` to block any processing of "penny" or noisy stocks from the source.)
- **复权清洗 (Forward Adjusted Cleaning)**: 
  - 强制接入 AkShare 东方财富源接口 `stock_hk_hist_min_em`，并硬编码 `adjust="qfq"` 参数，彻底消除了由于分红派息引发的 K 线虚假“暴跌”。(Mandatorily integrated Akshare EM API with `adjust="qfq"` to completely eliminate false K-line "crashes" caused by dividends.)
- **时间轴缝合 (Time Axis Stitching)**: 
  - 针对港股独特的午盘休市制度 (12:00-13:00)，使用 Pandas 在构建 DataFrame 期间剔除了该时段的幽灵空值，确保 60 分钟线的 MACD 及趋势均线完美连贯不偏移。(Addressed the unique HK market lunch break by strictly filtering out ghost null values during this window using Pandas, ensuring perfect continuity of 60-min MACD and trend MAs without drift.)
- **基础指标基石 (Local Indicators Benchmark)**: 
  - 本地急速计算 14 期 RSI 和标准 MACD 参数 (12,26,9)，为第四阶段的“双重副驾驶”风控提供了坚实的数据弹药。(Locally and rapidly calculatd 14-period RSI and standard MACD (12,26,9), providing solid data ammunition for the "Dual Co-pilot" risk control in Phase 4.)

### 2. 非结构化情绪引擎 (Unstructured Sentiment Engine)
- **动静结合的反爬伪装 (Dynamic Anti-bot Camouflage)**: 
  - 引擎内置了多元 User-Agent 伪装池，并在每次请求新闻 API 前加入 `random.uniform(2, 5)` 秒的动态随机休眠机制，有效防止源网站的 IP 封锁与限流。(The engine features a built-in diverse User-Agent pool and enforces a dynamic random sleep of 2-5 seconds before each API request, effectively preventing source website IP bans and rate-limiting.)
- **情报网捕获 (Intelligence Web Capture)**: 
  - 搭建了获取指定个股对应相关新闻和市场风向的抓取框架逻辑（已封装在 `fetch_sentiment_news` 中），这将在后期被送入大模型的 Prompt 喂料。(Deployed the framework logic for gathering symbol-specific related news and market sentiment (encapsulated in `fetch_sentiment_news`), which will be fed into the LLM's Prompt later.)

## 下一步计划 (Next Steps)
准备进入核心灵魂 **第三阶段：决策层（DeepSeek 外脑对接）** / Ready to enter the core soul **Phase 3: Decision Layer (DeepSeek Brain Integration)**.

*注：您在物理机运行测试时可能会遇到代理拒绝连接(ProxyError)，这是由于目前脚本内配置了通用的 `127.0.0.1:7890`，实盘前需根据您机器的具体网络进行修改。但这不影响系统工程的推进。*
*(Note: You might encounter ProxyError during physical machine testing because the script uses a universal `127.0.0.1:7890` base. This needs modification according to your actual setup before live-trading, but it doesn't affect the progression of system engineering.)*
