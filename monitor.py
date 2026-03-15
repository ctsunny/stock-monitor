#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商品库存抢购监控脚本
支持：扫码选品 | Bark推送 | 可配置扫码频率 | 多种提醒方式
作者：github.com/ctsunny
"""

import requests
import time
import json
import os
import sys
import argparse
from datetime import datetime
from urllib.parse import urlparse, urlencode, quote

# ─────────────────────────────────────────
# 配置区域（也可通过命令行参数覆盖）
# ─────────────────────────────────────────
DEFAULT_CONFIG = {
    "bark_key": "",           # Bark 密钥（必填）
    "bark_server": "https://api.day.app",  # Bark 服务端地址
    "interval": 30,           # 扫码间隔（秒）
    "notify_mode": "bark",    # 提醒方式: bark | bark+sound | bark+critical
    "user_agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
    "timeout": 15,
    "max_retries": 3,
}

CONFIG_FILE = os.path.expanduser("~/.stock_monitor.json")

# ─────────────────────────────────────────
# 颜色输出
# ─────────────────────────────────────────
class Colors:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def cprint(color, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{Colors.RESET}")

def success(msg): cprint(Colors.GREEN,  "✅ " + msg)
def warn(msg):    cprint(Colors.YELLOW, "⚠️  " + msg)
def error(msg):   cprint(Colors.RED,    "❌ " + msg)
def info(msg):    cprint(Colors.CYAN,   "ℹ️  " + msg)
def bold(msg):    cprint(Colors.BOLD,   msg)

# ─────────────────────────────────────────
# 配置管理
# ─────────────────────────────────────────
def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            cfg.update(saved)
            info(f"已加载配置文件: {CONFIG_FILE}")
        except Exception as e:
            warn(f"配置文件读取失败: {e}")
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        info(f"配置已保存至: {CONFIG_FILE}")
    except Exception as e:
        warn(f"配置保存失败: {e}")

def setup_config(cfg):
    """首次运行交互式配置"""
    print()
    bold("═" * 50)
    bold("        商品库存监控 - 初始配置向导")
    bold("═" * 50)
    print()

    # Bark 密钥
    current_key = cfg.get("bark_key", "")
    prompt = f"请输入 Bark 密钥 [{current_key or '未设置'}]: "
    key = input(prompt).strip()
    if key:
        cfg["bark_key"] = key

    # Bark 服务端
    current_server = cfg.get("bark_server", DEFAULT_CONFIG["bark_server"])
    prompt = f"Bark 服务端地址 [{current_server}]: "
    server = input(prompt).strip()
    if server:
        cfg["bark_server"] = server.rstrip("/")

    # 提醒方式
    print()
    info("提醒方式选项：")
    print("  1. bark          - 普通推送")
    print("  2. bark+sound    - 推送+铃声")
    print("  3. bark+critical - 紧急推送（强提醒，穿透静音）")
    mode_map = {"1": "bark", "2": "bark+sound", "3": "bark+critical"}
    current_mode = cfg.get("notify_mode", "bark")
    choice = input(f"选择提醒方式 [当前: {current_mode}，输入1/2/3]: ").strip()
    if choice in mode_map:
        cfg["notify_mode"] = mode_map[choice]

    # 扫码频率
    current_interval = cfg.get("interval", 30)
    prompt = f"扫码间隔（秒）[当前: {current_interval}秒]: "
    interval = input(prompt).strip()
    if interval.isdigit() and int(interval) >= 5:
        cfg["interval"] = int(interval)
    elif interval and int(interval) < 5:
        warn("间隔太短，已设为最小值 5 秒")
        cfg["interval"] = 5

    save_config(cfg)
    return cfg

# ─────────────────────────────────────────
# Bark 推送
# ─────────────────────────────────────────
def send_bark(cfg, title, body, url=""):
    key    = cfg.get("bark_key", "")
    server = cfg.get("bark_server", DEFAULT_CONFIG["bark_server"]).rstrip("/")
    mode   = cfg.get("notify_mode", "bark")

    if not key:
        warn("Bark 密钥未设置，跳过推送")
        return False

    params = {
        "title": title,
        "body":  body,
        "icon":  "https://is1-ssl.mzstatic.com/image/thumb/Purple116/v4/3e/f3/8c/3ef38ce5-2d46-f36e-2d47-f0e5fe60b4c3/AppIcon-0-0-1x_U007emarketing-0-10-0-85-220.png/230x0w.webp",
        "group": "stock-monitor",
        "sound": "minuet",
    }

    if mode == "bark+critical":
        params["level"] = "critical"
        params["volume"] = "10"
    elif mode == "bark+sound":
        params["level"] = "active"

    if url:
        params["url"] = url

    api_url = f"{server}/{key}"

    try:
        resp = requests.post(api_url, json=params, timeout=10)
        if resp.status_code == 200:
            success(f"Bark 推送成功: {title}")
            return True
        else:
            warn(f"Bark 推送失败 HTTP {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        error(f"Bark 推送异常: {e}")
        return False

def test_bark(cfg):
    """测试 Bark 推送"""
    info("发送 Bark 测试消息...")
    return send_bark(cfg, "🔔 监控脚本测试", "Bark 推送配置成功！监控脚本已就绪。")

# ─────────────────────────────────────────
# 商品页面解析
# ─────────────────────────────────────────
SESSION = requests.Session()

def get_headers(cfg):
    return {
        "User-Agent": cfg.get("user_agent", DEFAULT_CONFIG["user_agent"]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

def fetch_page(url, cfg):
    """获取页面内容"""
    for attempt in range(cfg.get("max_retries", 3)):
        try:
            resp = SESSION.get(
                url,
                headers=get_headers(cfg),
                timeout=cfg.get("timeout", 15),
                allow_redirects=True
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            if attempt < cfg.get("max_retries", 3) - 1:
                warn(f"请求失败 (第{attempt+1}次): {e}, 3秒后重试...")
                time.sleep(3)
            else:
                error(f"请求失败（已达最大重试）: {e}")
                return None

def detect_platform(url):
    """根据 URL 判断平台"""
    domain = urlparse(url).netloc.lower()
    if "jd.com" in domain or "360buy" in domain:
        return "jd"
    elif "taobao.com" in domain or "tmall.com" in domain:
        return "taobao"
    elif "amazon" in domain:
        return "amazon"
    elif "suning.com" in domain:
        return "suning"
    elif "pinduoduo.com" in domain or "yangkeduo" in domain:
        return "pdd"
    else:
        return "generic"

def check_stock_generic(resp, url):
    """
    通用库存检测：
    解析页面 HTML 中的常见「无货/售罄/缺货」关键词
    若不包含则推测为有货
    """
    text = resp.text.lower()
    out_of_stock_keywords = [
        "无货", "售罄", "缺货", "补货中", "暂时缺货",
        "out of stock", "sold out", "unavailable",
        "currently unavailable", "加入购物车" and False,  # placeholder
    ]
    in_stock_keywords = [
        "加入购物车", "立即购买", "add to cart", "buy now",
        "有货", "现货", "in stock",
    ]

    for kw in out_of_stock_keywords:
        if isinstance(kw, str) and kw in text:
            return False, f"检测到关键词: [{kw}]"

    for kw in in_stock_keywords:
        if kw in text:
            return True, f"检测到关键词: [{kw}]"

    return None, "无法确定库存状态（页面无明确标志）"

def check_stock_jd_api(item_id, cfg):
    """京东库存 API 查询"""
    api = f"https://c0.3.cn/stock?skuId={item_id}&area=1_72_2799_0&venderId=0"
    resp = fetch_page(api, cfg)
    if resp:
        try:
            data = resp.json()
            stock_state = data.get("stock", {}).get("StockState", "")
            # 33=现货, 34=无货, 36=采购中
            if stock_state == "33":
                return True, f"京东库存状态: 现货 (StockState={stock_state})"
            else:
                return False, f"京东库存状态: 无货/采购中 (StockState={stock_state})"
        except Exception as e:
            warn(f"京东API解析失败: {e}")
    return None, "API请求失败"

def extract_jd_sku(url):
    """从京东 URL 提取 skuId"""
    import re
    match = re.search(r'/(\d+)\.html', url)
    return match.group(1) if match else None

def check_stock(url, cfg):
    """综合库存检查入口"""
    platform = detect_platform(url)
    info(f"平台识别: {platform.upper()} | {url[:60]}...")

    if platform == "jd":
        sku_id = extract_jd_sku(url)
        if sku_id:
            in_stock, msg = check_stock_jd_api(sku_id, cfg)
            return in_stock, msg

    # 通用 HTML 解析
    resp = fetch_page(url, cfg)
    if resp is None:
        return None, "页面请求失败"
    return check_stock_generic(resp, url)

# ─────────────────────────────────────────
# 商品管理（扫码/手动输入 URL 列表）
# ─────────────────────────────────────────
PRODUCT_LIST_FILE = os.path.expanduser("~/.stock_products.json")

def load_products():
    if os.path.exists(PRODUCT_LIST_FILE):
        try:
            with open(PRODUCT_LIST_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return []

def save_products(products):
    with open(PRODUCT_LIST_FILE, "w") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

def add_product_interactive(products):
    """交互式添加商品"""
    print()
    bold("─" * 40)
    info("添加监控商品")
    print("提示：直接粘贴商品页面 URL 或扫码仪扫描商品二维码后粘贴")
    url = input("商品 URL（回车取消）: ").strip()
    if not url:
        return products
    if not url.startswith("http"):
        error("请输入有效的 http/https URL")
        return products
    name = input(f"商品备注名称（可留空）: ").strip()
    if not name:
        name = urlparse(url).netloc + " 商品"
    product = {"name": name, "url": url, "added": datetime.now().isoformat()}
    products.append(product)
    save_products(products)
    success(f"已添加: {name}")
    return products

def list_products(products):
    if not products:
        warn("监控列表为空，请先添加商品")
        return
    print()
    bold("─" * 60)
    bold(f"  当前监控商品列表（共 {len(products)} 个）")
    bold("─" * 60)
    for i, p in enumerate(products, 1):
        print(f"  {Colors.CYAN}{i:2d}.{Colors.RESET} {Colors.BOLD}{p['name']}{Colors.RESET}")
        print(f"      {p['url'][:70]}..." if len(p['url']) > 70 else f"      {p['url']}")
    bold("─" * 60)

def remove_product_interactive(products):
    list_products(products)
    if not products:
        return products
    idx = input("输入要删除的商品编号（回车取消）: ").strip()
    if idx.isdigit() and 1 <= int(idx) <= len(products):
        removed = products.pop(int(idx) - 1)
        save_products(products)
        success(f"已删除: {removed['name']}")
    else:
        warn("无效编号")
    return products

# ─────────────────────────────────────────
# 主监控循环
# ─────────────────────────────────────────
def monitor_loop(products, cfg, selected_indices=None):
    """主监控循环"""
    if not products:
        error("监控列表为空！请先添加商品 (菜单选项 1)")
        return

    to_monitor = []
    if selected_indices:
        for i in selected_indices:
            if 0 <= i < len(products):
                to_monitor.append(products[i])
    else:
        to_monitor = products

    if not to_monitor:
        error("没有有效的商品可监控")
        return

    interval   = cfg.get("interval", 30)
    bark_key   = cfg.get("bark_key", "")
    alerted    = set()   # 已推送过的商品 URL（避免重复推送）

    print()
    bold("═" * 60)
    bold(f"  开始监控 {len(to_monitor)} 个商品，扫码间隔 {interval} 秒")
    bold(f"  提醒方式: {cfg.get('notify_mode', 'bark')}")
    bold(f"  Bark 密钥: {'✅ 已配置' if bark_key else '❌ 未配置'}")
    bold("  按 Ctrl+C 停止监控")
    bold("═" * 60)
    print()

    round_count = 0
    try:
        while True:
            round_count += 1
            info(f"第 {round_count} 轮扫码开始...")

            for product in to_monitor:
                name = product["name"]
                url  = product["url"]

                in_stock, msg = check_stock(url, cfg)

                if in_stock is True:
                    success(f"【有货】{name} | {msg}")
                    if url not in alerted:
                        alerted.add(url)
                        send_bark(
                            cfg,
                            title=f"🛒 有货提醒！{name}",
                            body=f"{msg}\n\n点击前往购买",
                            url=url
                        )
                elif in_stock is False:
                    warn(f"【无货】{name} | {msg}")
                    alerted.discard(url)  # 重置，下次有货时重新推送
                else:
                    warn(f"【未知】{name} | {msg}")

                time.sleep(1)  # 每个商品间隔 1 秒，避免被封

            next_check = datetime.now().strftime("%H:%M:%S")
            info(f"本轮完成，{interval} 秒后进行下一轮... (下次: {next_check})")
            print()
            time.sleep(interval)

    except KeyboardInterrupt:
        print()
        bold("监控已停止。")

# ─────────────────────────────────────────
# 交互主菜单
# ─────────────────────────────────────────
def main_menu(cfg, products):
    while True:
        print()
        bold("═" * 50)
        bold("     🛒 商品库存抢购监控脚本")
        bold("═" * 50)
        print(f"  {Colors.CYAN}1.{Colors.RESET} 添加监控商品（粘贴/扫码 URL）")
        print(f"  {Colors.CYAN}2.{Colors.RESET} 查看监控列表")
        print(f"  {Colors.CYAN}3.{Colors.RESET} 删除监控商品")
        print(f"  {Colors.CYAN}4.{Colors.RESET} 开始监控（全部商品）")
        print(f"  {Colors.CYAN}5.{Colors.RESET} 开始监控（选择商品）")
        print(f"  {Colors.CYAN}6.{Colors.RESET} 修改配置（Bark密钥/频率/提醒方式）")
        print(f"  {Colors.CYAN}7.{Colors.RESET} 测试 Bark 推送")
        print(f"  {Colors.CYAN}0.{Colors.RESET} 退出")
        bold("─" * 50)

        choice = input("请选择: ").strip()

        if choice == "1":
            products = add_product_interactive(products)
        elif choice == "2":
            list_products(products)
        elif choice == "3":
            products = remove_product_interactive(products)
        elif choice == "4":
            monitor_loop(products, cfg)
        elif choice == "5":
            list_products(products)
            if products:
                indices_input = input("输入商品编号（逗号分隔，例如: 1,3,5）: ").strip()
                try:
                    indices = [int(x.strip()) - 1 for x in indices_input.split(",")]
                    monitor_loop(products, cfg, selected_indices=indices)
                except ValueError:
                    error("输入格式有误")
        elif choice == "6":
            cfg = setup_config(cfg)
        elif choice == "7":
            test_bark(cfg)
        elif choice == "0":
            bold("再见！")
            sys.exit(0)
        else:
            warn("无效选项，请重试")

# ─────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="商品库存抢购监控脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 monitor.py                        # 交互菜单模式
  python3 monitor.py --setup                # 重新配置
  python3 monitor.py --bark-key YOUR_KEY    # 指定 Bark 密钥
  python3 monitor.py --interval 15          # 每15秒扫一次
  python3 monitor.py --add URL              # 直接添加商品
  python3 monitor.py --start                # 直接开始监控全部商品
        """
    )
    parser.add_argument("--setup",       action="store_true", help="重新运行配置向导")
    parser.add_argument("--bark-key",    type=str,            help="Bark 密钥")
    parser.add_argument("--bark-server", type=str,            help="Bark 服务端地址")
    parser.add_argument("--interval",    type=int,            help="扫码间隔（秒，最小5）")
    parser.add_argument("--notify-mode", type=str,
                        choices=["bark", "bark+sound", "bark+critical"],
                        help="提醒方式")
    parser.add_argument("--add",         type=str,            help="添加商品 URL")
    parser.add_argument("--start",       action="store_true", help="直接开始监控")
    parser.add_argument("--test-bark",   action="store_true", help="测试 Bark 推送")
    return parser.parse_args()

def main():
    args = parse_args()
    cfg  = load_config()

    # 命令行覆盖配置
    if args.bark_key:
        cfg["bark_key"] = args.bark_key
        save_config(cfg)
    if args.bark_server:
        cfg["bark_server"] = args.bark_server.rstrip("/")
        save_config(cfg)
    if args.interval:
        cfg["interval"] = max(5, args.interval)
        save_config(cfg)
    if args.notify_mode:
        cfg["notify_mode"] = args.notify_mode
        save_config(cfg)

    products = load_products()

    if args.setup or not cfg.get("bark_key"):
        cfg = setup_config(cfg)

    if args.test_bark:
        test_bark(cfg)
        return

    if args.add:
        url  = args.add
        name = urlparse(url).netloc + " 商品"
        products.append({"name": name, "url": url, "added": datetime.now().isoformat()})
        save_products(products)
        success(f"已添加: {name}")

    if args.start:
        monitor_loop(products, cfg)
        return

    # 默认进入交互菜单
    main_menu(cfg, products)

if __name__ == "__main__":
    main()
