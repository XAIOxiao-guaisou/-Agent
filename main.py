import time
import schedule # type: ignore
from threading import Thread
import datetime
import subprocess
import concurrent.futures
import json
import os
from debug_sentinel import log_info, log_error, log_warn # type: ignore

# 引入我们打磨好的所有模块并屏蔽 IDE 环境尚未识别到的本地包爆红 (Suppress IDE import false-alarms)
from config import setup_global_proxy  # type: ignore
import akshare as ak # type: ignore
from data_harvester import TARGET_POOL, fetch_and_clean_kline_data, fetch_multi_dim_intelligence  # type: ignore
from deepseek_brain import ask_deepseek  # type: ignore
from execution_risk import LocalRiskController  # type: ignore
from monitor_hud import CyberpunkRadarHUD, send_mobile_notification  # type: ignore

# ==========================================
# Phase 7: Main Daemon (总线调度器)
# ==========================================

def is_trading_time() -> bool:
    """粗略判断是否在港股交易时间段 (简化版: 工作日 09:30-16:00)"""
    now = datetime.datetime.now()
    if now.weekday() >= 5: return False # 周末不交易
    current_time = now.time()
    return (datetime.time(9, 30) <= current_time <= datetime.time(12, 0)) or \
           (datetime.time(13, 0) <= current_time <= datetime.time(16, 0))

def single_target_cycle(symbol: str, risk_sys: LocalRiskController, hud: CyberpunkRadarHUD):
    """单只股票的 [感知 -> 思考 -> 风控执行] 完整生命周期"""
    hud.update_status(symbol, "SCANNING...")
    
    # 1. 并发启动感知层获取 K线数据 和 新闻情绪数据 (Parallelized network fetching to halve latency)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        kline_future = executor.submit(fetch_and_clean_kline_data, symbol, "60")
        intell_future = executor.submit(fetch_multi_dim_intelligence, symbol)
        
        df = kline_future.result()
        intelligence_dict = intell_future.result()
        
    if df is None or df.empty: # type: ignore
        return
    
    # 向 IDE 声明 df 此时绝对不为 None，消除报警
    assert df is not None 

    current_price = float(df.iloc[-1]['收盘']) # type: ignore
    current_rsi = float(df.iloc[-1]['RSI_14']) # type: ignore
    macd_hist = float(df.iloc[-1]['MACD_HIST']) # type: ignore
    
    # 2. 风控前置：检查是否触发割肉/止盈警报
    if risk_sys.monitor_dynamic_stop_loss(symbol, current_price):
        hud.update_status(symbol, "SELL_ALL")
        send_mobile_notification(symbol, "SELL_ALL", f"触发本地风控止损/止盈防线！现价: {current_price}")
        risk_sys.mock_sell_all(symbol)
        
        # 如果从深层拷贝中读写字典
        return

    # 从并发获取的结果中提取数据
    market_data_snapshot = {
        "current_price": current_price,
        "RSI_14": current_rsi,
        "MACD_HIST": macd_hist
    }

    # 3. 呼叫 DeepSeek 决策大脑
    # 为了防止网络抖动，计算时间较长
    start_time = time.time()
    ai_decision = ask_deepseek(symbol, market_data_snapshot, intelligence_dict)
    latency_ms = int((time.time() - start_time) * 1000)
    hud.update_network_latency(latency_ms)

    # 4. 执行层：本地双重副驾驶审核
    final_decision = risk_sys.dual_copilot_interceptor(symbol, ai_decision, current_price, current_rsi)
    action = final_decision["action"]
    
    # 5. 更新 UI 与手机推送
    hud.update_status(symbol, action)
    if action == "BUY":
        vol = final_decision.get("suggested_volume", 0)
        risk_sys.mock_buy(symbol, current_price, vol)
        send_mobile_notification(symbol, f"BUY ({vol}股)", final_decision.get("reason", ""))
    elif action == "SELL":
        risk_sys.mock_sell_all(symbol)
        send_mobile_notification(symbol, "SELL", final_decision.get("reason", ""))

def fast_tick_monitor(hud: CyberpunkRadarHUD, risk_sys: LocalRiskController):
    """
    高频价格雷达 (Fast Tick Radar)
    每 10 秒扫描一次白名单标的，越过大模型直接触发本地硬风控防线。
    将拉取结果写入 realtime_cache.json 供前端零延迟读取。
    """
    targets_for_hud = TARGET_POOL[:4] # 严格限制最多观测 4 支
    hud.register_symbols(targets_for_hud) # 初始化 UI 槽位
    
    while True:
        # 调试阶段强制放行：注释掉安全锁，方便在非交易时间查看真实数据流动
        # if not is_trading_time():
        #     time.sleep(60)
        #     continue
            
        try:
            # 读取前端自定义的 watchlist
            watchlist = []
            if os.path.exists("watchlist.json"):
                try:
                    with open("watchlist.json", "r", encoding="utf-8") as f:
                        watchlist = json.load(f)
                except Exception:
                    pass
            
            # 合并所有需要监控的标的 (去重)
            all_targets = list(set(TARGET_POOL + watchlist))
            
            # 获取东财全市场实时快照 (极速轻量接口)
            spot_df = ak.stock_hk_spot_em()
            spot_df['代码'] = spot_df['代码'].astype(str)
            
            cache_data = {}
            for symbol in all_targets:
                clean_sym = symbol.replace(".HK", "")
                match = spot_df[spot_df['代码'] == clean_sym]
                
                if not match.empty:
                    current_price = float(match.iloc[0]['最新价'])
                    pct_change = float(match.iloc[0]['涨跌幅'])
                    
                    # 保存到缓存结构中供 Web UI 读取
                    cache_data[symbol] = {"price": current_price, "pct": pct_change}
                    
                    # 如果是前4大核心标的，刷新桌面雷达 UI 和风控心跳
                    if symbol in targets_for_hud:
                        hud.update_tick(symbol, current_price, pct_change)
                        
                        # 毫秒级风控心跳：立刻计算是否触发了 8% 割肉或移动止盈
                        # 安全获取一份深拷贝的 positions 用于迭代判断
                        safe_positions = risk_sys.get_positions_copy()
                        if symbol in safe_positions:
                            if risk_sys.monitor_dynamic_stop_loss(symbol, current_price):
                                hud.update_status(symbol, "SELL_ALL")
                                send_mobile_notification(symbol, "SELL_ALL", f"急速雷达极速防线触发！现价: {current_price}")
                                risk_sys.mock_sell_all(symbol) # 本地落盘清仓
                                
            # 将多维度行情原子写入到本地缓存文件 
            tmp_cache = "realtime_cache.json.tmp"
            with open(tmp_cache, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_cache, "realtime_cache.json")
            
        except Exception as e:
            # 不死鸟机制：捕获网络抖动，防止监控主线程崩溃
            log_error(f"[-] 高频雷达网络抖动拦截成功: {e}")
            
        time.sleep(10) # 10 秒轮询一次，保护 IP 且满足实盘监控需求

# 维护全局 ThreadPool 对象以便优雅退出
global_executor = None

def run_schedule_loop(hud: CyberpunkRadarHUD, risk_sys: LocalRiskController):
    """后台定时任务慢速 AI 思考循环"""
    global global_executor
    
    def job():
        # 【脱离沙盘 1】恢复交易时间锁 (Trading Hours Guard - Production)
        if not is_trading_time(): 
            log_info(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 当前非交易时间，全盘扫描进入休眠。")
            return

        # 【脱离沙盘 2】动态构建真实猎杀名单合并硬编码与 Web UI 传入的动态标的
        active_targets = list(TARGET_POOL)
        if os.path.exists("watchlist.json"):
            try:
                with open("watchlist.json", "r", encoding="utf-8") as f:
                    user_watchlist = json.load(f)
                    if isinstance(user_watchlist, list):
                        active_targets.extend(user_watchlist)
            except Exception:
                pass
        # 去重，防止重复扫描
        active_targets = list(set(active_targets))

        log_info(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> 开启全盘并发扫描 (总索敌数量: {len(active_targets)}) <<<")

        # ThreadPool 并发管理 (根据建议调整为保守策略)
        max_workers = 2  # 保持并发数量防止 API 并发超限

        global global_executor
        global_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

        with global_executor as executor:
            # 【脱离沙盘 3】让 AI 真正分析所有自定义标的，而不仅仅是前 4 支！
            futures = [executor.submit(single_target_cycle, symbol, risk_sys, hud) for symbol in active_targets]  # type: ignore
            concurrent.futures.wait(futures)

        log_info("[+] 本轮全盘并发扫描已结束，系统进入休眠等待下一班车。")


    # 摒弃简单的轮询，改为硬编码的精准定时触发 (Precision Market Scheduling)
    # 紧贴 AkShare 60 分钟 K 线的收线时间进行触发，留出 2 分钟让数据落位
    # Follow the 60-min K-line close time with a 2-min buffer for data arrival.
    trade_times = ["10:32", "11:32", "14:02", "15:02", "15:55"]
    for t in trade_times:
        schedule.every().day.at(t).do(job)
        print(f"[*] 已设定定时扫描任务: {t}")
    
    # 启动时立刻强行跑一次，用于测试连通性
    job() 
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    import os # Add missing os import for cpu_count
    # setup_global_proxy() # 调试阶段注释掉代理，防止报错
    
    # 自动拉起 Streamlit Web UI 监控中心 (Auto-launch Streamlit Web UI)
    log_info("\n[+] 正在后台启动 Streamlit 赛博指挥中心...")
    try:
        # 使用 subprocess 从独立的虚拟环境进程启动 dashboard
        # stderr/stdout 定向到 DEVNULL 避免污染主控制台的输出
        subprocess.Popen(
            [r".\venv\Scripts\streamlit.exe", "run", "dashboard.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log_info("[+] Web UI 启动指令已发送! 您可以通过浏览器访问 http://localhost:8501 查看大屏。")
    except Exception as e:
        log_error(f"[-] Web UI 启动失败，请手动执行 `streamlit run dashboard.py`。报错: {e}")

    # 实例化赛博朋克 HUD 矩阵雷达
    hud = CyberpunkRadarHUD(max_slots=4)
    risk_sys = LocalRiskController(initial_capital=100000.0)
    
    # 包装全局退出逻辑
    try:
        # 线程 1: 启动高频急速监控雷达 (负责 10 秒级看盘与保命止损)
        log_info("[*] 正在点火后台 10秒级 高频防灾雷达守护进程 (Tick Daemon)...")
        tick_thread = Thread(target=fast_tick_monitor, args=(hud, risk_sys), daemon=True)
        tick_thread.start()
        
        # 线程 2: 启动慢速大模型思考调度 (负责小时级宏观分析与建仓)
        log_info("[*] 正在点火后台 小时级 并发思考守护进程 (Brain Daemon)...")
        ai_thread = Thread(target=run_schedule_loop, args=(hud, risk_sys), daemon=True)
        ai_thread.start()
        
        # 启动 GUI 主循环 (挂靠主线程)
        hud.start()
    except KeyboardInterrupt:
        log_warn("\n[!] 收到外界中断指令 (KeyboardInterrupt)！系统正在执行优雅退出流水线...")
    finally:
        # 优雅退出流：等待所有在途的订单和落盘逻辑执行完毕
        if global_executor is not None:
            log_info("[*] 正在关闭底层 ThreadPoolExecutor，等待所有任务排空...")
            global_executor.shutdown(wait=True)
        
        log_info("[*] 正在最后一次安全核对内存状态与硬盘状态...")
        risk_sys.save_positions()
        log_info("[+] 量化交易系统安全停机保护完成。主进程退出。")
