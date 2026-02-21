import tkinter as tk
from threading import Thread
import time
import requests # type: ignore

# ==========================================
# Phase 12/14: Visual Monitoring Center (Bilingual 4-Slot Radar HUD)
# ==========================================

SERVER_CHAN_SENDKEY = "SCTxxxxxxxxxxxxxxxxxxxxx"

def send_mobile_notification(symbol: str, action: str, reason: str):
    """通过 Server酱 发送微信/手机推送通知"""
    if SERVER_CHAN_SENDKEY.startswith("SCTx"):
        print(f"[!] 通知拦截: 未配置真实 Key -> {symbol} | {action} | {reason}")
        return
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_SENDKEY}.send"
    payload = {"title": f"【量化信号】{symbol} 执行 {action}", "desp": f"### 动作: **{action}**\n\n### 标的: {symbol}\n\n### AI与风控综合理由:\n{reason}\n\n*请及时前往券商APP进行复核下单。*"}
    try:
        response = requests.post(url, data=payload, timeout=10) # type: ignore
        if response.status_code == 200:
            print("[+] 手机推送下发成功")
    except Exception as e:
        print(f"[-] 手机推送下发失败: {e}")

class CyberpunkRadarHUD:
    def __init__(self, max_slots=4):
        """升级版 4 槽位赛博朋克雷达 (支持双语切换)"""
        self.root = tk.Tk()
        self.root.title("DeepSeek Radar")
        
        # 极简/无边框设定
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', 0.85)
        self.root.attributes('-topmost', True)
        
        self.bg_color = "#0B0C10"
        self.alert_color = "#C3073F"
        self.root.configure(bg=self.bg_color)
        
        # 尺寸与定位 (适应 4 个槽位的高度)
        self.width = 340
        self.height = 80 + (max_slots * 40)
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"{self.width}x{self.height}+{screen_width - self.width - 20}+50")
        
        # 拖拽绑定
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)

        self.is_zh = True # 默认中文
        self.max_slots = max_slots
        self.slots = {}
        self.is_flashing = False
        self._last_latency = 0
        self.x = 0
        self.y = 0

        # --- 顶栏 UI 布局 ---
        top_frame = tk.Frame(self.root, bg=self.bg_color)
        top_frame.pack(fill=tk.X, pady=5, padx=10)
        
        self.lbl_title = tk.Label(top_frame, text="⚡ 实时雷达矩阵" if self.is_zh else "⚡ LIVE RADAR", fg="#66FCF1", bg=self.bg_color, font=("Consolas", 12, "bold"))
        self.lbl_title.pack(side=tk.LEFT)
        
        self.btn_exit = tk.Button(top_frame, text="[X]", fg="#C3073F", bg=self.bg_color, bd=0, command=self.root.destroy, font=("Consolas", 10))
        self.btn_exit.pack(side=tk.RIGHT)
        
        self.btn_lang = tk.Button(top_frame, text="[EN]", fg="#45A29E", bg=self.bg_color, bd=0, command=self.toggle_lang, font=("Consolas", 9))
        self.btn_lang.pack(side=tk.RIGHT, padx=5)
        
        self.lbl_net = tk.Label(self.root, text="API: 待机 | AI 决策: 休眠" if self.is_zh else "API: WAIT | AI: SLEEP", fg="#45A29E", bg=self.bg_color, font=("Consolas", 9))
        self.lbl_net.pack()

        # --- 4 个监控槽位 (Slots) ---
        self.slots_frame = tk.Frame(self.root, bg=self.bg_color)
        self.slots_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def toggle_lang(self):
        """切换中英文显示"""
        self.is_zh = not self.is_zh
        self.btn_lang.config(text="[中]" if not self.is_zh else "[EN]")
        self.lbl_title.config(text="⚡ 实时雷达矩阵" if self.is_zh else "⚡ LIVE RADAR")
        
        if self._last_latency > 0:
            self.update_network_latency(self._last_latency)
        else:
            self.lbl_net.config(text="API: 待机 | AI 决策: 休眠" if self.is_zh else "API: WAIT | AI: SLEEP")
            
        # 刷新每个槽位的动作指令语言
        for sym, data in self.slots.items():
            current_sig = data["raw_sig"]
            self._apply_slot_signal(sym, current_sig)

    # --- 窗口拖拽逻辑 ---
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def register_symbols(self, symbols: list): # type: ignore
        """初始化监控白名单的槽位 UI"""
        for sym in symbols[:self.max_slots]:
            frame = tk.Frame(self.slots_frame, bg="#1F2833", pady=2)
            frame.pack(fill=tk.X, pady=2)
            
            lbl_sym = tk.Label(frame, text=f"[{sym}]", fg="#C5C6C7", bg="#1F2833", font=("Consolas", 11, "bold"), width=8, anchor="w")
            lbl_sym.pack(side=tk.LEFT, padx=5)
            
            lbl_price = tk.Label(frame, text="Wait...", fg="#FFFFFF", bg="#1F2833", font=("Consolas", 10), width=10, anchor="e")
            lbl_price.pack(side=tk.LEFT, padx=5)
            
            lbl_sig = tk.Label(frame, text="--", fg="#45A29E", bg="#1F2833", font=("Consolas", 10, "bold"), width=8)
            lbl_sig.pack(side=tk.RIGHT, padx=5)
            
            # 保存组件引用以及原始英文动作，用于多语言切换再加工
            self.slots[sym] = {"price": lbl_price, "sig": lbl_sig, "frame": frame, "raw_sig": "--"}

    def update_tick(self, symbol: str, price: float, pct_change: float):
        """高频更新单支股票的价格与涨跌幅 (线程安全调用)"""
        if symbol in self.slots:
            def task():
                color = "#00FF00" if pct_change > 0 else "#FF0000" if pct_change < 0 else "#FFFFFF"
                self.slots[symbol]["price"].config(text=f"{price:.2f} ({pct_change:+.1f}%)", fg=color)
            self.root.after(0, task)

    def _apply_slot_signal(self, symbol: str, action: str):
        """内部方法：应用颜色与跨语言翻译更新对应槽位"""
        if symbol not in self.slots: return
        
        action_map = {
            "SCANNING...": "扫描中",
            "HOLD": "观望",
            "BUY": "买入",
            "SELL": "卖出",
            "SELL_ALL": "清仓",
            "--": "--"
        }
        
        display_action = action_map.get(action, action) if self.is_zh else action
        color = "#66FCF1" if action == "BUY" else "#C3073F" if "SELL" in action else "#45A29E"
        
        self.slots[symbol]["sig"].config(text=display_action, fg=color)

    def update_status(self, symbol: str, action: str):
        """更新 AI 决策状态 (线程安全)"""
        if symbol in self.slots:
            def task():
                self.slots[symbol]["raw_sig"] = action
                self._apply_slot_signal(symbol, action)
                if "SELL" in action or action == "BUY":
                    self.trigger_alert()
            self.root.after(0, task)

    def update_network_latency(self, latency_ms: int):
        """更新网络延迟状态 (线程安全)"""
        self._last_latency = latency_ms
        def task():
            text = f"API: {latency_ms}ms | AI 决策: 活跃" if self.is_zh else f"API: {latency_ms}ms | AI: ACTIVE"
            self.lbl_net.config(text=text, fg="#66FCF1")
        self.root.after(0, task)

    def trigger_alert(self):
        """触发红色闪烁警报"""
        if not self.is_flashing:
            self.is_flashing = True
            self._flash_bg(8)

    def _flash_bg(self, count):
        """内部递归方法：执行闪烁循环动画"""
        if count <= 0:
            self.root.configure(bg=self.bg_color)
            self.is_flashing = False
            return
            
        new_bg = self.alert_color if self.root.cget("bg") == self.bg_color else self.bg_color
        self.root.configure(bg=new_bg)
        
        # 穿透到顶层组件的背景色
        for widget in [self.lbl_title, self.lbl_net, self.btn_exit, self.btn_lang]:
            widget.configure(bg=new_bg)
            
        self.root.after(150, self._flash_bg, count - 1)

    def start(self):
        """启动 GUI 主循环"""
        self.root.mainloop()

# ==========================================
# 模拟测试环境 (Mock Testing Environment)
# ==========================================
def mock_system_events(hud: CyberpunkRadarHUD):
    """模拟系统后台运行抛出事件"""
    hud.register_symbols(["00700", "03690", "09988"])
    time.sleep(2)
    
    # 模拟东财 Tick 行情跳动
    hud.update_tick("00700", 280.5, 1.2)
    hud.update_tick("03690", 88.0, -0.5)
    hud.update_tick("09988", 72.3, 0.0)
    
    time.sleep(2)
    # 模拟网络心跳与 AI 扫单
    hud.update_network_latency(120)
    hud.update_status("00700", "HOLD")
    
    time.sleep(2)
    hud.update_tick("03690", 86.5, -2.1)
    hud.update_network_latency(230)
    
    # 模拟发现严重危机，触发熔断清仓
    hud.update_status("03690", "SELL_ALL")
    send_mobile_notification("03690", "SELL_ALL", "急速雷达防线触发，跌破阈值。")

if __name__ == "__main__":
    app = CyberpunkRadarHUD(max_slots=4)
    # 启动后台模拟线程，不阻塞 UI 线程
    t = Thread(target=mock_system_events, args=(app,), daemon=True)
    t.start()
    
    app.start()
