@echo off
chcp 65001 > nul
echo.
echo =======================================================
echo   DeepSeek Quant - 选股雷达 [每日定时守护模式]
echo   将在每个工作日 16:18 港股收盘后自动扫描 Top 20
echo =======================================================
echo.
echo [*] 激活虚拟环境...
call venv\Scripts\activate

echo [*] 启动定时守护进程 (按 Ctrl+C 退出)...
python market_scanner.py --schedule

pause
