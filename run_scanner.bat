@echo off
chcp 65001 > nul
echo =======================================================
echo          DeepSeek Quant - 市场全景选股雷达启动
echo                  (Phase 17 Screener)
echo =======================================================
echo.
echo [*] 正在隔离并验证虚拟环境 (Activating Python venv)...
call venv\Scripts\activate

echo [*] 正在启动高级扫描与绘图引擎...
python market_scanner.py

echo.
echo =======================================================
echo [*] 雷达扫描完毕！请查看根目录下的 PNG 和 CSV 分析报告。
echo [*] 后台极速盯盘守护进程已自动接纳 Top 5 猎物。
echo =======================================================
pause
