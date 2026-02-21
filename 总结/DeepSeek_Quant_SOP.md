# 🤖 DeepSeek 云端大脑 + 本地量化中枢 SOP 
### Standard Operating Procedure: DeepSeek Cloud Brain + Local Quant Hub

#### **第一阶段：底层环境与网络基础设施铺设 / Phase 1: Base Environment & Network Infrastructure**
> *量化系统的第一步不是写策略，而是保证你的系统能 24 小时稳定连接外部世界。*
> *The first step for a quantitative system is not writing strategies, but ensuring your system maintains a stable 24/7 connection to the outside world.*

*   **Python 核心环境构建 / Core Python Environment Setup:**
    *   **新建虚拟环境 / New Virtual Environment:** 新建一个纯净的虚拟环境（venv 或 conda）。 
        *Create a pristine virtual environment (using venv or conda).*
    *   **安装核心依赖 / Install Core Dependencies:** `pip install akshare pandas requests urllib3 pydantic schedule`. 如果需要抓取动态网页或处理反爬机制，配置好 Playwright。 
        *Install standard libraries. If dynamic web scraping or anti-bot handling is required, prepare Playwright.*
*   **网络路由与低延迟优化 / Network Routing & Low-Latency Optimization:**
    *   **底层代理配置 / Base-level Proxy Settings:** 大模型的 API 调用和港股新闻抓取对网络连通性要求极高。需要在系统层面（如 Clash Core 路由规则）配置代理，确保 Python 脚本走低延迟节点，防止超时或丢包。 
        *LLM API calls and HK stock news scraping demand high connectivity. Configure OS-level proxies (e.g., Clash routing rules) to ensure Python scripts route through low-latency nodes, preventing timeouts or packet loss.*
    *   **代码级接管 / Code-level Takeover:** 在代码中通过 `proxies` 参数或全局环境变量精确接管网络请求。 
        *Intercept network requests in the code explicitly using `proxies` parameters or global environment variables.*

#### **第二阶段：感知层（数据收割机）开发 / Phase 2: Perception Layer (Data Harvester) Development**
> *编写一个定时任务脚本，专门负责为 DeepSeek 收集决策“弹药”。*
> *Write a scheduled task script dedicated to gathering decision-making "ammunition" for DeepSeek.*

*   **确定标的白名单（硬性过滤） / Target Whitelist (Hard Filtering):**
    *   在代码顶部写死常量：`TARGET_POOL = ["0700.HK", "3690.HK", "9988.HK"]`。绝不允许脚本处理名单之外的老千股或低流动性标的。 
        *Hardcode a constant at the top. Strictly prohibit the script from processing illiquid or "penny" stocks outside this list.*
*   **结构化量价获取（脏数据清洗） / Structured Price-Volume Acquisition (Dirty Data Cleaning):**
    *   使用 AkShare 接口获取最新的日线或 60 分钟级 K 线数据。**必须强制获取前复权数据（`adjust="qfq"`）**，避免因分红派息或拆股导致 K 线出现“暴跌”缺口，引发大模型恐慌性误判。
        *Fetch the latest daily or 60-minute K-line data using the AkShare API. **Mandatory: Fetch forward-adjusted data (`adjust="qfq"`)** to prevent "flash crash" gaps caused by dividends or stock splits, which would trigger panic misjudgments from the LLM.*
    *   **处理午休断层 (Lunch Break Gap Handling):** 港股在 12:00 - 13:00休市。在计算 60 分钟级别的 MACD 或均线时，必须在代码里对时间轴进行对齐和填补，过滤非交易时间段的空值，防止技术指标偏移。
        *HK stocks break from 12:00 to 13:00. When calculating 60-minute MACD or moving averages, the time axis must be aligned and padded in the code to filter out null values during non-trading hours, preventing technical indicator drift.*
    *   使用 Pandas 高效计算基础指标（如 RSI 相对强弱指标、MACD、均线乖离率）。 
        *Use Pandas to efficiently calculate fundamental indicators (e.g., RSI, MACD, Moving Average Bias).*
*   **非结构化情绪采集（突破反爬）/ Unstructured Sentiment Scraping (Bypassing Anti-bot):**
    *   **定向抓取 / Targeted Scraping:** 抓取财联社电报、雪球个股页面的最新前 10 条高赞评论或新闻标题。 
        *Scrape the top 10 most liked comments or latest news headlines from sources like Cailianpress telegraphs or Xueqiu individual stock pages.*
    *   **静态/动态休眠 / Sleep randomization:** 加入随机 User-Agent，并在请求间增加随机休眠机制（`time.sleep(random.uniform(2, 5))`）以防封 IP。 
        *Insert randomized User-Agents and sleep mechanisms between requests to prevent IP bans.*

#### **第三阶段：决策层（DeepSeek 外脑对接） / Phase 3: Decision Layer (DeepSeek Brain Integration)**
> *这是核心灵魂。必须通过严格的提示词工程（Prompt Engineering）死死按住大模型的“幻觉”。*
> *This is the core soul. Strict Prompt Engineering must be utilized to firmly suppress LLM "hallucinations".*

*   **组装系统级提示词 / Assemble System-Level Prompts:**
    *   明确 DeepSeek 的角色设定、输入数据格式以及严格的输出规范。要求它仅输出标准 JSON 格式。 
        *Clearly define DeepSeek's role, input data structure, and strict output rules. Mandate it to output exclusively in standard JSON format.*
*   **容错处理（防崩溃机制） / Fault Tolerance (Crash-Prevention Mechanism):**
    *   **DeepSeek-R1 特殊解析 (DeepSeek-R1 Specific Parsing):** R1 推理模型会输出 `<think>...</think>` 标签包裹的思维链（Chain of Thought）。必须在进入 JSON 解析器之前，使用正则表达式（Regex）剔除 `<think>` 标签及其内部内容，或定向提取 ` ```json ` 包裹的核心代码块，否则 `json.loads()` 必将崩溃。
        *The R1 reasoning model outputs a Chain of Thought wrapped in `<think>...</think>` tags. Before entering the JSON parser, use Regex to strip the `<think>` tags and their contents, or specifically extract the core code block wrapped in ` ```json `, otherwise `json.loads()` will crash.*
    *   **强类型解析 / Strongly Typed Parsing:** 引入 Pydantic 或严格的 `try...except json.loads` 应对大模型的格式抽风（如多返回了 markdown 反引号或逗号）。 
        *Introduce Pydantic or strict JSON loading exceptions to handle LLM format anomalies (e.g., rogue markdown backticks or trailing commas).*
    *   **回退逻辑 / Fallback Logic:** 核心防线：若连续 3 次 API 失败或 JSON 解析报错，默认输出 `{"action": "HOLD", "reason": "API_ERROR"}`，绝不可盲目买入。 
        *Core defense: If 3 consecutive API requests or JSON parsing attempts fail, fallback to a strict HOLD action. Blind buying is strictly forbidden.*

#### **第四阶段：执行层（硬风控与双重副驾驶） / Phase 4: Execution Layer (Hard Risk Control & Dual Co-pilot)**
> *全自动不是保障，写死在本地代码里的风控才是生命线。*
> *Full automation is not a guarantee; risk controls hardcoded into local logic are the true lifeline.*

*   **拦截器机制 / Interceptor Mechanism:**
    *   收到 DeepSeek 的 `BUY` 指令后，代码执行本地双重验证。 
        *Upon receiving a `BUY` directive from DeepSeek, execute a local dual-verification process.*
    *   **防御范例 / Defense Example:** `if deepseek_action == 'BUY' and local_rsi < 70 and current_drawdown < 0.08:` 只有外部 AI 指令和本地硬指标同时满足，信号放行。 
        *Signal is approved ONLY if external AI directives and local hard metrics align simultaneously.*
*   **仓位与动态止盈止损 / Position Sizing & Dynamic Take-Profit/Stop-Loss:**
    *   **暴露上限 / Exposure Limit:** 单次买入建议股数的总价值，绝不允许超过账户模拟总资金的 10%。 
        *The total value of a single suggested buy volume must NEVER exceed 10% of the simulated total account capital.*
    *   **硬止损警报 / Hard Stop-Loss Alert:** 强制记录成本价，若现价低于买入成本 8%，立即无视模型判断，触发本地 `SELL_ALL` 警报。 
        *Mandatorily record the cost price. If the current price drops 8% below the cost, immediately ignore the LLM and trigger a local `SELL_ALL` alert.*
    *   **动态移动止损 (Trailing Stop - Profit Protection):** 当持仓盈利超过 10% 后，自动激活移动止损机制。一旦价格从最高点回撤超过 5%，立即触发 `SELL_ALL` 警报，防止利润“过山车”。
        *When absolute position profit exceeds 10%, automatically activate a trailing stop mechanism. If the price retraces more than 5% from its highest point, immediately trigger a `SELL_ALL` alert to prevent a profit "rollercoaster".*

#### **第五阶段：“半自动”可视化监控中心 / Phase 5: "Semi-Auto" Visual Monitoring Center**
> *在实盘初期建立信任感，你需要一个能“先看后下单”的直观界面。*
> *To establish trust in the early stages of live trading, an intuitive "look before you trade" interface is required.*

*   **赛博朋克风格透明 HUD / Cyberpunk Style Transparent HUD:**
    *   使用 Tkinter 编写极简 GUI：无边框（`overrideredirect(True)`）、透明度（`attributes('-alpha', 0.8)`）、置顶（`attributes('-topmost', True)`）。 
        *Create a minimalist Tkinter GUI: borderless, transparent, and always-on-top.*
    *   如同监控插件悬浮于屏幕边缘，实时滚动刷新网络延迟，出现交易信号时高亮闪烁。 
        *Floating on the screen edge like a monitoring widget, scrolling real-time network latency, and flashing bright alerts upon detecting valid trading signals.*
*   **多渠道消息推送 / Multi-channel Message Push:**
    *   除了桌面端，集成 Server酱或 Telegram Bot 的 Webhook，将包含 `{"标的", "动作", "DeepSeek推理逻辑"}` 的卡片推送到手机。 
        *Integrate webhooks (like ServerChan or Telegram Bot) to push data cards containing `{"Target", "Action", "DeepSeek Reasoning"}` to your smartphone.*
    *   **最终裁决 / Final Verdict:** 由你完成最后一步：打开券商 App 点击下单。 
        *You are the final adjudicator: opening the broker App to manually execute the trade.*

#### **第六阶段：MVP 沙盒回测（Time Machine 验证）/ Phase 6: MVP Sandbox Backtesting (Time Machine Validation)**
> *在运行实盘前，必须通过数据回放跑通全链路。*
> *The entire pipeline must be stress-tested via data replay before going live.*

*   **时光机脚本 / Time Machine Script:**
    *   编写专属的 `backtest.py` 脚本，将系统时间拨回 2025 年初。 
        *Write a dedicated `backtest.py` script to dial the system clock back to early 2025.*
*   **闭环验证 / Closed-Loop Validation:**
    *   **重构 Prompt / Reconstruct Prompts:** 按天读取历史量价数据和历史新闻，组装喂给 DeepSeek。 
        *Iteratively read historical price-volume and news data day-by-day, feeding the assembled Prompts to DeepSeek.*
    *   **净值曲线计算 / Net Asset Value (NAV) Calculation:** 记录所有虚拟买卖流水，扣除印花税与双边佣金，绘制净值曲线图，对比其是否能够跑赢恒生指数 (HSI) 基准。 
        *Record all virtual transactions, deduct stamp duties and bilateral commissions, and plot the NAV curve to benchmark against the Hang Seng Index (HSI).*
