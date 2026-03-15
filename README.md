# 🛒 FACHOST TW-NAT 库存监控

> 专门监控 [https://fachost.cloud/products/tw-nat](https://fachost.cloud/products/tw-nat) 页面下所有套餐的库存状态，有货立即发送 Bark 提醒到 iPhone。

## ⚡ 一键运行

> 替换 `YOUR_BARK_KEY` 为你自己的 Bark 密钥后执行：

```bash
curl -fsSL https://raw.githubusercontent.com/ctsunny/stock-monitor/main/fachost_tw_nat_monitor.py -o fachost_tw_nat_monitor.py && python3 -m pip install -U requests && python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY' --interval 15
```

> 如提示 `No module named pip`，先执行：
> ```bash
> apt-get install -y python3-pip
> ```

只监控指定套餐（如只盯 Hinet-Nat-1 和 Seednet-Nat-1）：

```bash
curl -fsSL https://raw.githubusercontent.com/ctsunny/stock-monitor/main/fachost_tw_nat_monitor.py -o fachost_tw_nat_monitor.py && python3 -m pip install -U requests && python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY' --watch 'Hinet-Nat-1,Seednet-Nat-1' --interval 15 --notify-mode bark+critical
```

## 🔑 获取 Bark 密钥

1. iPhone 安装 [Bark App](https://apps.apple.com/app/bark-customed-notifications/id1403753865)
2. 打开 App，复制首页密钥（形如 `AbCdEfGhIjKl...`）
3. 粘贴到 `--bark-key` 参数

## 📦 功能特性

- 固定监控 `TW-NAT` 页面所有套餐
- 自动识别卡片中「立即购买」和「已售罄」状态
- Bark 推送支持三种方式，抢购建议用 `bark+critical`
- 避免重复推送：同一套餐有货只推一次，恢复售罄后重置
- 配置持久化，重启后自动读取

## 🚀 常用命令

**交互式配置**
```bash
python3 fachost_tw_nat_monitor.py --setup
```

**测试 Bark 是否通**
```bash
python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY' --test
```

**监控全部套餐（20秒/次）**
```bash
python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY'
```

**紧急提醒模式（穿透静音）**
```bash
python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY' --interval 10 --notify-mode bark+critical
```

**后台运行（screen）**
```bash
screen -S fachost
python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY' --interval 15
# Ctrl+A D 挂后台
```

**后台运行（nohup）**
```bash
nohup python3 fachost_tw_nat_monitor.py --bark-key 'YOUR_BARK_KEY' --interval 15 > fachost.log 2>&1 &
tail -f fachost.log
```

## 📋 参数说明

| 参数 | 说明 |
|---|---|
| `--bark-key KEY` | Bark 密钥（必填） |
| `--bark-server URL` | Bark 服务端，默认 `https://api.day.app`（自建时填写） |
| `--interval N` | 检测间隔秒数，最小 5，默认 20 |
| `--notify-mode` | `bark` 普通 / `bark+sound` 铃声 / `bark+critical` 穿透静音 |
| `--watch "名称1,名称2"` | 只监控指定套餐，留空=全部监控 |
| `--setup` | 交互式配置向导 |
| `--test` | 发送测试 Bark 消息 |

## 🏷️ 套餐名称参考

页面当前套餐（均可用于 `--watch` 参数）：

```
Hinet-Nat-1
Seednet-Nat-1
Hinet-Nat-4
Seednet-Nat-2
```

## 📁 配置文件位置

```bash
~/.fachost_tw_nat_monitor.json
```

## ⚠️ 注意事项

- 本脚本专门针对 `fachost.cloud/products/tw-nat` 页面结构定制
- 如网站前端改版，可能需要更新解析规则
- 建议检测间隔 ≥ 10 秒，避免触发反爬
