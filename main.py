import time
import schedule
from threading import Thread
import datetime

# 引入我们打磨好的所有模块
from config import setup_global_proxy
from data_harvester import TARGET_POOL, fetch_and_clean_kline_data, fetch_sentiment_news
from deepseek_brain import ask_deepseek
from execution_risk import LocalRiskController
from monitor_hud import CyberpunkHUD, send_mobile_notification

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
    
    # 1. 启动感知层获取数据
    df = fetch_and_clean_kline_data(symbol, period="60")
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

    # 获取市场新闻弹药
    news_list = fetch_sentiment_news(symbol)
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
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 当前非交易时间，跳过全盘扫描。")
            return
           
        print(f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] >>> 开启新一轮全盘扫描 <<<")
        for symbol in TARGET_POOL:
            single_target_cycle(symbol, risk_sys, hud)
            time.sleep(3) # 缓冲间隔，防封禁

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
    setup_global_proxy()
    
    # 实例化赛博朋克 UI
    hud = CyberpunkHUD()
    
    # 将核心爬虫与决策逻辑放入独立守护线程，不卡死 UI
    worker_thread = Thread(target=run_schedule_loop, args=(hud,), daemon=True)
    worker_thread.start()
    
    # 启动 UI 主循环
    hud.start()
