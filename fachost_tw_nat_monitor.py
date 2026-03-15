#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FACHOST TW-NAT 专用库存监控脚本
监控: https://fachost.cloud/products/tw-nat
有库存立即发送 Bark 提醒
作者: github.com/ctsunny
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import requests

URL = "https://fachost.cloud/products/tw-nat"
CONFIG_FILE = os.path.expanduser("~/.fachost_tw_nat_monitor.json")

DEFAULT_CONFIG = {
    "bark_key": "",
    "bark_server": "https://api.day.app",
    "interval": 20,
    "notify_mode": "bark",
    "watch_names": [],
    "timeout": 15,
}


class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"


def now():
    return datetime.now().strftime("%H:%M:%S")


def log(msg, color=C.RESET):
    print(f"{color}[{now()}] {msg}{C.RESET}")


def log_ok(msg):   log(msg, C.GREEN)
def log_warn(msg): log(msg, C.YELLOW)
def log_err(msg):  log(msg, C.RED)
def log_info(msg): log(msg, C.CYAN)


def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    log_info(f"配置已保存: {CONFIG_FILE}")


def send_bark(cfg, title, body, jump_url=""):
    if not cfg.get("bark_key"):
        log_warn("未设置 Bark 密钥，跳过推送")
        return False

    payload = {
        "title": title,
        "body": body,
        "group": "fachost-tw-nat",
        "sound": "minuet",
    }

    mode = cfg.get("notify_mode", "bark")
    if mode == "bark+sound":
        payload["level"] = "active"
    elif mode == "bark+critical":
        payload["level"] = "critical"
        payload["volume"] = "10"

    if jump_url:
        payload["url"] = jump_url

    api = f"{cfg['bark_server'].rstrip('/')}/{cfg['bark_key']}"
    try:
        r = requests.post(api, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log_err(f"Bark 请求失败: {e}")
        return False


def fetch_html(cfg):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(URL, headers=headers, timeout=cfg.get("timeout", 15))
    r.raise_for_status()
    return r.text


def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_cards(html):
    cards = []
    pattern = re.compile(
        r'<div class="flex flex-col bg-background-secondary border border-neutral rounded-xl p-6 gap-4 relative'
        r'.*?<h2[^>]*>(.*?)</h2>'
        r'(.*?)'
        r'<div class="mt-auto">(.*?)</div>\s*</div>',
        re.S,
    )

    for m in pattern.finditer(html):
        name   = clean_text(m.group(1))
        middle = m.group(2)
        tail   = m.group(3)
        full   = middle + "\n" + tail

        disabled = (
            "cursor-not-allowed" in tail
            or "pointer-events-none" in tail
            or "bg-neutral-200" in tail
            or "text-neutral-500" in tail
        )
        sold_out = (
            "已售罄" in full
            or "sold out" in full.lower()
            or "bg-red-100" in full
            or "text-red-600" in full
        )
        buy_now = (
            "立即购买" in full
            or "buy now" in full.lower()
            or "order now" in full.lower()
            or "bg-green-100" in full
            or "text-green-600" in full
        )

        in_stock = buy_now and not disabled
        if not buy_now and sold_out:
            in_stock = False

        if name:
            cards.append({
                "name": name,
                "in_stock": in_stock,
                "sold_out": sold_out,
                "buy_now": buy_now,
                "disabled": disabled,
            })

    return cards


def filter_cards(cards, watch_names):
    if not watch_names:
        return cards
    wanted = {x.strip().lower() for x in watch_names if x.strip()}
    return [c for c in cards if c["name"].strip().lower() in wanted]


def interactive_menu(cfg):
    """
    启动时弹出交互菜单，让用户输入 Bark Key 等配置，
    然后自动进入监控循环，无需再执行任何额外命令。
    """
    print()
    print(C.BOLD + "=" * 54 + C.RESET)
    print(C.BOLD + "   🛒  FACHOST TW-NAT 库存监控" + C.RESET)
    print(C.BOLD + "   " + URL + C.RESET)
    print(C.BOLD + "=" * 54 + C.RESET)
    print()

    # ── Bark 密钥 ──────────────────────────────────────────
    cur_key = cfg.get("bark_key", "")
    hint = f"[已保存: {cur_key[:6]}...{cur_key[-4:]}]" if len(cur_key) > 10 else "[未设置]"
    bark_key = input(f"  Bark 密钥 {hint}（直接回车保留原值）: ").strip()
    if bark_key:
        cfg["bark_key"] = bark_key

    # ── 检测频率 ────────────────────────────────────────────
    interval_input = input(f"  检测频率秒数 [当前: {cfg.get('interval', 20)}]（直接回车保留）: ").strip()
    if interval_input.isdigit():
        cfg["interval"] = max(5, int(interval_input))

    # ── 提醒方式 ────────────────────────────────────────────
    print()
    print("  提醒方式:")
    print("    1. bark          普通推送")
    print("    2. bark+sound    有铃声")
    print("    3. bark+critical 穿透静音 ★ 抢购推荐")
    mode_map = {"1": "bark", "2": "bark+sound", "3": "bark+critical"}
    cur_mode = cfg.get("notify_mode", "bark")
    cur_num  = {v: k for k, v in mode_map.items()}.get(cur_mode, "1")
    choice = input(f"  选择 1/2/3 [当前: {cur_num}]（直接回车保留）: ").strip()
    if choice in mode_map:
        cfg["notify_mode"] = mode_map[choice]

    # ── 指定套餐 ────────────────────────────────────────────
    print()
    print("  已知套餐名: Hinet-Nat-1 / Seednet-Nat-1 / Hinet-Nat-4 / Seednet-Nat-2")
    cur_watch = ", ".join(cfg.get("watch_names", [])) or "全部"
    names_input = input(f"  指定监控套餐（逗号分隔，留空=全部）[当前: {cur_watch}]: ").strip()
    if names_input:
        cfg["watch_names"] = [x.strip() for x in names_input.split(",") if x.strip()]
    elif names_input == "" and cur_watch == "全部":
        cfg["watch_names"] = []

    save_config(cfg)

    # ── 测试推送确认 ────────────────────────────────────────
    print()
    do_test = input("  发送 Bark 测试消息？(y/N): ").strip().lower()
    if do_test == "y":
        ok = send_bark(cfg, "FACHOST 监控测试", "Bark 配置正常，监控即将启动。", URL)
        log(f"测试推送: {'成功 ✅' if ok else '失败 ❌'}")

    print()
    return cfg


def monitor(cfg):
    watch_names = cfg.get("watch_names", [])
    alerted = set()
    round_no = 0

    print(C.BOLD + "=" * 54 + C.RESET)
    print(C.BOLD + f"  ▶ 监控启动" + C.RESET)
    print(C.BOLD + f"  频率 : {cfg['interval']} 秒/次" + C.RESET)
    print(C.BOLD + f"  方式 : {cfg.get('notify_mode', 'bark')}" + C.RESET)
    print(C.BOLD + f"  套餐 : {', '.join(watch_names) if watch_names else '全部'}" + C.RESET)
    print(C.BOLD + "  Ctrl+C 停止" + C.RESET)
    print(C.BOLD + "=" * 54 + C.RESET)
    print()

    while True:
        round_no += 1
        log_info(f"第 {round_no} 轮检测...")
        try:
            html  = fetch_html(cfg)
            cards = parse_cards(html)
            cards = filter_cards(cards, watch_names)

            if not cards:
                log_warn("未解析到目标套餐，页面结构可能有变化")
            else:
                for c in cards:
                    if c["in_stock"]:
                        log_ok(f"✅ 有货: {c['name']}")
                        if c["name"] not in alerted:
                            alerted.add(c["name"])
                            ok = send_bark(
                                cfg,
                                title=f"🛒 FACHOST 有库存: {c['name']}",
                                body=f"{c['name']} 已可购买！立即打开页面下单。",
                                jump_url=URL,
                            )
                            log_ok(f"Bark 推送: {'成功 ✅' if ok else '失败 ❌'}")
                    else:
                        log_warn(f"❌ 售罄: {c['name']}")
                        alerted.discard(c["name"])

        except KeyboardInterrupt:
            print()
            log_info("监控已停止。")
            sys.exit(0)
        except Exception as e:
            log_err(f"检测异常: {e}")

        log_info(f"{cfg['interval']} 秒后下一轮...")
        print()
        try:
            time.sleep(max(5, int(cfg["interval"])))
        except KeyboardInterrupt:
            print()
            log_info("监控已停止。")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="FACHOST TW-NAT 库存提醒",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 fachost_tw_nat_monitor.py                   ← 启动菜单配置后自动监控
  python3 fachost_tw_nat_monitor.py --bark-key KEY    ← 跳过菜单直接监控
  python3 fachost_tw_nat_monitor.py --bark-key KEY --watch 'Hinet-Nat-1,Seednet-Nat-1' --interval 10
  python3 fachost_tw_nat_monitor.py --bark-key KEY --test
        """,
    )
    parser.add_argument("--bark-key",     type=str,  help="Bark 密钥（提供则跳过菜单）")
    parser.add_argument("--bark-server",  type=str,  help="Bark 服务端地址")
    parser.add_argument("--interval",     type=int,  help="检测频率秒数（最小5）")
    parser.add_argument("--notify-mode",  type=str,
                        choices=["bark", "bark+sound", "bark+critical"],
                        help="提醒方式")
    parser.add_argument("--watch",        type=str,  help="指定套餐名，逗号分隔")
    parser.add_argument("--test",         action="store_true", help="发送 Bark 测试消息后退出")
    args = parser.parse_args()

    cfg = load_config()

    # 没有传任何参数 → 进交互菜单
    no_args = not any([args.bark_key, args.bark_server, args.interval,
                       args.notify_mode, args.watch, args.test])
    if no_args:
        cfg = interactive_menu(cfg)
        monitor(cfg)
        return

    # 有参数 → 直接应用参数，跳过菜单
    if args.bark_key:    cfg["bark_key"]    = args.bark_key
    if args.bark_server: cfg["bark_server"] = args.bark_server.rstrip("/")
    if args.interval:    cfg["interval"]    = max(5, args.interval)
    if args.notify_mode: cfg["notify_mode"] = args.notify_mode
    if args.watch:
        cfg["watch_names"] = [x.strip() for x in args.watch.split(",") if x.strip()]

    save_config(cfg)

    if args.test:
        ok = send_bark(cfg, "FACHOST 监控测试", "测试消息：Bark 配置正常，监控脚本已就绪。", URL)
        log(f"测试推送: {'成功 ✅' if ok else '失败 ❌'}")
        return

    monitor(cfg)


if __name__ == "__main__":
    main()
