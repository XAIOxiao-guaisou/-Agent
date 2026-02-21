import akshare as ak # type: ignore
import pandas as pd # type: ignore
import datetime
import time
import os
import json
import matplotlib.pyplot as plt # type: ignore
import matplotlib.colors as mcolors # type: ignore
from tqdm import tqdm # type: ignore
# from config import setup_global_proxy # type: ignore  # 调试阶段注释掉代理，防止报错

# ==========================================
# 量化选股雷达: 7日动量与异动扫描系统 (Phase 17)
# ==========================================

# 设置中文字体，防止图表乱码 (Windows常用SimHei，Mac常用Arial Unicode MS)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def get_top_liquid_stocks(top_n=100) -> pd.DataFrame:
    """第一层漏斗：获取全市场成交额最大的 Top N 港股，剔除老千股"""
    print("[*] 正在拉取全市场快照，进行流动性初筛...")
    df_spot = ak.stock_hk_spot_em()
    
    # 调优一：流动性漏斗的“仙股”漏洞
    # 确保数据格式正确，剔除没有成交额的死水股，并且价格必须大于等于 1.0 港币
    df_spot = df_spot[(df_spot['成交额'] > 0) & (df_spot['最新价'] >= 1.0)]
    df_spot = df_spot.sort_values(by='成交额', ascending=False).head(top_n)
    return df_spot[['代码', '名称', '最新价', '成交额']]

def calculate_stock_indicators(symbol: str, retries=3):
    """第二层漏斗：拉取个股日线，计算 7 日看好指标，带有API熔断保护"""
    for attempt in range(retries):
        try:
            # 调优二：拉取过去 60 天的日线前复权数据（留足计算 RSI 的预热空间）
            df = ak.stock_hk_hist(symbol=symbol, period="daily", adjust="qfq")
            
            # 调优一：停牌股与次新股物理隔离
            if df is None or len(df) < 30:
                return None
                
            df['日期'] = pd.to_datetime(df['日期'])
            df.set_index('日期', inplace=True)
            
            # 检查最后一条数据是否是最近的 (排除长期停牌)
            last_date = df.index[-1]
            if (datetime.datetime.now() - last_date).days > 5:
                # 容忍周末加上一点假期的天数，超过5天没交易则认为停牌
                return None
            
            # 1. 计算 7 日累计涨幅 (7-Day Momentum)
            # 取最近的一天和 7 个交易日之前的那天
            close_now = df['收盘'].iloc[-1]
            close_7d_ago = df['收盘'].iloc[-8]
            momentum_7d = ((close_now - close_7d_ago) / close_7d_ago) * 100
            
            # 2. 计算 RSI_14 (使用 60 天预热，确保极其平滑)
            delta = df['收盘'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean() # 真正的金融系统一般用 EMA，这里用 rolling mean 简化，但 60 天依然能过滤噪音
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_14 = 100 - (100 / (1 + rs))
            current_rsi = rsi_14.iloc[-1]
            
            # 3. 计算放量比例 (近期3天均量 / 前7天均量)
            vol_recent_3d = df['成交量'].iloc[-3:].mean()
            vol_prev_7d = df['成交量'].iloc[-10:-3].mean()
            volume_ratio = vol_recent_3d / vol_prev_7d if vol_prev_7d > 0 else 1.0

            return {
                "7日涨幅(%)": round(momentum_7d, 2),
                "RSI_14": round(current_rsi, 2),
                "放量比": round(volume_ratio, 2)
            }
        except Exception as e:
            # 调优二：API 熔断与动态退避
            if attempt < retries - 1:
                time.sleep(3) # 强制休眠退避
            else:
                return None

def run_scanner():
    """执行全盘扫描"""
    # 1. 获取流动性 Top 100
    liquid_stocks = get_top_liquid_stocks(100)
    
    results = []
    print(f"[*] 开始对 Top 100 活跃港股进行 60日深度数据溯源与计算...")
    
    # 使用 tqdm 显示进度条
    for index, row in tqdm(liquid_stocks.iterrows(), total=len(liquid_stocks)):
        symbol = str(row['代码'])
        name = str(row['名称'])
        
        indicators = calculate_stock_indicators(symbol)
        if indicators:
            # 第三层漏斗：过滤掉 RSI 严重超买 (>75) 或者处于严重下跌趋势 (<0 放量下跌) 的股票
            if indicators["RSI_14"] < 75 and indicators["RSI_14"] > 0: 
                # 调优一：量纲归一化
                score = (indicators["7日涨幅(%)"] * 1.0) + (indicators["放量比"] * 5.0)
                res = {
                    "代码": symbol,
                    "名称": name,
                    "最新价": row['最新价'],
                    "综合看好得分": round(score, 2)
                }
                res.update(indicators)
                results.append(res)
                
        # 保护 API，防止封禁
        time.sleep(0.3)
        
    # 转换为 DataFrame
    df_results = pd.DataFrame(results)
    
    if df_results.empty:
        return df_results
        
    # 提取 Top 20
    df_top20 = df_results.sort_values(by="综合看好得分", ascending=False).head(20)
    return df_top20

def plot_top_20(df_top20):
    """绘制 Top 20 潜力股指标图"""
    print("[*] 正在生成 Top 20 分析图表...")
    
    # 倒序排列以便在水平柱状图中得分高的在最上面
    df_plot = df_top20.sort_values(by="综合看好得分", ascending=True).copy()
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # 创建渐变颜色（得分越高颜色越暖）
    norm = mcolors.Normalize(vmin=df_plot['综合看好得分'].min(), vmax=df_plot['综合看好得分'].max())
    cmap = plt.get_cmap('RdYlGn_r') # 红-黄-绿反转 (红色代表涨/高分)
    
    bars = ax.barh(df_plot['名称'] + " (" + df_plot['代码'] + ")", 
                   df_plot['综合看好得分'], 
                   color=cmap(norm(df_plot['综合看好得分'])))
    
    # 在柱子旁边写上具体的数据 (涨幅和放量比)
    for bar, (_, row) in zip(bars, df_plot.iterrows()):
        text = f" 涨幅:{row['7日涨幅(%)']}% | RSI:{row['RSI_14']} | 放量:{row['放量比']}x"
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2, text, 
                va='center', ha='left', fontsize=9, color='white' if plt.rcParams['axes.facecolor'] == 'black' else 'black')

    # 图表美化
    ax.set_title(f"港股 Top 20 综合看好潜力榜 (基于7日动量与量价共振)\n生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", fontsize=16, pad=20)
    ax.set_xlabel('综合看好得分 (Momentum & Volume Score)', fontsize=12)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    # 紧凑布局并保存
    plt.tight_layout()
    save_path = "top20_promising_stocks.png"
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"[+] 图表已成功保存至当前目录: {save_path}")
    
    # 将 Top 20 数据导出为 CSV 备查
    df_top20.to_csv("top20_promising_stocks.csv", index=False, encoding="utf-8-sig")
    print(f"[+] 数据表已成功导出为: top20_promising_stocks.csv")

def atomic_inject_watchlist(df_top20):
    """调优三：IPC 通信的原子化写入"""
    top5_symbols = df_top20.head(5)['代码'].tolist()
    # 格式化港股代码补充后缀
    formatted_symbols = [sym + ".HK" if not sym.endswith(".HK") else sym for sym in top5_symbols]
    
    tmp_file = "watchlist.json.tmp"
    tgt_file = "watchlist.json"
    
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(formatted_symbols, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, tgt_file)
        print(f"[+] 已经成功以原子化方式将 Top 5 猎物灌入系统后台白名单箱 ({tgt_file})！")
    except Exception as e:
        print(f"[-] 写入 watchlist 失败: {e}")

def scheduled_job():
    """Unattended scheduled execution (no interactive prompts)"""
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{ts}] Timed trigger! Running post-close stock screener...")
    top20_data = run_scanner()
    if not top20_data.empty:
        print(top20_data[['\u540d\u79f0', '\u4ee3\u7801', '7\u65e5\u6da8\u5e45(%)', 'RSI_14', '\u653e\u91cf\u6bd4', '\u7efc\u5408\u770b\u597d\u5f97\u5206']].head(5))
        plot_top_20(top20_data)
        atomic_inject_watchlist(top20_data)  # auto-inject, no prompt
        print("[+] Scheduled scan done. Top 5 auto-injected into watchlist.json.")
    else:
        print("[-] No qualifying stocks found. Market may be closed or network error.")

if __name__ == "__main__":
    import sys
    is_schedule_mode = "--schedule" in sys.argv

    print("="*60)
    print("DeepSeek Quant Market Scanner")
    if is_schedule_mode:
        print("Mode: Daily Timed Daemon  (auto-scan every weekday at 16:18)")
    else:
        print("Mode: Single-Shot Interactive Scan")
    print("="*60)

    if is_schedule_mode:
        import schedule as _sch  # type: ignore
        SCAN_TIME = "16:18"
        for _day in [_sch.every().monday, _sch.every().tuesday, _sch.every().wednesday,
                     _sch.every().thursday, _sch.every().friday]:
            _day.at(SCAN_TIME).do(scheduled_job)
        print(f"[*] Daemon started! Will scan every weekday at {SCAN_TIME}. Press Ctrl+C to exit.")
        while True:
            _sch.run_pending()
            time.sleep(30)
    else:
        # Interactive single-shot mode
        top20_data = run_scanner()
        if not top20_data.empty:
            print(top20_data[['\u540d\u79f0', '\u4ee3\u7801', '7\u65e5\u6da8\u5e45(%)', 'RSI_14', '\u653e\u91cf\u6bd4', '\u7efc\u5408\u770b\u597d\u5f97\u5206']].head(5))
            plot_top_20(top20_data)
            ans = input("\n[?] Auto-inject Top 5 into watchlist.json for live radar? (Y/Enter=Yes / N): ")
            if ans.upper() in ["Y", "", "YES"]:
                atomic_inject_watchlist(top20_data)
                print("[+] Closed-loop complete. Live radar is now tracking Top 5.")
        else:
            print("[-] No qualifying stocks found.")


