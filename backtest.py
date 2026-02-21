import pandas as pd
import akshare as ak
import datetime
import random
from config import setup_global_proxy
from deepseek_brain import ask_deepseek
from execution_risk import LocalRiskController

# ==========================================
# Phase 6: MVP Sandbox Backtesting (Time Machine)
# ==========================================

class TimeMachineBacktester:
    def __init__(self, symbol: str, initial_capital: float = 100000.0):
        """
        时光机回测沙盒 (Time Machine Backtesting Sandbox)
        """
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position_volume = 0
        self.history_records = []
        
        # 接入第四阶段的风控核心 (Integrating Phase 4 Risk Controller)
        self.risk_sys = LocalRiskController(initial_capital)
        print(f"[*] 沙盒初始化完成: 标的={symbol}, 初始资金=￥{initial_capital}")

    def load_historical_data(self, start_date: str, end_date: str):
        """
        按天加载历史量价数据 (Load historical price-volume data day-by-day)
        由于是日线回测, 我们拉取前复权的日线数据。
        """
        print(f"[*] 正在拉取 {self.symbol} 从 {start_date} 到 {end_date} 的前复权日线数据...")
        try:
            # 港股日线前复权数据获取 (Daily forward-adjusted K-line)
            df = ak.stock_hk_hist(symbol=self.symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            df['日期'] = pd.to_datetime(df['日期'])
            df.set_index('日期', inplace=True)
            
            # 预热计算 RSI (RSI calculation)
            delta = df['收盘'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI_14'] = 100 - (100 / (1 + rs))
            df.dropna(inplace=True)
            return df
        except Exception as e:
            print(f"[-] 历史数据拉取失败: {e}")
            return None

    def execute_trade(self, date: datetime.datetime, current_price: float, action: str, suggested_volume: int = 0):
        """执行虚拟买卖手续，计算印花税与佣金 (Execute virtual trade, calc stamp duty & commission)"""
        # 假设印花税 0.1%, 佣金 0.03% (Assume stamp duty 0.1%, commission 0.03%)
        fee_rate = 0.001 + 0.0003
        
        if action == "BUY" and self.cash >= current_price * suggested_volume:
            trade_val = current_price * suggested_volume
            fee = trade_val * fee_rate
            self.cash -= (trade_val + fee)
            self.position_volume += suggested_volume
            
            # 同步给风控系统记录成本
            self.risk_sys.mock_buy(self.symbol, current_price, suggested_volume)
            
            self.history_records.append({
                "date": date, "action": "BUY", "price": current_price, 
                "vol": suggested_volume, "fee": fee, "nav": self.calculate_nav(current_price)
            })
            print(f"[{date.date()}] 买入 {suggested_volume} 股 @ {current_price}, 剩余现金: {self.cash:.1f}")

        elif action in ["SELL", "SELL_ALL"] and self.position_volume > 0:
            trade_val = current_price * self.position_volume
            fee = trade_val * fee_rate
            self.cash += (trade_val - fee)
            
            print(f"[{date.date()}] 卖出所有 {self.position_volume} 股 @ {current_price}, 获得现金: {self.cash:.1f}")
            self.history_records.append({
                "date": date, "action": "SELL", "price": current_price, 
                "vol": self.position_volume, "fee": fee, "nav": self.calculate_nav(current_price)
            })
            
            # 清空仓位记录
            self.position_volume = 0
            if self.symbol in self.risk_sys.positions:
                del self.risk_sys.positions[self.symbol]

    def calculate_nav(self, current_price: float) -> float:
        """计算当前总净值 (Calculate Net Asset Value)"""
        return self.cash + (self.position_volume * current_price)

    def run_backtest(self, df: pd.DataFrame):
        """
        执行闭环回放推演 (Execute closed-loop backtest simulation)
        """
        print(f"\n[>>>] 开始回测 (Start Backtesting) [<<<]")
        
        # 逐日回放
        for index, row in df.iterrows():
            current_date = index
            current_price = row['收盘']
            current_rsi = row['RSI_14']
            
            # --- 阶段 1: 实时风控防线 (Real-time Risk Defense) ---
            if self.position_volume > 0:
                is_stop_triggered = self.risk_sys.monitor_dynamic_stop_loss(self.symbol, current_price)
                if is_stop_triggered:
                    self.execute_trade(current_date, current_price, "SELL_ALL")
                    continue # 已经止损清仓，跳过大模型交互
            
            # 为了节约 API 测试时间与金钱，这里我们伪造 DeepSeek 的随机理性决策
            # 实盘回测应将 row 数据组装并调用 `ask_deepseek`
            # For saving API costs during test, mocking LLM's rational decision
            mock_action = random.choice(["BUY", "BUY", "HOLD", "HOLD", "HOLD", "SELL"])
            mock_reason = "Mock LLM Backtest Reasoning."
            llm_decision = {"action": mock_action, "reason": mock_reason}
            
            # --- 阶段 2: 拦截器双重验证 (Interceptor Dual Verification) ---
            final_decision = self.risk_sys.dual_copilot_interceptor(self.symbol, llm_decision, current_price, current_rsi)
            
            # --- 阶段 3: 执行层 (Execution Layer) ---
            if final_decision["action"] == "BUY":
                self.execute_trade(current_date, current_price, "BUY", final_decision.get("suggested_volume", 0))
            elif final_decision["action"] in ["SELL", "SELL_ALL"]:
                self.execute_trade(current_date, current_price, "SELL")
                
        # 回测结束统计
        final_price = df.iloc[-1]['收盘']
        final_nav = self.calculate_nav(final_price)
        total_return = (final_nav - self.initial_capital) / self.initial_capital * 100
        print(f"\n[====================================]")
        print(f"回测结束 (Backtest Completed) | 标的: {self.symbol}")
        print(f"初始本金 (Initial): ￥{self.initial_capital}")
        print(f"最终净值 (Final NAV): ￥{final_nav:.2f}")
        print(f"总收益率 (Total Return): {total_return:.2f}%")
        print(f"[====================================]")


if __name__ == "__main__":
    setup_global_proxy()
    # 建立测试时光机，标的：00700 (腾讯)
    sandbox = TimeMachineBacktester(symbol="00700", initial_capital=100000.0)
    
    # 拨回 2024 年初到现在的岁月
    historical_df = sandbox.load_historical_data(start_date="20240101", end_date="20241231")
    
    if historical_df is not None:
        sandbox.run_backtest(historical_df)
