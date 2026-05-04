#!/bin/bash
# Klipper Xiaomi Thermometer 安装脚本
# 用法: curl -sSL https://cdn.jsdelivr.net/gh/xmg101/klipper-xiaomi-thermometer@master/install.sh | bash
# 或: bash install.sh [klipper_path]

set -e

KLIPPER_PATH="${1:-$HOME/klipper}"
RAW_BASE="https://cdn.jsdelivr.net/gh/xmg101/klipper-xiaomi-thermometer@master"

echo "=== Klipper Xiaomi Thermometer 安装 ==="
echo "Klipper 路径: $KLIPPER_PATH"
echo ""

# 检查目录
EXTRAS_DIR="$KLIPPER_PATH/klippy/extras"
if [ ! -d "$EXTRAS_DIR" ]; then
    echo "[ERROR] extras 目录不存在: $EXTRAS_DIR"
    echo "请指定正确的 Klipper 路径: bash install.sh /path/to/klipper"
    exit 1
fi

# 安装 micloud
echo "[1/3] 安装 micloud 依赖..."
if python3 -c "import micloud" 2>/dev/null; then
    echo "  [OK] micloud 已安装"
else
    pip3 install --break-system-packages micloud 2>/dev/null \
      || pip3 install --user micloud 2>/dev/null \
      || pip3 install micloud 2>/dev/null \
      || pip3 install --break-system-packages git+https://github.com/Squishy47/micloud.git \
      || {
        echo "  [ERROR] micloud 安装失败"
        echo "  请手动安装: pip3 install --break-system-packages micloud"
        exit 1
      }
    echo "  [OK] micloud 安装完成"
fi

# 下载模块（直接用 curl，不依赖本地文件）
echo "[2/3] 安装 xiaomi_thermometer 模块..."
if curl -sSL "$RAW_BASE/xiaomi_thermometer.py" -o "$EXTRAS_DIR/xiaomi_thermometer.py"; then
    echo "  [OK] xiaomi_thermometer.py -> $EXTRAS_DIR/"
else
    echo "  [ERROR] 下载失败，手动下载: $RAW_BASE/xiaomi_thermometer.py"
    exit 1
fi

# 注册到 temperature_sensors.cfg
echo "[3/3] 注册模块..."
CFG_FILE="$EXTRAS_DIR/temperature_sensors.cfg"
if grep -q "\[xiaomi_thermometer\]" "$CFG_FILE"; then
    echo "  [SKIP] 已注册"
else
    sed -i '/^\[temperature_combined\]$/a \\n# Load "xiaomi_thermometer" sensor\n[xiaomi_thermometer]' "$CFG_FILE"
    echo "  [OK] 已注册"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "请在 printer.cfg 中添加:"
echo ""
echo "  [xiaomi_thermometer chamber]"
echo "  mi_account: 你的小米账号"
echo "  mi_password: 你的小米密码"
echo "  # min_temp: 0"
echo "  # max_temp: 50"
echo ""
echo "然后重启 Klipper: sudo systemctl restart klipper"
