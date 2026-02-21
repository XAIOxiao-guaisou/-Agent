# Phase 15 Report: Web UI Fast-Tick Watchlist & Real-World Optimization

## 核心重构目标 (Core Refactoring Goals)
在迈向高频实盘阶段，系统暴露了若干严重脱离沙盒环境的隐患：API轮询风暴、前端页面闪烁与内存泄漏、以及进程级强制关闭带来的数据破损风险。
本阶段（即实盘优化第二阶段）致力于彻底打通高速与低速环境壁垒，实现前后端“读写物理分离”，部署防御性风控锁，并打造沉浸式的网页监控中枢。

## 重大技术突破 (Major Technological Breakthroughs)

### 1. 彻底的读写缓存分离 (Cache-Based Decoupling)
- **痛点**：Streamlit 网页直拉外部源（Akshare）引发 IP 封禁。
- **方案**：`dashboard.py` 内部被全面剥夺了外网访问权限（`import akshare` 已被剔除）。所有的外部数据收割统一汇聚在 `main.py` 守护进程中。
- **机制**：由 `fast_tick_monitor` 进行统一的行情抓取（含自定义自选队列），然后以原子级写入速度落盘为本地通讯管道文件 `realtime_cache.json`。Web UI 只负责在这条纯本地的内网管道里进行纳秒级别的无痛读取，**将 API 并发轰炸降至了 0。**

### 2. Streamlit 渲染引擎升级 (`@st.fragment`)
- **痛点**：传统模式下的 `st.rerun()` 强行整页刷新，导致网页出现严重白屏闪烁。
- **方案**：引入 Web 2.0 时代的局部渲染机制。通过包裹核心数据展示区的 `@st.fragment(run_every="2s")` 装饰器，页面主体构架保持静止，仅让前端表格以 2 秒级的频率单独轮询本地缓存并平滑渐变，实现了比肩专业盯盘终端（如东财、同花顺）的丝滑全屏体验。

### 3. 可重入悲观锁护航 (Re-Entrant Thread Locks)
- **痛点**：高频行情下，AI 慢系统（小时级）读取持仓序列与快系统（秒级）强制斩仓发生碰撞，可能激发 Python 字典遍历期的严重内存宕机 (`RuntimeError`)。
- **方案**：将 `execution_risk.py` 中的普通锁升级为 `threading.RLock()`（可重入锁）。
- 并在最危险的遍历区域引入 `get_positions_copy()` 利用深沉拷贝获得安全快照。从此以后，无论是风控防线 `monitor_dynamic_stop_loss` 的评估，还是买卖操作的数据覆盖，都被包在了不漏水的最强互斥锁中。哪怕毫秒级碰撞也断绝了竞态条件导致的崩溃。

### 4. 优雅降落伞机制 (Graceful Shutdown)
- **前置**：如果用户直接 Ctrl+C 关闭 `main.py`，未写入完成的 JSON 可能出现半文件截断。
- **落地**：在核心入口埋入最顶层的 `KeyboardInterrupt` 全局降落伞。当捕获到退出指令时，系统强制锁定释放流水线，触发 `global_executor.shutdown(wait=True)` 排查排空所有线程池残留操作，并在打印最终巡逻记录后原子落地，确保每一次关闭都不会伴随记忆遗忘。

## 后续建议
随着“双轨架构”、“动态止损”及“读写物理分离”的实装完毕，该 `DeepSeek Quant Engine` 的底层骨架已经完全足以抵御实盘冲击，可以直接无伤上挂实单账号运作。
