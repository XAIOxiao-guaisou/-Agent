import os
import urllib3

# === 全局网络与基础设施配置 (Global Network & Infrastructure Configuration) ===

# 代理配置 (Proxy configuration)
# 请根据你的实际网络环境 (如 Clash/V2Ray) 调整端口号，默认为 7890
# Please adjust the port according to your actual proxy environment (e.g., Clash), default is 7890.
PROXY_HOST = "127.0.0.1"
PROXY_PORT = "7890"

# 构建代理字典格式，供 Requests 等应用层直接调用
# Build proxy dictionary for application-layer calls like Requests
PROXIES = {
    "http": f"http://{PROXY_HOST}:{PROXY_PORT}",
    "https": f"http://{PROXY_HOST}:{PROXY_PORT}",
}

# 忽略 urllib3 的 HTTPS 安全警告 (防止控制台被警告刷屏)
# Suppress urllib3 HTTPS warnings (Prevent console from being flooded)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def setup_global_proxy():
    """
    配置全局环境变量接管所有底层请求 (如底层库发出的请求)
    Configure global environment variables to intercept all underlying requests.
    """
    os.environ['HTTP_PROXY'] = f"http://{PROXY_HOST}:{PROXY_PORT}"
    os.environ['HTTPS_PROXY'] = f"http://{PROXY_HOST}:{PROXY_PORT}"
    os.environ['ALL_PROXY'] = f"socks5://{PROXY_HOST}:{PROXY_PORT}"
    print(f"[*] 全局代理已挂载 (Global proxy mounted): {PROXY_HOST}:{PROXY_PORT}")

if __name__ == "__main__":
    setup_global_proxy()
    print("[*] 基础设施模块验证完成。Infrastructure module validation complete.")
