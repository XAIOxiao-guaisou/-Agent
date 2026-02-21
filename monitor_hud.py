import tkinter as tk
from threading import Thread
import time
import requests # type: ignore

# ==========================================
# Phase 5/12: Visual Monitoring Center (Bilingual Tkinter HUD)
# ==========================================

SERVER_CHAN_SENDKEY = "SCTxxxxxxxxxxxxxxxxxxxxx"

def send_mobile_notification(symbol: str, action: str, reason: str):
    if SERVER_CHAN_SENDKEY.startswith("SCTx"):
        print(f"[!] 通知拦截: 未配置真实的 Server酱 Key, 本地打印 -> {symbol} | {action} | {reason}")
        return
        
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_SENDKEY}.send"
    title = f"【量化信号】{symbol} 执行 {action}"
    desp = f"### 动作: **{action}**\n\n### 标的: {symbol}\n\n### AI与风控综合理由:\n{reason}\n\n*请及时前往券商APP进行复核下单。*"
    
    payload = {"title": title, "desp": desp}
    try:
        response = requests.post(url, data=payload, timeout=10) # type: ignore
        if response.status_code == 200:
            print("[+] 手机推送下发成功")
    except Exception as e:
        print(f"[-] 手机推送下发失败: {e}")

class CyberpunkHUD:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DeepSeek Quant HUD")
        
        self.root.overrideredirect(True)
        screen_width = self.root.winfo_screenwidth()
        self.width = 340
        self.height = 150
        self.root.geometry(f"{self.width}x{self.height}+{screen_width - self.width - 20}+50")
        
        self.root.attributes('-alpha', 0.8)
        self.root.attributes('-topmost', True)
        
        self.root.configure(bg="#0B0C10")
        self.bg_color = "#0B0C10"
        self.alert_color = "#C3073F"
        
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)

        self.is_zh = True # 默认中文
        
        self.lbl_title = tk.Label(self.root, text="量化核心状态" if self.is_zh else "QUANT CORE STATUS", fg="#66FCF1", bg=self.bg_color, font=("Consolas", 12, "bold"))
        self.lbl_title.pack(pady=5)
        
        self.lbl_net = tk.Label(self.root, text="网络延迟: 等待响应" if self.is_zh else "Network: WAIT", fg="#45A29E", bg=self.bg_color, font=("Consolas", 10))
        self.lbl_net.pack()
        
        self.lbl_symbol = tk.Label(self.root, text="盯盘中: 无" if self.is_zh else "Watching: NONE", fg="#C5C6C7", bg=self.bg_color, font=("Consolas", 10))
        self.lbl_symbol.pack()
        
        self.lbl_signal = tk.Label(self.root, text="操作信号: 观望" if self.is_zh else "SIGNAL: HOLD", fg="#66FCF1", bg=self.bg_color, font=("Consolas", 16, "bold"))
        self.lbl_signal.pack(pady=10)
        
        self.btn_exit = tk.Button(self.root, text="[X]", fg="#C3073F", bg=self.bg_color, bd=0, command=self.root.destroy, font=("Consolas", 8))
        self.btn_exit.place(x=self.width-25, y=5)
        
        self.btn_lang = tk.Button(self.root, text="[EN]", fg="#45A29E", bg=self.bg_color, bd=0, command=self.toggle_lang, font=("Consolas", 8))
        self.btn_lang.place(x=self.width-55, y=5)
        
        self.is_flashing = False

        self._last_latency = 0
        self._last_symbol = ""
        self._last_action = ""

    def toggle_lang(self):
        self.is_zh = not self.is_zh
        self.btn_lang.config(text="[中]" if not self.is_zh else "[EN]")
        self.lbl_title.config(text="量化核心状态" if self.is_zh else "QUANT CORE STATUS")
        
        if self._last_latency > 0:
            self.update_network_latency(self._last_latency)
        else:
            self.lbl_net.config(text="网络延迟: 等待响应" if self.is_zh else "Network: WAIT")
            
        if self._last_symbol:
            self.update_status(self._last_symbol, self._last_action)
        else:
            self.lbl_symbol.config(text="盯盘中: 无" if self.is_zh else "Watching: NONE")
            self.lbl_signal.config(text="操作信号: 观望 (HOLD)" if self.is_zh else "SIGNAL: HOLD")

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

    def update_network_latency(self, latency_ms: int):
        self._last_latency = latency_ms
        prefix = "API 延迟:" if self.is_zh else "API Latency:"
        self.lbl_net.config(text=f"{prefix} {latency_ms} ms")
        if latency_ms < 500:
            self.lbl_net.config(fg="#66FCF1")
        else:
            self.lbl_net.config(fg="#FCE181")

    def update_status(self, symbol: str, action: str):
        self._last_symbol = symbol
        self._last_action = action
        
        target_prefix = "扫描标的:" if self.is_zh else "Target:"
        signal_prefix = "信号指令:" if self.is_zh else "SIGNAL:"
        
        action_map = {
            "SCANNING...": "扫描中...",
            "HOLD": "观望 (HOLD)",
            "BUY": "买入 (BUY)",
            "SELL": "卖出 (SELL)",
            "SELL_ALL": "清仓 (SELL_ALL)"
        }
        
        display_action = action_map.get(action, action) if self.is_zh else action
        
        self.lbl_symbol.config(text=f"{target_prefix} {symbol}")
        self.lbl_signal.config(text=f"{signal_prefix} {display_action}")
        
        if action in ["BUY", "SELL", "SELL_ALL"]:
            self.trigger_alert()
            
    def _flash_bg(self, count):
        if count <= 0:
            self.root.configure(bg=self.bg_color)
            for widget in [self.lbl_title, self.lbl_net, self.lbl_symbol, self.lbl_signal, self.btn_exit, self.btn_lang]:
                widget.configure(bg=self.bg_color)
            self.is_flashing = False
            return
        
        current_bg = self.root.cget("bg")
        new_bg = self.alert_color if current_bg == self.bg_color else self.bg_color
        
        self.root.configure(bg=new_bg)
        for widget in [self.lbl_title, self.lbl_net, self.lbl_symbol, self.lbl_signal, self.btn_exit, self.btn_lang]:
            widget.configure(bg=new_bg)
            
        self.root.after(200, self._flash_bg, count - 1)

    def trigger_alert(self):
        if not self.is_flashing:
            self.is_flashing = True
            self._flash_bg(10)

    def start(self):
        self.root.mainloop()

# ==========================================
# 模拟测试环境 (Mock Testing Environment)
# ==========================================
def mock_system_events(hud: CyberpunkHUD):
    time.sleep(2)
    hud.update_network_latency(120)
    time.sleep(1)
    hud.update_status("00700.HK", "HOLD")
    time.sleep(2)
    hud.update_network_latency(850)
    time.sleep(2)
    hud.update_network_latency(230)
    hud.update_status("03690.HK", "BUY")
    send_mobile_notification("03690", "BUY", "RSI is 30, MACD Golden Cross, LLM reason: Strong recovery momentum.")

if __name__ == "__main__":
    app = CyberpunkHUD()
    t = Thread(target=mock_system_events, args=(app,), daemon=True)
    t.start()
    app.start()
