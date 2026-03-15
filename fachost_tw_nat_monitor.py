#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FACHOST TW-NAT 专用库存监控脚本
监控: https://fachost.cloud/products/tw-nat
有库存立即发送 Bark 提醒
作者: github.com/ctsunny
"""

import json
import os
import re
import subprocess
import sys
import termios
import time
import tty
from datetime import datetime

import requests

URL         = "https://fachost.cloud/products/tw-nat"
CONFIG_FILE = os.path.expanduser("~/.fachost_tw_nat_monitor.json")
STATUS_FILE = os.path.expanduser("~/.fachost_tw_nat_status.json")
SCREEN_NAME = "fachost-monitor"
HOURLY_INTERVAL = 3600   # 小时状态汇报间隔秒

KNOWN_PLANS = ["Hinet-Nat-1", "Seednet-Nat-1", "Hinet-Nat-3", "Hinet-Nat-4", "Seednet-Nat-2"]

DEFAULT_CONFIG = {
    "bark_key":    "",
    "bark_server": "https://api.day.app",
    "interval":    20,
    "notify_mode": "bark",
    "watch_names": [],
    "timeout":     15,
}


class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"


def now():
    return datetime.now().strftime("%H:%M:%S")


def log(msg, color=C.RESET):
    print(f"{color}[{now()}] {msg}{C.RESET}", flush=True)

def log_ok(msg):   log(msg, C.GREEN)
def log_warn(msg): log(msg, C.YELLOW)
def log_err(msg):  log(msg, C.RED)
def log_info(msg): log(msg, C.CYAN)


# ────────────────────────── 配置 ─────────────────────────

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    log_info(f"配置已保存: {CONFIG_FILE}")


def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_status():
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ────────────────────────── screen 管理 ─────────────────────────

def screen_exists():
    try:
        out = subprocess.check_output(["screen", "-ls"], stderr=subprocess.DEVNULL).decode()
        return SCREEN_NAME in out
    except Exception:
        return False


def screen_available():
    return subprocess.call(["which", "screen"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def start_in_screen():
    script = os.path.abspath(__file__)
    subprocess.Popen(
        ["screen", "-dmS", SCREEN_NAME,
         "python3", script, "--run-monitor"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    return screen_exists()


def stop_screen():
    try:
        subprocess.call(
            ["screen", "-S", SCREEN_NAME, "-X", "quit"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(0.5)
        return True
    except Exception:
        return False


def attach_screen():
    os.system(f"screen -r {SCREEN_NAME}")


# ────────────────────────── 空格多选 ─────────────────────────

def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def multi_select(title, options, selected):
    sel = set(selected)
    cur = 0
    ENTER = ("\r", "\n")

    def render():
        lines = len(options) + 3
        sys.stdout.write(f"\033[{lines}A\033[J")
        print(f"  {C.BOLD}{title}{C.RESET}")
        print(f"  {C.DIM}[↑↓] 移动  [空格] 勾选/取消  [回车] 确定  [0] 监控全部{C.RESET}")
        for i, opt in enumerate(options):
            check = "[x]" if opt in sel else "[ ]"
            arrow = "> " if i == cur else "  "
            color = C.GREEN if opt in sel else C.RESET
            print(f"  {arrow}{color}{check} {opt}{C.RESET}")
        sys.stdout.flush()

    print(f"  {C.BOLD}{title}{C.RESET}")
    print(f"  {C.DIM}[↑↓] 移动  [空格] 勾选/取消  [回车] 确定  [0] 监控全部{C.RESET}")
    for i, opt in enumerate(options):
        check = "[x]" if opt in sel else "[ ]"
        arrow = "> " if i == cur else "  "
        color = C.GREEN if opt in sel else C.RESET
        print(f"  {arrow}{color}{check} {opt}{C.RESET}")

    while True:
        ch = getch()
        if ch == "\x1b":
            ch2 = getch()
            if ch2 == "[":
                ch3 = getch()
                if ch3 == "A" and cur > 0:
                    cur -= 1
                elif ch3 == "B" and cur < len(options) - 1:
                    cur += 1
        elif ch == " ":
            opt = options[cur]
            if opt in sel: sel.remove(opt)
            else: sel.add(opt)
        elif ch == "0":
            sel = set()
        elif ch in ENTER:
            break
        elif ch in ("q", "Q", "\x03"):
            break
        render()
    return sel


# ────────────────────────── Bark ─────────────────────────

def send_bark(cfg, title, body, jump_url="", force_normal=False):
    """
    force_normal=True 时强制使用普通推送（不穿透静音），用于状态汇报。
    """
    if not cfg.get("bark_key"):
        log_warn("未设置 Bark 密钥，跳过推送")
        return False
    payload = {
        "title": title, "body": body,
        "group": "fachost-tw-nat", "sound": "minuet",
    }
    if not force_normal:
        mode = cfg.get("notify_mode", "bark")
        if mode == "bark+sound":        payload["level"] = "active"
        elif mode == "bark+critical":   payload["level"] = "critical"; payload["volume"] = "10"
    if jump_url:
        payload["url"] = jump_url
    api = f"{cfg['bark_server'].rstrip('/')}/{cfg['bark_key']}"
    try:
        r = requests.post(api, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log_err(f"Bark 请求失败: {e}")
        return False


# ────────────────────────── 页面解析 ─────────────────────────

def fetch_html(cfg):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    r = requests.get(URL, headers=headers, timeout=cfg.get("timeout", 15))
    r.raise_for_status()
    return r.text


def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_cards(html):
    cards = []
    pattern = re.compile(
        r'<div class="flex flex-col bg-background-secondary border border-neutral rounded-xl p-6 gap-4 relative'
        r'.*?<h2[^>]*>(.*?)</h2>(.*?)<div class="mt-auto">(.*?)</div>\s*</div>',
        re.S,
    )
    for m in pattern.finditer(html):
        name = clean_text(m.group(1))
        full = m.group(2) + "\n" + m.group(3)
        tail = m.group(3)
        disabled = any(x in tail for x in [
            "cursor-not-allowed", "pointer-events-none",
            "bg-neutral-200", "text-neutral-500"])
        sold_out = any(x in full for x in [
            "已售罄", "sold out", "bg-red-100", "text-red-600"])
        buy_now  = any(x in full for x in [
            "立即购买", "buy now", "order now",
            "bg-green-100", "text-green-600"])
        in_stock = buy_now and not disabled
        if not buy_now and sold_out:
            in_stock = False
        if name:
            cards.append({"name": name, "in_stock": in_stock})
    return cards


def filter_cards(cards, watch_names):
    if not watch_names:
        return cards
    wanted = {x.strip().lower() for x in watch_names}
    return [c for c in cards if c["name"].strip().lower() in wanted]


# ────────────────────────── 监控循环 ─────────────────────────

def run_monitor():
    cfg = load_config()
    watch_names = cfg.get("watch_names", [])
    alerted     = set()
    round_no    = 0
    last_hourly = time.time()   # 上次小时汇报时间

    watch_str = ", ".join(watch_names) if watch_names else "全部"

    print(C.BOLD + "=" * 54 + C.RESET, flush=True)
    print(C.BOLD + "  ▶ FACHOST TW-NAT 监控已在后台运行" + C.RESET, flush=True)
    print(C.BOLD + f"  频率 : {cfg['interval']} 秒/次" + C.RESET, flush=True)
    print(C.BOLD + f"  方式 : {cfg.get('notify_mode','bark')}" + C.RESET, flush=True)
    print(C.BOLD + f"  套餐 : {watch_str}" + C.RESET, flush=True)
    print(C.BOLD + "=" * 54 + C.RESET, flush=True)

    # ── 启动通知 ──
    send_bark(
        cfg,
        title="🟢 FACHOST 监控已启动",
        body=f"监控套餐: {watch_str}\n频率: {cfg['interval']}秒/次\n方式: {cfg.get('notify_mode','bark')}",
        force_normal=True,
    )
    log_ok("启动通知已发送")

    def send_hourly_report(plans_status):
        ts  = datetime.now().strftime("%H:%M")
        if plans_status:
            lines = []
            for name, st in plans_status.items():
                icon = "✅" if st == "有货" else "❌"
                lines.append(f"{icon} {name}: {st}")
            body = "\n".join(lines)
        else:
            body = "暂无套餐数据"
        send_bark(
            cfg,
            title=f"📊 FACHOST 小时状态汇报 {ts}",
            body=body,
            force_normal=True,
        )
        log_info(f"小时状态汇报已发送 ({ts})")

    while True:
        round_no += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_info(f"第 {round_no} 轮检测...")
        status = {"last_check": ts, "round": round_no, "plans": {}}

        try:
            html  = fetch_html(cfg)
            cards = parse_cards(html)
            cards = filter_cards(cards, watch_names)
            if not cards:
                log_warn("未解析到套餐，页面结构可能有变")
            else:
                for c in cards:
                    st = "有货" if c["in_stock"] else "售罄"
                    status["plans"][c["name"]] = st
                    if c["in_stock"]:
                        log_ok(f"✅ 有货: {c['name']}")
                        if c["name"] not in alerted:
                            alerted.add(c["name"])
                            ok = send_bark(
                                cfg,
                                title=f"🛒 FACHOST 有库存: {c['name']}",
                                body=f"{c['name']} 已可购买！立即打开页面。",
                                jump_url=URL,
                            )
                            log_ok(f"Bark: {'成功✅' if ok else '失败❌'}")
                    else:
                        log_warn(f"❌ 售罄: {c['name']}")
                        alerted.discard(c["name"])
        except KeyboardInterrupt:
            # ── 停止通知 ──
            send_bark(
                cfg,
                title="🔴 FACHOST 监控已停止",
                body=f"已运行 {round_no} 轮，时间: {datetime.now().strftime('%H:%M:%S')}",
                force_normal=True,
            )
            log_info("监控已停止")
            sys.exit(0)
        except Exception as e:
            log_err(f"异常: {e}")
            status["error"] = str(e)

        save_status(status)

        # ── 小时汇报 ──
        now_ts = time.time()
        if now_ts - last_hourly >= HOURLY_INTERVAL:
            send_hourly_report(status.get("plans", {}))
            last_hourly = now_ts

        log_info(f"{cfg['interval']} 秒后下一轮...")
        print(flush=True)
        try:
            time.sleep(max(5, int(cfg["interval"])))
        except KeyboardInterrupt:
            send_bark(
                cfg,
                title="🔴 FACHOST 监控已停止",
                body=f"已运行 {round_no} 轮，时间: {datetime.now().strftime('%H:%M:%S')}",
                force_normal=True,
            )
            log_info("监控已停止")
            sys.exit(0)


# ────────────────────────── 主菜单 ─────────────────────────

def main_menu():
    cfg = load_config()

    while True:
        running = screen_exists()
        status  = load_status()

        print()
        print(C.BOLD + "=" * 54 + C.RESET)
        print(C.BOLD + "   🛒  FACHOST TW-NAT 库存监控" + C.RESET)
        print(C.BOLD + "=" * 54 + C.RESET)

        state_str = f"{C.GREEN}运行中 ●{C.RESET}" if running else f"{C.RED}已停止 ○{C.RESET}"
        print(f"  状态  : {state_str}")
        if status:
            print(f"  最近检测: {status.get('last_check','--')}  第 {status.get('round','?')} 轮")
            for name, st in status.get("plans", {}).items():
                icon = "✅" if st == "有货" else "❌"
                print(f"    {icon} {name}: {st}")
            if "error" in status:
                print(f"  {C.RED}最近异常: {status['error']}{C.RESET}")

        key = cfg.get('bark_key', '')
        key_str = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else ("已设置" if key else "未设置")
        watch = ', '.join(cfg.get('watch_names', [])) or '全部'
        print(C.DIM + f"  Bark   : {key_str}" + C.RESET)
        print(C.DIM + f"  频率   : {cfg.get('interval',20)}秒  方式: {cfg.get('notify_mode','bark')}  套餐: {watch}" + C.RESET)
        print(C.BOLD + "=" * 54 + C.RESET)

        if running:
            print("  1. 查看实时日志 (attach screen)")
            print("  2. 停止监控")
            print("  3. 修改配置并重启")
        else:
            print("  1. 启动监控 (screen 后台)")
            print("  2. 修改配置")
        print("  0. 退出")
        print()

        choice = input("  请选择: ").strip()

        if running:
            if choice == "1":
                print(f"  {C.CYAN}进入实时日志，按 Ctrl+A D 挂到后台{C.RESET}")
                time.sleep(1)
                attach_screen()
            elif choice == "2":
                stop_screen()
                # 由于 screen 被 kill，无法触发 KeyboardInterrupt，这里由菜单失送停止通知
                last_st = load_status()
                send_bark(
                    cfg,
                    title="🔴 FACHOST 监控已停止",
                    body=f"已运行 {last_st.get('round','?')} 轮，时间: {datetime.now().strftime('%H:%M:%S')}",
                    force_normal=True,
                )
                log_ok("监控已停止")
            elif choice == "3":
                stop_screen()
                cfg = config_wizard(cfg)
                if start_in_screen():
                    log_ok(f"监控已在后台重新启动 (screen: {SCREEN_NAME})")
                else:
                    log_err("启动失败，请检查 screen 是否已安装")
            elif choice == "0":
                break
        else:
            if choice == "1":
                cfg = config_wizard(cfg)
                if start_in_screen():
                    log_ok(f"监控已在后台启动 (screen: {SCREEN_NAME})")
                    log_info("可关闭 SSH，监控持续运行")
                else:
                    log_err("启动失败")
            elif choice == "2":
                cfg = config_wizard(cfg)
            elif choice == "0":
                break


def config_wizard(cfg):
    print()
    print(C.BOLD + "  —— 配置向导 ——" + C.RESET)
    print()

    cur_key = cfg.get("bark_key", "")
    hint = f"[{cur_key[:6]}...{cur_key[-4:]}]" if len(cur_key) > 10 else "[未设置]"
    v = input(f"  Bark 密钥 {hint} (回车保留): ").strip()
    if v: cfg["bark_key"] = v

    v = input(f"  检测频率秒 [{cfg.get('interval',20)}] (回车保留): ").strip()
    if v.isdigit(): cfg["interval"] = max(5, int(v))

    print()
    mode_map = {"1": "bark", "2": "bark+sound", "3": "bark+critical"}
    cur_num  = {v2: k for k, v2 in mode_map.items()}.get(cfg.get("notify_mode","bark"), "1")
    print("  提醒方式:")
    print("    1. bark          普通")
    print("    2. bark+sound    铃声")
    print("    3. bark+critical 穿透静音 ★抢购推荐")
    v = input(f"  选择 1/2/3 [当前:{cur_num}] (回车保留): ").strip()
    if v in mode_map: cfg["notify_mode"] = mode_map[v]

    print()
    current_sel = set(cfg.get("watch_names", []))
    try:
        html  = fetch_html({**cfg, "timeout": 10})
        cards = parse_cards(html)
        options = [c["name"] for c in cards] if cards else KNOWN_PLANS
    except Exception:
        options = KNOWN_PLANS

    print()
    new_sel = multi_select("选择监控套餐 (空格勾选, 0=全部)", options, current_sel)
    cfg["watch_names"] = list(new_sel)
    print()

    do_test = input("  发送 Bark 测试消息? (y/N): ").strip().lower()
    if do_test == "y":
        ok = send_bark(cfg, "FACHOST 测试", "Bark 正常，监控即将启动。", URL, force_normal=True)
        log(f"测试: {'成功✅' if ok else '失败❌ 请检查 Bark Key 是否正确'}")

    save_config(cfg)
    return cfg


# ────────────────────────── 入口 ─────────────────────────

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--run-monitor":
        run_monitor()
    else:
        if not screen_available():
            print(f"{C.YELLOW}[提示] 建议安装 screen: apt install screen{C.RESET}")
        main_menu()
