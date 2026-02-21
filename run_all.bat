@echo off
chcp 65001 > nul
echo.
echo  ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗████████╗
echo  ██╔══██╗╚██╗ ██╔╝██╔══██╗████╗  ██║╚══██╔══╝
echo  ██████╔╝ ╚████╔╝ ███████║██╔██╗ ██║   ██║
echo  ██╔═══╝   ╚██╔╝  ██╔══██║██║╚██╗██║   ██║
echo  ██║        ██║   ██║  ██║██║ ╚████║   ██║
echo  ╚═╝        ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝
echo.
echo        DeepSeek Quant Engine v1.0
echo        ===========================
echo        一键启动量化交易微服务三虎架构
echo        [Brain Daemon] [Tick Radar] [Web HUD]
echo.

echo [*] 激活虚拟环境...
call venv\Scripts\activate

echo [*] 检查依赖...
python -c "import akshare, streamlit, schedule" 2>nul || (
    echo [!] 正在安装缺失依赖...
    pip install akshare streamlit schedule matplotlib tqdm
)

echo.
echo [*] 正在点火...交易矩阵即将启动！
echo [*] Streamlit 指挥中心地址: http://localhost:8501
echo [*] 按 Ctrl+C 可触发优雅停机（自动保存持仓状态）
echo.
python main.py

pause
