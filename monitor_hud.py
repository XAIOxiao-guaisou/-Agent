import tkinter as tk
from threading import Thread
import time
import requests
import json

# ==========================================
# Phase 5: Visual Monitoring Center (Tkinter HUD)
# ==========================================

# 预设 Server酱 Webhook (请替换为您真实的 SendKey)
# Preset ServerChan Webhook (Please replace with your real SendKey)
SERVER_CHAN_SENDKEY = "SCTxxxxxxxxxxxxxxxxxxxxx"

def send_mobile_notification(symbol: str, action: str, reason: str):
    """
    通过 Server酱 发送微信/手机推送通知
    Push notification to mobile via ServerChan.
    """
    if SERVER_CHAN_SENDKEY.startswith("SCTx"):
        print(f"[!] 通知拦截: 未配置真实的 Server酱 Key, 本地打印 -> {symbol} | {action} | {reason}")
        return
        
    url = f"https://sctapi.ftqq.com/{SERVER_CHAN_SENDKEY}.send"
    title = f"【量化信号】{symbol} 执行 {action}"
    desp = f"### 动作: **{action}**\n\n### 标的: {symbol}\n\n### AI与风控综合理由:\n{reason}\n\n*请及时前往券商APP进行复核下单。*"
    
    payload = {"title": title, "desp": desp}
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("[+] 手机推送下发成功")
    except Exception as e:
        print(f"[-] 手机推送下发失败: {e}")

class CyberpunkHUD:
    def __init__(self):
        """
        赛博朋克风格透明 HUD 监控台
        Cyberpunk Style Transparent HUD Monitor.
        """
        self.root = tk.Tk()
        self.root.title("DeepSeek Quant HUD")
        
        # 极简/无边框设定 (Minimalist/Borderless)
        self.root.overrideredirect(True)
        # 获取屏幕宽度并将其放在右上角 (Place at top right)
        screen_width = self.root.winfo_screenwidth()
        self.width = 320
        self.height = 150
        self.root.geometry(f"{self.width}x{self.height}+{screen_width - self.width - 20}+50")
        
        # 透明度设定 (Transparency)
        self.root.attributes('-alpha', 0.8)
        # 始终置顶窗体 (Always on top)
        self.root.attributes('-topmost', True)
        
        # 深色赛博风背景 (Dark Cyberpunk Background)
        self.root.configure(bg="#0B0C10")
        self.bg_color = "#0B0C10"
        self.alert_color = "#C3073F" # 红色闪烁警报色
        
        # 拖拽窗口功能 (Drag window function)
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)

        # 布局控件 (Layout Widgets)
        self.lbl_title = tk.Label(self.root, text="QUANT CORE STATUS", fg="#66FCF1", bg=self.bg_color, font=("Consolas", 12, "bold"))
        self.lbl_title.pack(pady=5)
        
        self.lbl_net = tk.Label(self.root, text="Network: WAIT", fg="#45A29E", bg=self.bg_color, font=("Consolas", 10))
        self.lbl_net.pack()
        
        self.lbl_symbol = tk.Label(self.root, text="Watching: NONE", fg="#C5C6C7", bg=self.bg_color, font=("Consolas", 10))
        self.lbl_symbol.pack()
        
        self.lbl_signal = tk.Label(self.root, text="SIGNAL: HOLD", fg="#66FCF1", bg=self.bg_color, font=("Consolas", 16, "bold"))
        self.lbl_signal.pack(pady=10)
        
        # 退出按钮 (Exit button)
        self.btn_exit = tk.Button(self.root, text="[X]", fg="#C3073F", bg=self.bg_color, bd=0, command=self.root.destroy, font=("Consolas", 8))
        self.btn_exit.place(x=self.width-25, y=5)
        
        self.is_flashing = False

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
        self.lbl_net.config(text=f"API Latency: {latency_ms} ms")
        if latency_ms < 500:
            self.lbl_net.config(fg="#66FCF1") # Green/Cyan
        else:
            self.lbl_net.config(fg="#FCE181") # Yellow/Warning

    def update_status(self, symbol: str, action: str):
        self.lbl_symbol.config(text=f"Target: {symbol}")
        self.lbl_signal.config(text=f"SIGNAL: {action}")
        
        if action in ["BUY", "SELL", "SELL_ALL"]:
            self.trigger_alert()
            
    def _flash_bg(self, count):
        if count <= 0:
            self.root.configure(bg=self.bg_color)
            for widget in [self.lbl_title, self.lbl_net, self.lbl_symbol, self.lbl_signal, self.btn_exit]:
                widget.configure(bg=self.bg_color)
            self.is_flashing = False
            return
            
        # 切换颜色 (Toggle color)
        current_bg = self.root.cget("bg")
        new_bg = self.alert_color if current_bg == self.bg_color else self.bg_color
        
        self.root.configure(bg=new_bg)
        for widget in [self.lbl_title, self.lbl_net, self.lbl_symbol, self.lbl_signal, self.btn_exit]:
            widget.configure(bg=new_bg)
            
        self.root.after(200, self._flash_bg, count - 1)

    def trigger_alert(self):
        """触发背景闪烁警报 (Trigger background flash alert)"""
        if not self.is_flashing:
            self.is_flashing = True
            self._flash_bg(10) # 闪烁 10 次 (Flash 10 times)

    def start(self):
        self.root.mainloop()

# ==========================================
# 模拟测试环境 (Mock Testing Environment)
# ==========================================
def mock_system_events(hud: CyberpunkHUD):
    """模拟系统后台运行抛出事件"""
    time.sleep(2)
    # 模拟网络心跳
    hud.update_network_latency(120)
    time.sleep(1)
    hud.update_status("00700.HK", "HOLD")
    time.sleep(2)
    hud.update_network_latency(850)
    
    time.sleep(2)
    # 模拟发现严重机会/危机，触发警报
    hud.update_network_latency(230)
    hud.update_status("03690.HK", "BUY")
    send_mobile_notification("03690", "BUY", "RSI is 30, MACD Golden Cross, LLM reason: Strong recovery momentum.")

if __name__ == "__main__":
    app = CyberpunkHUD()
    # 启动后台模拟线程，不阻塞 UI 线程
    # Start a background mock thread to avoid blocking the UI thread
    t = Thread(target=mock_system_events, args=(app,), daemon=True)
    t.start()
    
    app.start()
