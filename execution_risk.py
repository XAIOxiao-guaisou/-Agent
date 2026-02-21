import json
import os
import threading
from debug_sentinel import log_info, log_error, log_warn # type: ignore

# ==========================================
# Phase 4/10 Update: Execution Layer (Thread-Safe Risk Control with Logging)
# ==========================================

class LocalRiskController:
    def __init__(self, initial_capital: float = 100000.0, persist_file: str = "local_positions.json"):
        self.total_capital = initial_capital
        self.max_exposure_ratio = 0.10
        self.persist_file = persist_file
        self.lock = threading.RLock() # 新增可重入锁 (Added Re-entrant thread-safe lock)
        
        # 启动时自动从本地恢复记忆
        self.positions = self.load_positions()

    def load_positions(self) -> dict:
        """从本地 JSON 文件读取持仓记忆"""
        if os.path.exists(self.persist_file):
            try:
                with open(self.persist_file, "r", encoding="utf-8") as f:
                    log_info("[+] 成功恢复本地持仓记忆文件。")
                    return json.load(f)
            except Exception as e:
                log_error(f"[-] 加载本地持仓失败: {e}")
        return {}
        
    def get_positions_copy(self) -> dict:
        """返回深层拷贝的安全只读字典供其他线程使用"""
        with self.lock:
            import copy
            return copy.deepcopy(self.positions)

    def save_positions(self):
        """将当前持仓状态落盘保存 (原子级写入 Atomic Write + Thread-Safe ThreadLock)"""
        with self.lock: # 锁定文件写入资源
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
                log_error(f"[-] 保存本地持仓失败: {e}")

    def calculate_position_size(self, current_price: float) -> int:
        max_capital_for_trade = self.total_capital * self.max_exposure_ratio
        return int(max_capital_for_trade // current_price)

    def dual_copilot_interceptor(self, symbol: str, deepseek_decision: dict, current_price: float, current_rsi: float) -> dict:
        action = deepseek_decision.get("action", "HOLD")
        reason = deepseek_decision.get("reason", "No reason provided")
        
        log_info(f"[!] 触发 {symbol} 风控拦截器 -> AI: {action} | RSI: {current_rsi:.2f}")

        if action == "BUY":
            if current_rsi >= 70:
                log_warn(f"   [x] 拦截: RSI超买 ({current_rsi:.2f})，驳回追高，转为 HOLD。")
                return {"action": "HOLD", "reason": f"RSI_OVERHEATED: {reason}"}
            
            suggested_vol = self.calculate_position_size(current_price)
            if suggested_vol <= 0: return {"action": "HOLD", "reason": "INSUFFICIENT_FUNDS"}
            
            log_info(f"   [v] 放行: 允许买入 {suggested_vol} 股。")
            deepseek_decision["suggested_volume"] = suggested_vol
            return deepseek_decision

        elif action == "SELL":
            with self.lock: # 读锁防并发崩溃 (Read lock)
                 if symbol not in self.positions:
                     return {"action": "HOLD", "reason": "NO_POSITION"}
            return deepseek_decision
        return deepseek_decision

    def monitor_dynamic_stop_loss(self, symbol: str, current_price: float) -> bool:
        with self.lock: # 全局包围防竞争 (Enclose fully to prevent race condition during iteration)
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
                    log_warn(f"[!!!] 警报: {symbol} 触发移动止盈！强制 SELL_ALL。")
                    return True
                    
            if current_price <= cost_price * 0.92:
                log_warn(f"[!!!] 警报: {symbol} 跌破8%硬止损！强制 SELL_ALL。")
                return True
            return False
        
    def execute_live_buy(self, symbol: str, price: float, volume: int):
        """实盘买入执行钉子 (Live Buy Hook)
        目前为本地落盘记录，下一步接驳券商 API
        """
        with self.lock:  # 修改持仓字典也要上锁
            self.positions[symbol] = {
                "cost_price": price,
                "volume": volume,
                "highest_price": price
            }
        self.save_positions()  # 每次买入后立刻落盘记忆
        log_info(f"   => [实盘订单生成] 成功买入 {symbol} {volume}股 @ {price}")
        # TODO: Phase 19 -> 此处调用 Interactive Brokers / 富涂 OpenAPI 发送真实市价单
        # from broker_api import place_order
        # place_order(symbol=symbol, action='BUY', qty=volume, order_type='MKT')

    def execute_live_sell_all(self, symbol: str):
        """实盘清仓执行钉子 (Live Sell All Hook)
        目前为本地落盘记录，下一步接驳券商 API
        """
        with self.lock:  # 卖出清理也上锁
            if symbol in self.positions:
                self.positions.pop(symbol, None)
        self.save_positions()  # 卖出后清空该标的记忆
        log_info(f"   => [实盘订单生成] 清仓 {symbol}")
        # TODO: Phase 19 -> 此处调用 Interactive Brokers / 富涂 OpenAPI 发送市价卖出单
        # from broker_api import place_order
        # place_order(symbol=symbol, action='SELL', qty='ALL', order_type='MKT')

    # 向前兼容别名 (Backward Compatibility Aliases)
    # 旧代码如果调用 mock_buy/mock_sell_all 仍将正常工作
    mock_buy = execute_live_buy
    mock_sell_all = execute_live_sell_all

