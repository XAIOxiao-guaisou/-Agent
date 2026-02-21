import json

# ==========================================
# Phase 4: Execution Layer (Hard Risk Control)
# ==========================================

class LocalRiskController:
    def __init__(self, initial_capital: float = 100000.0):
        """
        本地硬风控防线 (Local Hard Risk Control Defense Line)
        :param initial_capital: 初始模拟资金 (单次建仓暴露不超过 10%)
        """
        self.total_capital = initial_capital
        self.max_exposure_ratio = 0.10  # 10% limit
        
        # 记录持仓状态 (Record position status)
        # 结构: {"00700": {"cost_price": 280.0, "volume": 100, "highest_price": 280.0}}
        self.positions = {}

    def calculate_position_size(self, current_price: float) -> int:
        """
        仓位计算器：计算单次最多可买入的股数 (由于港股按手交易，暂简化为股数)
        Position Size Calculator: Max shares allowed for a single trade based on 10% capital exposure.
        """
        max_capital_for_trade = self.total_capital * self.max_exposure_ratio
        # 向下取整 (Round down to nearest share/lot)
        max_shares = int(max_capital_for_trade // current_price)
        return max_shares

    def dual_copilot_interceptor(self, symbol: str, deepseek_decision: dict, current_price: float, current_rsi: float) -> dict:
        """
        拦截器机制（双重副驾驶）
        Interceptor Mechanism (Dual Co-pilot)
        
        只有大模型的 BUY 指令且本地硬指标 (如 RSI不过热) 同时满足，信号才放行。
        """
        action = deepseek_decision.get("action", "HOLD")
        reason = deepseek_decision.get("reason", "No reason provided")
        
        print(f"\n[!] 触发 {symbol} 风控拦截器 (Interceptor triggered)")
        print(f"   -> AI 原始信号: {action} ({reason})")
        print(f"   -> 本地硬指标: 价={current_price}, RSI={current_rsi:.2f}")

        if action == "BUY":
            # 规则 1: RSI 绝不可以超过 70 (超买区拒绝追高)
            if current_rsi >= 70:
                print(f"   [x] 拦截: 本地 RSI 达到 {current_rsi:.2f} 过热，驳回 AI 追高指令，强制转为 HOLD！")
                return {"action": "HOLD", "reason": f"RSI_OVERHEATED_REJECTED (AI wanted BUY): {reason}"}
            
            # 计算暴露头寸 (Calculate exposure)
            suggested_vol = self.calculate_position_size(current_price)
            if suggested_vol <= 0:
                 print(f"   [x] 拦截: 资金不足 1 股建仓，驳回 BUY 指令。")
                 return {"action": "HOLD", "reason": "INSUFFICIENT_FUNDS_EXPOSURE_LIMIT"}
            
            print(f"   [v] 放行: 允许买入 {suggested_vol} 股。")
            deepseek_decision["suggested_volume"] = suggested_vol
            return deepseek_decision

        elif action == "SELL":
             # 如果当前根本没有持仓，直接忽略 SELL
             if symbol not in self.positions:
                 print(f"   [-] 忽略: 当前无 {symbol} 的持仓，无法执行 SELL。")
                 return {"action": "HOLD", "reason": "NO_POSITION_TO_SELL"}
             
             print(f"   [v] 放行: 允许 AI 触发的平仓指令。")
             return deepseek_decision

        return deepseek_decision

    def monitor_dynamic_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        进阶风控：动态止盈止损线实时监控 (Trailing Stop & Hard Stop-loss)
        
        :return: True 表示触发警报必须卖出，False 表示安全
        """
        if symbol not in self.positions:
            return False
            
        pos = self.positions[symbol]
        cost_price = pos["cost_price"]
        
        # 更新该周期的最高价
        if current_price > pos["highest_price"]:
            pos["highest_price"] = current_price
            
        highest_price = pos["highest_price"]
        
        # 计算当前绝对利润率 (Absolute Profit Ratio)
        profit_ratio = (current_price - cost_price) / cost_price
        
        # ---------------------------------------------------------
        # 1. 动态移动止损 (Trailing Stop - Profit Protection)
        # 当持仓盈利超过 10% 后，自动激活移动止损机制
        # ---------------------------------------------------------
        if highest_price >= cost_price * 1.10: # 曾经盈利达到过 10%
            drawdown_from_high = (highest_price - current_price) / highest_price
            if drawdown_from_high >= 0.05: # 从最高点回撤 5%
                print(f"[!!!] 警报 (TRAILING STOP): {symbol} 触发利润保卫战！从高点 {highest_price} 回撤 5%，现价 {current_price}，强制 SELL_ALL 并止盈。")
                return True
                
        # ---------------------------------------------------------
        # 2. 硬止损线 (Hard Stop-Loss Alert)
        # 若现价低于买入成本 8%
        # ---------------------------------------------------------
        if current_price <= cost_price * 0.92:
            print(f"[!!!] 警报 (HARD STOP): {symbol} 跌破硬止损防线！成本 {cost_price}，现价 {current_price} (跌幅超过 8%)，无视 AI 强制 SELL_ALL。")
            return True
            
        return False
        
    def mock_buy(self, symbol: str, price: float, volume: int):
        """模拟买入并登记"""
        self.positions[symbol] = {
            "cost_price": price,
            "volume": volume,
            "highest_price": price
        }
        print(f"   => [模拟登记] 买入 {symbol} {volume}股 @ {price}")


if __name__ == "__main__":
    risk_sys = LocalRiskController(initial_capital=100000)
    
    # 测试用例 1: AI想买，但由于指标过热被拦截
    # Test Case 1: Intercept AI BUY due to overheated indicator
    decision_1 = {"action": "BUY", "reason": "MACD 金叉"}
    final_1 = risk_sys.dual_copilot_interceptor("00700", decision_1, current_price=280.0, current_rsi=75.0)
    print("最终决策_1:", final_1)
    
    # 测试用例 2: AI想买，指标正常，计算单次最大仓位金额 (1万)
    # Test Case 2: Allow BUY, calc max exposure volume (Limit 10% = 10k)
    final_2 = risk_sys.dual_copilot_interceptor("00700", decision_1, current_price=280.0, current_rsi=40.0)
    print("最终决策_2:", final_2)
    
    # 建立持仓，开始监控测试...
    risk_sys.mock_buy("00700", price=280.0, volume=final_2["suggested_volume"])
    
    # 测试用例 3: 测试 8% 硬止损
    # Test Case 3: Hard Stop-Loss at -8%
    print("\n[测试硬止损]")
    risk_sys.monitor_dynamic_stop_loss("00700", current_price=257.0) # 280 * 0.92 = 257.6
    
    # 测试用例 4: 测试 10% 盈利后的 5% 回撤保利润
    # Test Case 4: Trailing Stop after 10%+ profit 
    print("\n[测试移动止损]")
    risk_sys.monitor_dynamic_stop_loss("00700", current_price=310.0) # 暴涨到盈利 10.7% (Highest updated to 310)
    risk_sys.monitor_dynamic_stop_loss("00700", current_price=294.0) # 从高点回撤 5.16% (Trigger Sell)
