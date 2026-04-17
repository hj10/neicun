#!/usr/bin/env python3
"""内存释放专家（演示版，支持后台与保活模式）。"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import signal
import subprocess
import sys
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox, ttk

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

APP_NAME = "内存释放专家"
CONFIG_DIR = Path.home() / ".memory_manager"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "background.log"


@dataclass
class AppConfig:
    auto_start: bool = False
    timed_cleanup: bool = True
    interval_minutes: int = 10


class BackgroundAgent:
    """无界面后台模式：按间隔执行内存整理。"""

    def __init__(self, once: bool = False) -> None:
        self.once = once
        self.running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_: object) -> None:
        self.running = False

    def run(self) -> int:
        self._log("后台模式已启动")
        while self.running:
            config = load_config()
            interval = max(1, min(60, config.interval_minutes))

            if config.timed_cleanup:
                result = cleanup_memory()
                self._log(f"执行内存整理：{result}")
            elif self.once:
                self._log("定时释放已关闭，单次后台执行结束")

            if self.once:
                break

            for _ in range(interval * 60):
                if not self.running:
                    break
                time.sleep(1)

        self._log("后台模式已退出")
        return 0

    def _log(self, text: str) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {text}\n"
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(line)
        print(text)


class KeepAliveSupervisor:
    """保活模式：监控后台子进程，异常退出后自动重启。"""

    def __init__(self) -> None:
        self.running = True
        self.child: subprocess.Popen[str] | None = None
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_: object) -> None:
        self.running = False
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()

    def run(self) -> int:
        print("保活模式已启动（监控后台进程）。")
        restart_count = 0
        while self.running:
            cmd = [sys.executable, __file__, "--background"]
            self.child = subprocess.Popen(cmd, text=True)
            return_code = self.child.wait()

            if not self.running:
                break

            # 保持保活语义：无论是否正常退出，都继续拉起。
            restart_count += 1
            print(f"后台进程退出（code={return_code}），第 {restart_count} 次重启中...")
            time.sleep(2)

        print("保活模式已退出。")
        return 0


class MemoryManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("500x520")
        self.resizable(False, False)
        self.configure(bg="#eef3f9")

        self.config_data = load_config()
        self._schedule_job: str | None = None

        self.auto_start_var = tk.BooleanVar(value=self.config_data.auto_start)
        self.timed_cleanup_var = tk.BooleanVar(value=self.config_data.timed_cleanup)
        self.interval_var = tk.StringVar(value=str(self.config_data.interval_minutes))

        self.total_mem_var = tk.StringVar(value="物理内存总量：--")
        self.used_mem_var = tk.StringVar(value="已用物理内存：--")
        self.percent_var = tk.StringVar(value="可用量百分比：--")
        self.status_var = tk.StringVar(value="准备就绪")

        self._build_style()
        self._build_ui()
        self._refresh_memory_stats()
        self._sync_schedule()
        self.protocol("WM_DELETE_WINDOW", self._on_quit)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background="#eef3f9", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 6), font=("Microsoft YaHei", 10))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")])
        style.configure("Card.TLabelframe", background="#ffffff")
        style.configure("Card.TLabelframe.Label", background="#ffffff", foreground="#1f4f8b")

    def _build_ui(self) -> None:
        self._build_header()

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=14, pady=(8, 12))

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        basic_tab = ttk.Frame(notebook)
        optimize_tab = ttk.Frame(notebook)
        about_tab = ttk.Frame(notebook)

        notebook.add(basic_tab, text="基本设置")
        notebook.add(optimize_tab, text="优化规则")
        notebook.add(about_tab, text="关于")

        self._build_basic_tab(basic_tab)
        self._build_optimize_tab(optimize_tab)
        self._build_about_tab(about_tab)

    def _build_header(self) -> None:
        banner = tk.Frame(self, bg="#2f5d9b", height=95)
        banner.pack(fill="x")
        banner.pack_propagate(False)

        tk.Label(
            banner,
            text="内存释放专家",
            fg="#ffdd44",
            bg="#2f5d9b",
            font=("Microsoft YaHei", 20, "bold"),
        ).pack(anchor="w", padx=18, pady=(14, 2))

        tk.Label(
            banner,
            text="支持桌面模式 / 后台模式 / 保活模式",
            fg="#e7f1ff",
            bg="#2f5d9b",
            font=("Microsoft YaHei", 10),
        ).pack(anchor="w", padx=20)

    def _build_basic_tab(self, parent: ttk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="设置", style="Card.TLabelframe")
        card.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Checkbutton(card, text="随开机自动启动", variable=self.auto_start_var).pack(
            anchor="w", padx=14, pady=(8, 6)
        )
        ttk.Checkbutton(card, text="定时自动释放内存", variable=self.timed_cleanup_var).pack(
            anchor="w", padx=14, pady=2
        )

        interval_row = ttk.Frame(card)
        interval_row.pack(fill="x", padx=14, pady=8)
        ttk.Label(interval_row, text="每隔").pack(side="left")
        ttk.Entry(interval_row, textvariable=self.interval_var, width=8).pack(side="left", padx=5)
        ttk.Label(interval_row, text="分钟释放一次内存（1~60）").pack(side="left")

        ttk.Label(card, text="（建议设置为 10~20 分钟）", foreground="#666666").pack(
            anchor="w", padx=14, pady=(0, 8)
        )

        ttk.Separator(card).pack(fill="x", padx=14, pady=8)
        ttk.Label(card, textvariable=self.total_mem_var).pack(anchor="w", padx=14, pady=2)
        ttk.Label(card, textvariable=self.used_mem_var).pack(anchor="w", padx=14, pady=2)
        ttk.Label(card, textvariable=self.percent_var).pack(anchor="w", padx=14, pady=2)
        ttk.Separator(card).pack(fill="x", padx=14, pady=8)

        ttk.Label(card, text="让内存为我所用！", foreground="#1f4f8b").pack(anchor="e", padx=14, pady=(0, 8))

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(btn_row, text="保存设置", command=self._save_settings).pack(side="left")
        ttk.Button(btn_row, text="立即释放", command=self._manual_cleanup).pack(side="right", padx=(6, 0))
        ttk.Button(btn_row, text="退出程序", command=self._on_quit).pack(side="right")

        ttk.Label(parent, textvariable=self.status_var, foreground="#1f4f8b").pack(
            fill="x", padx=14, pady=(0, 8)
        )

    def _build_optimize_tab(self, parent: ttk.Frame) -> None:
        tips = (
            "运行模式说明：\n"
            "1) 桌面模式: python memory_manager.py\n"
            "2) 后台模式: python memory_manager.py --background\n"
            "3) 保活模式: python memory_manager.py --keepalive\n\n"
            "优化建议：\n"
            "- 定时释放建议 10~20 分钟一次。\n"
            "- 长期高占用建议关闭大程序或重启。"
        )
        ttk.Label(parent, text=tips, justify="left").pack(anchor="nw", padx=16, pady=16)

    def _build_about_tab(self, parent: ttk.Frame) -> None:
        about = (
            f"{APP_NAME}\n"
            "版本: 1.2.0\n"
            "用途: 模拟经典内存工具界面，支持后台运行与保活。\n\n"
            "说明：现代系统会自动管理内存，本工具主要触发\n"
            "垃圾回收并展示实时内存状态。"
        )
        ttk.Label(parent, text=about, justify="left").pack(anchor="nw", padx=16, pady=16)

    def _save_settings(self) -> None:
        interval = self._parse_interval(show_error=True)
        if interval is None:
            return

        self.config_data = AppConfig(
            auto_start=self.auto_start_var.get(),
            timed_cleanup=self.timed_cleanup_var.get(),
            interval_minutes=interval,
        )

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as file:
            json.dump(asdict(self.config_data), file, ensure_ascii=False, indent=2)

        auto_start_text = self._configure_auto_start(self.config_data.auto_start)
        self._sync_schedule()
        self.status_var.set(f"设置已保存。{auto_start_text}")

    def _parse_interval(self, *, show_error: bool) -> int | None:
        try:
            interval = int(self.interval_var.get().strip())
        except ValueError:
            if show_error:
                messagebox.showerror("输入错误", "请输入 1~60 之间的整数分钟。")
            return None
        if not 1 <= interval <= 60:
            if show_error:
                messagebox.showerror("输入错误", "间隔分钟必须在 1~60 之间。")
            return None
        return interval

    def _manual_cleanup(self) -> None:
        released_text = cleanup_memory()
        self._refresh_memory_stats()
        self.status_var.set(f"已执行释放：{released_text}")

    def _refresh_memory_stats(self) -> None:
        if psutil is None:
            self.total_mem_var.set("物理内存总量：未安装 psutil")
            self.used_mem_var.set("已用物理内存：请执行 pip install psutil")
            self.percent_var.set("可用量百分比：--")
            return

        mem = psutil.virtual_memory()
        total_kb = mem.total / 1024
        used_kb = (mem.total - mem.available) / 1024
        avail_percent = mem.available / mem.total * 100

        self.total_mem_var.set(f"物理内存总量：{total_kb:,.0f} KB")
        self.used_mem_var.set(f"已用物理内存：{used_kb:,.0f} KB")
        self.percent_var.set(f"可用量百分比：{avail_percent:,.1f} %")

    def _sync_schedule(self) -> None:
        if self._schedule_job is not None:
            self.after_cancel(self._schedule_job)
            self._schedule_job = None

        if not self.timed_cleanup_var.get():
            return

        interval = self._parse_interval(show_error=False)
        if interval is None:
            interval = 10
            self.interval_var.set("10")

        self._schedule_job = self.after(interval * 60 * 1000, self._timed_cleanup_callback)

    def _timed_cleanup_callback(self) -> None:
        self._manual_cleanup()
        self._sync_schedule()

    def _configure_auto_start(self, enabled: bool) -> str:
        if enabled:
            return "已勾选开机自启（演示版未改写系统启动项）。"
        return ""

    def _on_quit(self) -> None:
        if self._schedule_job is not None:
            self.after_cancel(self._schedule_job)
            self._schedule_job = None
        self.destroy()


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        interval = int(raw.get("interval_minutes", 10))
        interval = max(1, min(60, interval))
        return AppConfig(
            auto_start=bool(raw.get("auto_start", False)),
            timed_cleanup=bool(raw.get("timed_cleanup", True)),
            interval_minutes=interval,
        )
    except Exception:
        return AppConfig()


def cleanup_memory() -> str:
    before = available_memory_kb()
    gc.collect()

    if platform.system() == "Windows":
        empty_working_set_windows()

    after = available_memory_kb()
    if before is None or after is None:
        return "完成"

    diff = after - before
    if diff >= 0:
        return f"可用内存提升 {diff:,.0f} KB"
    return f"已触发整理（系统波动 {abs(diff):,.0f} KB）"


def empty_working_set_windows() -> None:
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        process = kernel32.GetCurrentProcess()
        psapi.EmptyWorkingSet(process)
    except Exception:
        pass


def available_memory_kb() -> float | None:
    if psutil is None:
        return None
    return psutil.virtual_memory().available / 1024


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--background", action="store_true", help="后台模式，无界面运行")
    parser.add_argument("--keepalive", action="store_true", help="保活模式，监控后台进程")
    parser.add_argument("--once", action="store_true", help="仅执行一次后台释放（测试用）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.keepalive:
        return KeepAliveSupervisor().run()

    if args.background:
        return BackgroundAgent(once=args.once).run()

    app = MemoryManagerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
