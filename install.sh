#!/bin/bash
set -e

echo ""
echo "====================================================="
echo "   🛒  FACHOST TW-NAT 库存监控 - 安装向导"
echo "====================================================="
echo ""

# 安装依赖
if ! command -v screen &>/dev/null; then
    echo "[步骤1] 安装 screen..."
    apt-get install -y -q screen
else
    echo "[步骤1] screen 已安装 ✓"
fi

echo "[步骤2] 下载监控脚本..."
curl -fsSL https://raw.githubusercontent.com/ctsunny/stock-monitor/main/fachost_tw_nat_monitor.py \
    -o /usr/local/bin/fachost-monitor
chmod +x /usr/local/bin/fachost-monitor

echo "[步骤3] 安装 Python 依赖..."
python3 -m pip install -q -U requests --break-system-packages 2>/dev/null \
    || pip3 install -q -U requests 2>/dev/null \
    || python3 -m pip install -q -U requests

echo ""
echo "[安装完成] 以后直接运行:"
echo ""
echo "   fachost-monitor"
echo ""
echo "====================================================="
echo ""

python3 /usr/local/bin/fachost-monitor
