import time
import schedule
from threading import Thread
import datetime
import subprocess
import concurrent.futures
from debug_sentinel import log_info, log_error, log_warn

# 引入我们打磨好的所有模块并屏蔽 IDE 环境尚未识别到的本地包爆红 (Suppress IDE import false-alarms)
from config import setup_global_proxy  # type: ignore
from data_harvester import TARGET_POOL, fetch_and_clean_kline_data, fetch_sentiment_news  # type: ignore
from deepseek_brain import ask_deepseek  # type: ignore
from execution_risk import LocalRiskController  # type: ignore
from monitor_hud import CyberpunkHUD, send_mobile_notification  # type: ignore

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

def single_target_cycle(symbol: str, risk_sys: LocalRiskController, hud: CyberpunkHUD):
    """单只股票的 [感知 -> 思考 -> 风控执行] 完整生命周期"""
    hud.update_status(symbol, "SCANNING...")
    
    # 1. 并发启动感知层获取 K线数据 和 新闻情绪数据 (Parallelized network fetching to halve latency)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        kline_future = executor.submit(fetch_and_clean_kline_data, symbol, "60")
        news_future = executor.submit(fetch_sentiment_news, symbol)
        
        df = kline_future.result()
        news_list = news_future.result()
        
    if df is None or df.empty: 
        return
        
    current_price = df.iloc[-1]['收盘']
    current_rsi = df.iloc[-1]['RSI_14']
    
    # 2. 风控前置：检查是否触发割肉/止盈警报
    if risk_sys.monitor_dynamic_stop_loss(symbol, current_price):
        hud.update_status(symbol, "SELL_ALL")
        send_mobile_notification(symbol, "SELL_ALL", f"触发本地风控止损/止盈防线！现价: {current_price}")
        risk_sys.mock_sell_all(symbol)
        return

    # 从并发获取的结果中提取数据
    market_data_snapshot = {
        "current_price": current_price,
        "RSI_14": current_rsi,
        "MACD_HIST": df.iloc[-1]['MACD_HIST']
    }

    # 3. 呼叫 DeepSeek 决策大脑
    # 为了防止网络抖动，计算时间较长
    start_time = time.time()
    ai_decision = ask_deepseek(symbol, market_data_snapshot, news_list)
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

def run_schedule_loop(hud: CyberpunkHUD):
    """后台定时任务循环"""
    risk_sys = LocalRiskController(initial_capital=100000.0)
    
    def job():
        # 如果不在交易时间，直接跳过 (实盘解除此注释)
        if not is_trading_time(): 
            log_info(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 当前非交易时间，跳过全盘扫描。")
            return
           
        log_info(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> 开启新一轮全盘并发扫描 (MAX_THREADS) <<<")
        
        # 利用线程池进行高并发处理 (Concurrent processing utilizing ThreadPoolExecutor)
        # 默认最大工作线程数为 CPU 核心数 + 4，这里根据 TARGET_POOL 数量动态自适应
        cpu_cores = os.cpu_count()
        cpu_cores = cpu_cores if cpu_cores is not None else 4
        max_workers = min(len(TARGET_POOL) or 1, cpu_cores + 4)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有的独立标的任务到线程池 (Submit all independent symbol tasks)
            futures = [executor.submit(single_target_cycle, symbol, risk_sys, hud) for symbol in TARGET_POOL] # type: ignore
            
            # 等待所有猎物扫描完毕 (Wait for all scanning tasks to finish)
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
    setup_global_proxy()
    
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

    # 实例化赛博朋克 HUD (桌面右上角弹窗版)
    hud = CyberpunkHUD()
    
    # 将核心爬虫与决策逻辑放入独立守护线程，不卡死 UI
    log_info("[*] 正在点火后台并发调度守护进程 (Daemon Thread)...")
    worker_thread = Thread(target=run_schedule_loop, args=(hud,), daemon=True)
    worker_thread.start()
    
    # 启动 GUI 主循环 (挂靠主线程)
    hud.start()
