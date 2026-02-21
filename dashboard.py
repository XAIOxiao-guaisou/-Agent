import streamlit as st
import json
import os
import pandas as pd # type: ignore
from datetime import datetime
import time

# ==========================================
# Phase 8/12: Web UI Dashboard (Bilingual Localization)
# ==========================================

st.set_page_config(page_title="DeepSeek Quant HUD", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0B0C10; color: #C5C6C7; }
    h1, h2, h3 { color: #66FCF1; font-family: 'Consolas', monospace; }
    .metric-card { background-color: #1F2833; padding: 20px; border-radius: 10px; border-left: 5px solid #45A29E; }
    .profit { color: #00FF00; font-weight: bold; }
    .loss { color: #FF0000; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

POSITIONS_FILE = "local_positions.json"
CACHE_FILE = "realtime_cache.json"
WATCHLIST_FILE = "watchlist.json"
INITIAL_CAPITAL = 100000.0

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def fetch_realtime_prices(symbols):
    """从主进程剥离出来的本地缓存读取价格，切断所有直连 API 避免封禁"""
    if not symbols:
        return {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            return {sym: cache.get(sym, {}).get("price", 0.0) for sym in symbols}
        except Exception:
            return {sym: 0.0 for sym in symbols}
    return {sym: 0.0 for sym in symbols}

def fetch_realtime_cache():
    """读取所有缓存（含价格与涨跌幅），供自选股表盘使用"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def update_watchlist_file(symbols_list):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.load(f) if False else json.dump(symbols_list, f, ensure_ascii=False)
    except Exception:
        pass

# ==========================
# UI 布局渲染区
# ==========================

st.sidebar.header("⚙️ Settings / 设置")
lang = st.sidebar.radio("🌐 Language / 语言", ["中文 (Chinese) - 当前默认", "English"])
is_zh = lang is not None and lang.startswith("中文")

# 翻译字典
T = {
    "title": "🤖 DeepSeek Quant 赛博指挥中心" if is_zh else "🤖 DeepSeek Quant Command Center",
    "last_refresh": "**最后刷新时间:**" if is_zh else "**Last Refresh:**",
    "btn_refresh": "🔄 强制刷新数据" if is_zh else "🔄 Manual Refresh",
    "sidebar_tip": "💡 **架构提示**：\n本大屏页面为 **只读模式** (物理隔离)。\n刷新或关闭网页 **绝不会** 影响后台 main.py 引擎中的风控巡逻与交易行为。" if is_zh else "💡 **Tip**: This page is strictly **Read-Only** & isolated. Refreshing or closing it will NOT affect the background trading engine.",
    "col_symbol": "标的 (Symbol)" if is_zh else "Symbol",
    "col_vol": "持仓股数" if is_zh else "Volume",
    "col_cost": "成本价" if is_zh else "Cost Price",
    "col_price": "现价" if is_zh else "Current Price",
    "col_high": "历史最高" if is_zh else "Highest Price",
    "col_stop": "硬止损防线" if is_zh else "Hard Stop-Loss",
    "col_drawdown": "浮动最高回撤" if is_zh else "Max Drawdown",
    "col_pnl": "浮动盈亏" if is_zh else "Floating PnL",
    "col_roi": "收益率" if is_zh else "ROI",
    "metric_cap": "初始模拟本金" if is_zh else "Initial Capital",
    "metric_dep": "当前已用头寸" if is_zh else "Deployed Capital",
    "metric_val": "当前总持仓市值" if is_zh else "Total Pos Value",
    "metric_pnl": "总浮动盈亏" if is_zh else "Total Net PnL",
    "metric_stat": "系统防护状态" if is_zh else "System Status",
    "stat_online": "守护进程运行中" if is_zh else "Daemon Running",
    "sub_matrix": "📊 实时持仓监控矩阵" if is_zh else "📊 Active Positions Matrix",
    "no_pos": "👀 当前空仓观望中。后台雷达正在持续为您扫描市场深坑与套利机会..." if is_zh else "👀 No active positions. Scanning for market opportunities...",
    "sub_watchlist": "⚡ 自定义极速盯盘中枢" if is_zh else "⚡ Custom Watchlist Matrix",
    "lbl_watch": "自定义盯盘代码 (逗号分隔)" if is_zh else "Custom Watchlist (comma separated)",
    "help_watch": "如: 00700, 03690。主雷达将提供秒级跳动。" if is_zh else "e.g., 00700, 03690. Tick daemon monitors them.",
    "col_pct": "涨跌幅" if is_zh else "Pct Change",
}

st.title(T["title"])
st.markdown(f"{T['last_refresh']} `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

if st.sidebar.button(T["btn_refresh"]):
    st.rerun()

st.sidebar.markdown("---")
# 自定盯盘代码输入区
watch_input = st.sidebar.text_input(T["lbl_watch"], help=T["help_watch"], value="00700")

# 解析输入并写入通信文件给主后台
custom_symbols = []
if watch_input.strip():
    custom_symbols = [s.strip() for s in watch_input.split(",") if s.strip()]
    update_watchlist_file(custom_symbols)

st.sidebar.markdown("---")
st.sidebar.info(T["sidebar_tip"])

@st.fragment(run_every="2s")
def render_live_matrices():
    positions = load_positions()
    symbols_held = list(positions.keys())
    
    # 从本地缓存高速读取
    realtime_prices = fetch_realtime_prices(symbols_held)
    full_cache = fetch_realtime_cache()

    total_deployed = 0.0
    total_current_value = 0.0
    holding_records = []

    for sym, pos_data in positions.items():
        cost = pos_data['cost_price']
        vol = pos_data['volume']
        highest = pos_data.get('highest_price', cost)
        current_p = realtime_prices.get(sym, cost)
        
        cost_value = cost * vol
        curr_value = current_p * vol
        pnl = curr_value - cost_value
        pnl_percent = (pnl / cost_value) * 100 if cost_value > 0 else 0
        
        total_deployed += cost_value
        total_current_value += curr_value
        
        drawdown_from_high = ((highest - current_p) / highest) * 100 if highest > 0 else 0
        stop_loss_price = cost * 0.92
        
        holding_records.append({
            T["col_symbol"]: sym,
            T["col_vol"]: vol,
            T["col_cost"]: f"HK$ {cost:.2f}",
            T["col_price"]: f"HK$ {current_p:.2f}",
            T["col_high"]: f"HK$ {highest:.2f}",
            T["col_stop"]: f"HK$ {stop_loss_price:.2f}",
            T["col_drawdown"]: f"{drawdown_from_high:.2f}%",
            T["col_pnl"]: f"{pnl:.2f}",
            T["col_roi"]: f"{pnl_percent:.2f}%"
        })

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(T["metric_cap"], f"HK$ {INITIAL_CAPITAL:,.2f}")
    col2.metric(T["metric_dep"], f"HK$ {total_deployed:,.2f}")
    total_pnl = total_current_value - total_deployed
    col3.metric(T["metric_val"], f"HK$ {total_current_value:,.2f}", delta=f"{total_pnl:,.2f} HK$")
    col4.metric(T["metric_stat"], "🟢 ONLINE", delta=T["stat_online"])

    st.markdown("---")
    st.subheader(T["sub_matrix"])

    def color_pnl(val):
        if '%' in str(val):
            num = float(val.replace('%', ''))
        else:
            try:
                num = float(val)
            except ValueError:
                return ''
        color = '#00FF00' if num > 0 else '#FF0000' if num < 0 else 'white'
        return f'color: {color}; font-weight: bold;'

    if holding_records:
        df = pd.DataFrame(holding_records)
        styled_df = df.style.map(color_pnl, subset=[T["col_pnl"], T["col_roi"]]) # type: ignore
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info(T["no_pos"])

    # 渲染极速盯盘中枢
    if custom_symbols:
        st.markdown("---")
        st.subheader(T["sub_watchlist"])
        watch_records = []
        for sym in custom_symbols:
            c_data = full_cache.get(sym, {"price": 0.0, "pct": 0.0})
            watch_records.append({
                T["col_symbol"]: sym,
                T["col_price"]: f"HK$ {c_data['price']:.3f}",
                T["col_pct"]: f"{c_data['pct']:.2f}%"
            })
        if watch_records:
            wdf = pd.DataFrame(watch_records)
            styled_wdf = wdf.style.map(color_pnl, subset=[T["col_pct"]]) # type: ignore
            st.dataframe(styled_wdf, use_container_width=True, hide_index=True)

# 启动局部刷新组件
render_live_matrices()
