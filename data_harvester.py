import pandas as pd # type: ignore
import akshare as ak # type: ignore
from base64 import b64encode
import datetime
import time
import random
from config import setup_global_proxy # type: ignore
from debug_sentinel import log_info, log_error, log_warn # type: ignore

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

def fetch_multi_dim_intelligence(symbol: str) -> dict:
    """
    抓取多维度情报网 (Multi-Dimensional Intelligence Web)
    包含: 1. 个股微观新闻  2. 宏观实时电报
    """
    if symbol not in TARGET_POOL:
        raise ValueError(f"[!] 越权访问警告: {symbol} 不在 TARGET_POOL 白名单中！")
        
    print(f"[*] 正在雷达扫描 {symbol} 的多维度市场情绪...")
    
    # 防封 IP 休眠机制
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    time.sleep(random.uniform(2, 5))
    
    intelligence_pack = {
        "micro_stock_news": [],   # 个股新闻
        "macro_market_news": []   # 宏观大盘电报
    }
    
    # 维度 1: 抓取个股微观新闻 (Micro Sentiment)
    try:
        news_df = ak.stock_news_em(symbol=symbol)
        if news_df is not None and not news_df.empty:
            titles = news_df['新闻标题'].head(5).tolist()
            intelligence_pack["micro_stock_news"] = [f"【个股】{t}" for t in titles]
    except Exception as e:
        print(f"[-] 获取 {symbol} 个股新闻失败: {str(e)}")

    # 维度 2: 抓取全市场宏观实时电报 (Macro Sentiment - 财联社)
    try:
        # 抓取财联社实时电报，获取大盘宏观情绪
        macro_df = ak.stock_telegraph_cls()
        if macro_df is not None and not macro_df.empty:
            # 过滤掉过长的内容，只取标题或简讯的前 4 条
            macro_titles = macro_df['标题'].head(4).tolist()
            # 如果标题为空，尝试提取内容的前 50 个字
            cleaned_macros = []
            for idx, row in macro_df.head(4).iterrows():
                title_str = str(row.get('标题', ''))
                content_str = str(row.get('内容', ''))
                text = title_str if title_str and title_str != 'nan' else content_str[:50] + "..." # type: ignore
                cleaned_macros.append(f"【宏观】{text}")
                
            intelligence_pack["macro_market_news"] = cleaned_macros
    except Exception as e:
        print(f"[-] 获取宏观电报失败: {str(e)}")

    print(f"[+] 情报网抓取完毕: {len(intelligence_pack['micro_stock_news'])}条微观, {len(intelligence_pack['macro_market_news'])}条宏观。")
    return intelligence_pack

if __name__ == "__main__":
    setup_global_proxy()
    # 测试拉取腾讯量价数据
    df_700 = fetch_and_clean_kline_data("00700", period="60")
    if df_700 is not None:
         print(df_700.tail())
         
    # 测试拉取腾讯情绪数据
    intell_700 = fetch_multi_dim_intelligence("00700")
    print(intell_700)
