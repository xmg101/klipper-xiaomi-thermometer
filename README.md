# Klipper Xiaomi Thermometer

通过小米云 API 读取米家蓝牙温湿度计温度，集成到 Klipper 温度系统。

支持：米家蓝牙温湿度计 3 mini 等通过蓝牙网关连接小米云的设备。

## 安装

```bash
curl -sSL https://raw.githubusercontent.com/xmg101/klipper-xiaomi-thermometer/main/install.sh | bash
```

如果 Klipper 不在 `~/klipper`，指定路径：

```bash
bash install.sh /custom/path/to/klipper
```

## 配置

在 `printer.cfg` 中添加：

```ini
[xiaomi_thermometer chamber]
mi_account: 你的小米账号
mi_password: 你的小米密码
min_temp: 0
max_temp: 50
```

可选参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `mi_country` | `cn` | 小米账号区域: cn, de, us, ru, sg |
| `query_interval` | `5.0` | 查询间隔(秒)，最小 1.0 |

## 故障排查

如果日志显示找不到温度计，查看日志中的 "Available devices" 列表，找到你的设备 model 值，修改 `xiaomi_thermometer.py` 中的 `XIAOMI_THERMOMETER_MODEL` 常量。
