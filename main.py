import time
import schedule # type: ignore
from threading import Thread
import datetime
import subprocess
import concurrent.futures
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
    """
    targets = TARGET_POOL[:4] # 严格限制最多观测 4 支
    hud.register_symbols(targets) # 初始化 UI 槽位
    
    while True:
        # 实盘安全锁：非交易时间不进行高频请求防止东财 IP 封禁
        if not is_trading_time():
            time.sleep(60)
            continue
            
        try:
            # 获取东财全市场实时快照 (极速轻量接口)
            spot_df = ak.stock_hk_spot_em()
            spot_df['代码'] = spot_df['代码'].astype(str)
            
            for symbol in targets:
                clean_sym = symbol.replace(".HK", "")
                match = spot_df[spot_df['代码'] == clean_sym]
                
                if not match.empty:
                    current_price = float(match.iloc[0]['最新价'])
                    pct_change = float(match.iloc[0]['涨跌幅'])
                    
                    # 1. 刷新桌面雷达 UI
                    hud.update_tick(symbol, current_price, pct_change)
                    
                    # 2. 毫秒级风控心跳：立刻计算是否触发了 8% 割肉或移动止盈
                    if symbol in risk_sys.positions:
                        if risk_sys.monitor_dynamic_stop_loss(symbol, current_price):
                            hud.update_status(symbol, "SELL_ALL")
                            send_mobile_notification(symbol, "SELL_ALL", f"急速雷达极速防线触发！现价: {current_price}")
                            risk_sys.mock_sell_all(symbol) # 本地落盘清仓
                            
        except Exception as e:
            # 不死鸟机制：捕获网络抖动，防止监控主线程崩溃
            log_error(f"[-] 高频雷达网络抖动拦截成功: {e}")
            
        time.sleep(10) # 10 秒轮询一次，保护 IP 且满足实盘监控需求


def run_schedule_loop(hud: CyberpunkRadarHUD, risk_sys: LocalRiskController):
    """后台定时任务慢速 AI 思考循环"""
    
    def job():
        # 如果不在交易时间，直接跳过 (实盘解除此注释)
        if not is_trading_time(): 
            log_info(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 当前非交易时间，跳过全盘扫描。")
            return
           
        log_info(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> 开启新一轮全盘并发扫描 (MAX_THREADS) <<<")
        
        # ThreadPool 并发管理 (根据建议调整为保守策略)
        max_workers = 2 # 设定为保守并流，防止大模型 API Rate Limit
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有的独立标的任务到线程池 (限制为前4支以匹配雷达)
            futures = [executor.submit(single_target_cycle, symbol, risk_sys, hud) for symbol in TARGET_POOL[:4]] # type: ignore
            
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

    # 实例化赛博朋克 HUD 矩阵雷达
    hud = CyberpunkRadarHUD(max_slots=4)
    risk_sys = LocalRiskController(initial_capital=100000.0)
    
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
