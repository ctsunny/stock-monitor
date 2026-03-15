# 🛒 FACHOST TW-NAT 库存监控

> 专门监控 [https://fachost.cloud/products/tw-nat](https://fachost.cloud/products/tw-nat) 页面所有套餐库存状态，有货立即 Bark 推送到 iPhone。

## ⚡ 一键安装并运行

```bash
apt install -y screen && curl -fsSL https://raw.githubusercontent.com/ctsunny/stock-monitor/main/fachost_tw_nat_monitor.py -o fachost_tw_nat_monitor.py && python3 -m pip install -U requests --break-system-packages && python3 fachost_tw_nat_monitor.py
```

> **说明**: Debian/Ubuntu 新系统限制系统级 pip，`--break-system-packages` 对 root 服务器完全安全。

## 🎮 菜单操作说明

启动后会显示主菜单：

```
状态  : 运行中 ●  /  已停止 ○
最近检测: 2026-03-15 21:33:27  第 3 轮
  ❌ Hinet-Nat-1: 售罄
  ❌ Seednet-Nat-1: 售罄
操作选项:
  1. 查看实时日志 (attach screen)
  2. 停止监控
  3. 修改配置并重启
  0. 退出
```

### 套餐多选方式

进入配置选套餐时，自动从页面拉取套餐列表，用以下操作：

```
[↑↓] 移动光标    [空格] 勾选/取消    [回车] 确定    [0] 监控全部

> [x] Hinet-Nat-1      ← 已勾选
  [ ] Seednet-Nat-1
  [x] Hinet-Nat-4      ← 已勾选
  [ ] Seednet-Nat-2
```

## 🖥️ SSH 断开后持续运行

监控通过 `screen` 在后台运行，关闭 SSH 不影响。再次 SSH 登录后直接运行脚本即可从菜单查看状态。

```bash
# 查看监控运行状态
 python3 fachost_tw_nat_monitor.py

# 手动 attach 实时日志
screen -r fachost-monitor
# Ctrl+A D 挂回后台
```

## 🔑 获取 Bark 密钥

1. iPhone 安装 [Bark App](https://apps.apple.com/app/bark-customed-notifications/id1403753865)
2. 打开 App，复制首页密钥（形如 `AbCdEfGhIjKl...`）
3. 粘贴到配置菜单的 Bark 密钥输入框

> 如果测试推送失败，在服务器运行以下命令验证：
> ```bash
> curl "https://api.day.app/你的KEY/测试/Bark正常"
> ```
> 返回 `{"code":200}` 即为 Key 正确。

## 📋 参数说明

| 参数 | 说明 |
|---|---|
| Bark 密钥 | Bark App 首页那串字符 |
| 检测频率 | 建议 15–30 秒，最小 5 秒 |
| 提醒方式 | `bark+critical` 可穿透静音，抢购必备 |
| 套餐选择 | 空格勾选，0 = 监控全部 |

## ⚠️ 注意事项

- 建议检测间隔 ≥ 10 秒，避免触发反爬
- 如网站前端改版可能需要更新解析规则
