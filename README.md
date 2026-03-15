# 🛒 商品库存抢购监控脚本

> Linux 运行 · Bark 推送 · 扫码选品 · 可配置频率

## 功能特性

- 📦 **多商品监控** —— 同时监控多个商品 URL
- 📲 **Bark 推送** —— 有货立即推送到 iPhone，支持普通/铃声/紧急三种提醒
- ⏱️ **可配置频率** —— 自定义扫码间隔（最低 5 秒）
- 🏪 **多平台支持** —— 京东（API 精准查询）+ 淘宝/天猫/亚马逊/苏宁/拼多多（通用 HTML 解析）
- 🔍 **扫码/粘贴 URL** —— 通过扫码枪或手动粘贴商品页面链接
- 💾 **配置持久化** —— 密钥、频率、商品列表自动保存
- 🎛️ **交互菜单 + CLI 参数** —— 两种使用方式

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/ctsunny/stock-monitor.git
cd stock-monitor
pip3 install -r requirements.txt
```

### 2. 运行（交互模式）

```bash
python3 monitor.py
```

首次运行会自动进入配置向导，输入 Bark 密钥即可。

### 3. 快速启动（CLI 参数）

```bash
# 指定 Bark 密钥并直接开始监控
python3 monitor.py --bark-key YOUR_BARK_KEY --start

# 设置扫码间隔 15 秒 + 紧急提醒
python3 monitor.py --bark-key YOUR_BARK_KEY --interval 15 --notify-mode bark+critical --start

# 添加一个商品并监控
python3 monitor.py --add 'https://item.jd.com/100012043978.html' --start

# 测试 Bark 推送
python3 monitor.py --bark-key YOUR_BARK_KEY --test-bark
```

## 获取 Bark 密钥

1. 在 iPhone 上安装 [Bark App](https://apps.apple.com/app/bark-customed-notifications/id1403753865)
2. 打开 App，复制显示的密钥（形如 `AbCdEfGhIjK...`）
3. 粘贴到脚本配置中

## 提醒方式说明

| 模式 | 说明 |
|------|------|
| `bark` | 普通推送，无特殊声音 |
| `bark+sound` | 推送 + 铃声提醒 |
| `bark+critical` | **紧急推送**，穿透静音模式，适合抢购 |

## 商品 URL 格式示例

| 平台 | URL 示例 |
|------|----------|
| 京东 | `https://item.jd.com/100012043978.html` |
| 淘宝 | `https://item.taobao.com/item.htm?id=...` |
| 天猫 | `https://detail.tmall.com/item.htm?id=...` |
| 亚马逊 | `https://www.amazon.cn/dp/...` |
| 苏宁 | `https://product.suning.com/...` |

## 扫码枪使用

大多数扫码枪会模拟键盘输入，扫描商品包装上的二维码/条形码后：
1. 如果扫出的是商品 URL → 直接粘贴到脚本 URL 输入框
2. 如果扫出的是商品 SKU 编号 → 需手动拼接为商品详情页 URL

> 建议使用手机扫码后分享链接复制，效果更好。

## 配置文件位置

| 文件 | 说明 |
|------|------|
| `~/.stock_monitor.json` | 主配置（Bark密钥、频率、提醒方式）|
| `~/.stock_products.json` | 商品监控列表 |

## CLI 参数总览

```
--setup              重新运行配置向导
--bark-key KEY       指定 Bark 密钥
--bark-server URL    指定 Bark 服务端（自建时使用）
--interval N         扫码间隔（秒）
--notify-mode MODE   提醒方式: bark | bark+sound | bark+critical
--add URL            添加商品 URL
--start              直接开始监控所有商品
--test-bark          测试 Bark 推送连通性
```

## 注意事项

- 京东商品使用官方库存 API，准确率较高
- 淘宝/天猫等平台登录后才可查看库存，建议配合 Cookie 方案（进阶）
- 扫码过于频繁可能触发反爬，建议间隔 ≥ 30 秒
- 本脚本仅供学习与个人使用
