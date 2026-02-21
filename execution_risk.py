import json
import os

# ==========================================
# Phase 4 Update: Execution Layer (Hard Risk Control with Memory)
# ==========================================

class LocalRiskController:
    def __init__(self, initial_capital: float = 100000.0, persist_file: str = "local_positions.json"):
        self.total_capital = initial_capital
        self.max_exposure_ratio = 0.10
        self.persist_file = persist_file
        
        # 启动时自动从本地恢复记忆
        self.positions = self.load_positions()

    def load_positions(self) -> dict:
        """从本地 JSON 文件读取持仓记忆"""
        if os.path.exists(self.persist_file):
            try:
                with open(self.persist_file, "r", encoding="utf-8") as f:
                    print("[+] 成功恢复本地持仓记忆文件。")
                    return json.load(f)
            except Exception as e:
                print(f"[-] 加载本地持仓失败: {e}")
        return {}

    def save_positions(self):
        """将当前持仓状态落盘保存 (原子级写入 Atomic Write)"""
        temp_file = self.persist_file + ".tmp"
        bak_file = self.persist_file + ".bak"
        try:
            # 1. 备份旧文件 (Backup old file)
            if os.path.exists(self.persist_file):
                os.replace(self.persist_file, bak_file)
                
            # 2. 将数据写入临时文件 (Write data to temporary file)
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.positions, f, indent=4, ensure_ascii=False)
                # 确保写入硬盘 (Ensure flushed to disk)
                f.flush()
                os.fsync(f.fileno())
                
            # 3. 原子级重命名替换 (Atomic rename/replace)
            os.replace(temp_file, self.persist_file)
        except Exception as e:
            print(f"[-] 保存本地持仓失败: {e}")

    def calculate_position_size(self, current_price: float) -> int:
        max_capital_for_trade = self.total_capital * self.max_exposure_ratio
        return int(max_capital_for_trade // current_price)

    def dual_copilot_interceptor(self, symbol: str, deepseek_decision: dict, current_price: float, current_rsi: float) -> dict:
        action = deepseek_decision.get("action", "HOLD")
        reason = deepseek_decision.get("reason", "No reason provided")
        
        print(f"\n[!] 触发 {symbol} 风控拦截器 -> AI: {action} | RSI: {current_rsi:.2f}")

        if action == "BUY":
            if current_rsi >= 70:
                print(f"   [x] 拦截: RSI超买 ({current_rsi:.2f})，驳回追高，转为 HOLD。")
                return {"action": "HOLD", "reason": f"RSI_OVERHEATED: {reason}"}
            
            suggested_vol = self.calculate_position_size(current_price)
            if suggested_vol <= 0: return {"action": "HOLD", "reason": "INSUFFICIENT_FUNDS"}
            
            print(f"   [v] 放行: 允许买入 {suggested_vol} 股。")
            deepseek_decision["suggested_volume"] = suggested_vol
            return deepseek_decision

        elif action == "SELL":
             if symbol not in self.positions:
                 return {"action": "HOLD", "reason": "NO_POSITION"}
             return deepseek_decision
        return deepseek_decision

    def monitor_dynamic_stop_loss(self, symbol: str, current_price: float) -> bool:
        if symbol not in self.positions: return False
        pos = self.positions[symbol]
        cost_price = pos["cost_price"]
        
        # 更新最高价并持久化
        if current_price > pos["highest_price"]:
            pos["highest_price"] = current_price
            self.save_positions()
            
        highest_price = pos["highest_price"]
        
        if highest_price >= cost_price * 1.10: 
            if (highest_price - current_price) / highest_price >= 0.05:
                print(f"[!!!] 警报: {symbol} 触发移动止盈！强制 SELL_ALL。")
                return True
                
        if current_price <= cost_price * 0.92:
            print(f"[!!!] 警报: {symbol} 跌破8%硬止损！强制 SELL_ALL。")
            return True
        return False
        
    def mock_buy(self, symbol: str, price: float, volume: int):
        self.positions[symbol] = {
            "cost_price": price,
            "volume": volume,
            "highest_price": price
        }
        self.save_positions() # 每次买入后立刻落盘记忆
        print(f"   => [状态已落盘] 买入 {symbol} {volume}股 @ {price}")

    def mock_sell_all(self, symbol: str):
        if symbol in self.positions:
            del self.positions[symbol]
            self.save_positions() # 卖出后清空该标的记忆
            print(f"   => [状态已落盘] 清仓 {symbol}")
