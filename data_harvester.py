import pandas as pd
import akshare as ak
from base64 import b64encode
import datetime
import time
import random
from config import setup_global_proxy
from debug_sentinel import log_info, log_error, log_warn

# ==========================================
# Phase 2: Perception Layer (Data Harvester)
# ==========================================

# 1. 结构化量价引擎 (Structured Data Engine)
# ==========================================

# 硬编码白名单 (Hardcoded Whitelist)
# 绝不允许处理名单之外的标的 (Strictly prohibit processing symbols outside this list)
# 00700 (腾讯), 03690 (美团), 09988 (阿里)
TARGET_POOL = ["00700", "03690", "09988"] 

def fetch_and_clean_kline_data(symbol: str, period: str = "60") -> pd.DataFrame:
    """
    抓取并清洗指定股票的 K 线数据 (默认 60 分钟级别)
    """
    if symbol not in TARGET_POOL:
        raise ValueError(f"[!] 越权访问警告: {symbol} 不在 TARGET_POOL 白名单中！")

    log_info(f"[*] 正在拉取 {symbol} 的 {period} 分钟级别感知数据...")
    
    try:
        # 使用 AkShare 的 stock_hk_hist_min_em 接口获取港股分时行情数据 (东方财富数据源)
        # 必须强制带入 adjust="qfq" (前复权) 参数，防止分红派息导致的 K 线缺口
        # Mandatory adjust="qfq" to prevent flash-crash gaps from dividends
        df = ak.stock_hk_hist_min_em(symbol=symbol, period=period, adjust="qfq")
        
        # 将时间列转换为 datetime 对象，并设为索引
        df['时间'] = pd.to_datetime(df['时间'])
        df.set_index('时间', inplace=True)
        
        # 脏数据清洗：处理午休断层 (Lunch Break Gap Handling)
        # 港股交易时间段：09:30-12:00, 13:00-16:00
        # 如果是 60 分钟线，确保时间轴连续，避免指标偏移
        # 过滤掉非交易时间段的数据 (Filter out non-trading hours)
        df = df.between_time('09:30', '16:00')
        # 剔除 12:01 到 12:59 之间的午休幽灵数据 (如果有)
        # Exclude ghost data during lunch break (12:01 - 12:59)
        lunch_mask = (df.index.time > datetime.time(12, 0)) & (df.index.time < datetime.time(13, 0))
        df = df[~lunch_mask]

        # 计算基础指标：RSI 相对强弱指标 (14期) 和 MACD
        # Calculate basic indicators: RSI (14-period) and MACD
        
        # 1. RSI
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))
        
        # 2. MACD (12, 26, 9)
        exp1 = df['收盘'].ewm(span=12, adjust=False).mean()
        exp2 = df['收盘'].ewm(span=26, adjust=False).mean()
        df['MACD_DIF'] = exp1 - exp2
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        df['MACD_HIST'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])
        
        # 清除因为计算指标产生的 NaN 行
        df.dropna(inplace=True)
        
        log_info(f"[+] {symbol} 收割完成: 获取到 {len(df)} 根清洗过的高质量 K 线。")
        return df

    except Exception as e:
        log_error(f"[-] 数据收割失败 ({symbol}): {str(e)}")
        return None

# ==========================================
# 2. 非结构化情绪引擎 (Unstructured Sentiment Engine)
# ==========================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def fetch_sentiment_news(symbol: str) -> list:
    """
    抓取对应港股的非结构化情绪数据 (如新闻或财联社电报)
    Fetch unstructured sentiment data (e.g., news or telegraphs) for the symbol.
    
    :param symbol: 股票代码 (例如 "00700")
    :return: 包含新闻标题的列表
    """
    if symbol not in TARGET_POOL:
        raise ValueError(f"[!] 越权访问警告: {symbol} 不在 TARGET_POOL 白名单中！")
        
    print(f"[*] 正在收集 {symbol} 的市场情绪与新闻弹药...")
    
    # 动态伪装与防封 IP 休眠机制 (Anti-bot mechanisms)
    # 随机选择 User-Agent, 并在请求前随机休眠 2-5 秒
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    sleep_time = random.uniform(2, 5)
    print(f"[*] [防反爬伪装] 选择 User-Agent, 准备休眠 {sleep_time:.2f} 秒...")
    time.sleep(sleep_time)
    
    news_list = []
    try:
        # 实际使用 AkShare 的个股新闻接口 (东方财富数据源)
        # Use AkShare's individual stock news interface (Eastmoney data source)
        news_df = ak.stock_news_em(symbol=symbol)
        
        if news_df is not None and not news_df.empty:
            # 提取前 5 条最新新闻的标题作为大模型的情绪弹药
            # Extract the 5 most recent news headlines as sentiment ammunition for the LLM
            # 注意: 不同版本的 AkShare 返回列名可能存在差异，通常包含 '新闻标题'
            titles = news_df['新闻标题'].head(5).tolist()
            news_list = [f"【市场新闻】{title}" for title in titles]
            log_info(f"[+] {symbol} 情绪收集完毕，共获取 {len(news_list)} 条真实新闻弹药。")
        else:
            log_warn(f"[-] {symbol} 未抓取到有效新闻，弹药库为空。")
            
        return news_list
    except Exception as e:
        log_error(f"[-] 获取 {symbol} 真新闻数据失败: {str(e)}")
        return []

if __name__ == "__main__":
    setup_global_proxy()
    # 测试拉取腾讯量价数据
    df_700 = fetch_and_clean_kline_data("00700", period="60")
    if df_700 is not None:
         print(df_700.tail())
         
    # 测试拉取腾讯情绪数据
    news_700 = fetch_sentiment_news("00700")
    print(news_700)
