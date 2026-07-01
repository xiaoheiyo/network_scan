import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import subprocess
import threading
import time
import re
import os
import sys
import winsound
import json
import statistics
import socket
import struct
import gzip
import shutil
from datetime import datetime, timedelta
from datetime import time as dt_time
from collections import deque
import queue as queue_module

# 基础路径：exe所在目录（打包后）或脚本所在目录（源码运行）
def _get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    try:
        if __compiled__:
            return os.path.dirname(os.path.abspath(sys.argv[0]))
    except NameError:
        pass
    return os.path.dirname(os.path.abspath(__file__))
BASE_DIR = _get_base_dir()

STATUS_KEYS = ['normal', 'timeout', 'unreachable', 'ttl_expired', 'host_not_found', 'packet_loss_jitter', 'first_packet_timeout']
STATUS_NAMES = {
    'normal': '正常连通', 'timeout': '请求超时', 'unreachable': '目标不可达',
    'ttl_expired': 'TTL传输中过期', 'host_not_found': '找不到主机',
    'packet_loss_jitter': '部分丢包与延迟抖动', 'first_packet_timeout': '仅首包超时'
}
STATUS_DEFAULTS = {
    'normal': '#00CC00', 'timeout': '#CC0000', 'unreachable': '#990000', 'ttl_expired': '#CCCC00',
    'host_not_found': '#990099', 'packet_loss_jitter': '#CC6600', 'first_packet_timeout': '#FF9900'
}

SOUND_OPTIONS = ['无', '错误音', '警告音', '提示音', '蜂鸣(低)', '蜂鸣(中)', '蜂鸣(高)']
SOUND_VALUES = ['none', 'hand', 'exclamation', 'asterisk', 'beep_low', 'beep_mid', 'beep_high']
ALARM_DEFAULT_SOUNDS = {
    'normal': 'none', 'timeout': 'hand', 'unreachable': 'hand', 'ttl_expired': 'exclamation',
    'host_not_found': 'exclamation', 'packet_loss_jitter': 'asterisk', 'first_packet_timeout': 'asterisk'
}


class SettingsDialog:
    def __init__(self, parent, app):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.update_idletasks()

        w, h = 520, 850
        px = parent.winfo_x() + (parent.winfo_width() - w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.dialog.geometry(f"{w}x{h}+{px}+{py}")

        self.app = app
        self.buttons = {}
        self.labels = {}

        main = ttk.Frame(self.dialog, padding="15")
        main.pack(fill=tk.BOTH, expand=True)

        # === 配置留存 ===
        box1 = ttk.LabelFrame(main, text="配置留存", padding="8")
        box1.pack(fill=tk.X, pady=(0, 8))
        self.persist_var = tk.BooleanVar(value=app.config.get('persist_config', True))
        ttk.Checkbutton(box1, text="保留配置设置到文件（IP列表、颜色等）", variable=self.persist_var).pack(anchor=tk.W)

        # === 记录保存 ===
        box2 = ttk.LabelFrame(main, text="记录保存", padding="8")
        box2.pack(fill=tk.X, pady=(0, 8))
        self.save_var = tk.BooleanVar(value=app.config['save_records'])
        ttk.Checkbutton(box2, text="保存Ping记录到文件（log目录下，每个IP独立文件）", variable=self.save_var).pack(anchor=tk.W, pady=(0, 5))
        size_row = ttk.Frame(box2)
        size_row.pack(fill=tk.X)
        ttk.Label(size_row, text="单个日志最大(KB):").pack(side=tk.LEFT)
        self.logsize_spin = ttk.Spinbox(size_row, from_=10, to=102400, width=10)
        self.logsize_spin.set(app.config.get('max_log_size', 1024))
        self.logsize_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(size_row, text="(超过自动压缩归档)").pack(side=tk.LEFT, padx=5)

        # === 高级设置 ===
        box_adv = ttk.LabelFrame(main, text="高级设置", padding="8")
        box_adv.pack(fill=tk.X, pady=(0, 8))
        self.auto_start_var = tk.BooleanVar(value=app.config.get('auto_start', False))
        ttk.Checkbutton(box_adv, text="定时启动监控", variable=self.auto_start_var,
                        command=self.toggle_auto_start).pack(anchor=tk.W)
        time_row = ttk.Frame(box_adv)
        time_row.pack(fill=tk.X, padx=(20, 0), pady=(3, 5))
        ttk.Label(time_row, text="启动时间(时:分):").pack(side=tk.LEFT)
        self.auto_hour = ttk.Spinbox(time_row, from_=0, to=23, width=4, format='%02.0f')
        self.auto_hour.set(app.config.get('auto_start_hour', 8))
        self.auto_hour.pack(side=tk.LEFT, padx=2)
        ttk.Label(time_row, text=":").pack(side=tk.LEFT)
        self.auto_min = ttk.Spinbox(time_row, from_=0, to=59, width=4, format='%02.0f')
        self.auto_min.set(app.config.get('auto_start_min', 0))
        self.auto_min.pack(side=tk.LEFT, padx=2)
        self.auto_stop_var = tk.BooleanVar(value=app.config.get('auto_stop', False))
        ttk.Checkbutton(box_adv, text="定时关闭监控", variable=self.auto_stop_var,
                        command=self.toggle_auto_start).pack(anchor=tk.W)
        stop_row = ttk.Frame(box_adv)
        stop_row.pack(fill=tk.X, padx=(20, 0), pady=(3, 5))
        ttk.Label(stop_row, text="关闭时间(时:分):").pack(side=tk.LEFT)
        self.auto_stop_hour = ttk.Spinbox(stop_row, from_=0, to=23, width=4, format='%02.0f')
        self.auto_stop_hour.set(app.config.get('auto_stop_hour', 18))
        self.auto_stop_hour.pack(side=tk.LEFT, padx=2)
        ttk.Label(stop_row, text=":").pack(side=tk.LEFT)
        self.auto_stop_min = ttk.Spinbox(stop_row, from_=0, to=59, width=4, format='%02.0f')
        self.auto_stop_min.set(app.config.get('auto_stop_min', 0))
        self.auto_stop_min.pack(side=tk.LEFT, padx=2)
        self.crash_var = tk.BooleanVar(value=app.config.get('crash_restart', False))
        ttk.Checkbutton(box_adv, text="闪退自动重启", variable=self.crash_var).pack(anchor=tk.W)
        self.alarm_var = tk.BooleanVar(value=app.config.get('alarm_enabled', True))
        ttk.Checkbutton(box_adv, text="异常告警声", variable=self.alarm_var).pack(anchor=tk.W)
        self.toggle_auto_start()

        # === 状态颜色 + 告警声 ===
        box3 = ttk.LabelFrame(main, text="Ping状态 - 颜色自定义  告警声设置(持续正常→异常时播放)", padding="8")
        box3.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        canvas = tk.Canvas(box3, highlightthickness=0)
        scrollbar = ttk.Scrollbar(box3, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor=tk.NW)

        self.alarm_vars = {}
        for i, key in enumerate(STATUS_KEYS):
            current = app.config.get(f'{key}_color', STATUS_DEFAULTS[key])
            row = ttk.Frame(inner)
            row.pack(fill=tk.X, pady=3)

            ttk.Label(row, text=STATUS_NAMES[key], width=22, anchor=tk.W).pack(side=tk.LEFT, padx=5)
            btn = tk.Button(row, bg=current, width=3, height=1, relief=tk.RIDGE, bd=2,
                           command=lambda k=key: self.pick_color(k))
            btn.pack(side=tk.LEFT, padx=3)
            label = ttk.Label(row, text=current, font=('Consolas', 9), width=10)
            label.pack(side=tk.LEFT, padx=3)
            preview = tk.Canvas(row, width=20, height=16, bg=current, highlightthickness=1, highlightbackground='#ccc')
            preview.pack(side=tk.LEFT, padx=3)
            self.buttons[key] = btn
            self.labels[key] = (label, preview)

            sound_val = app.config.get(f'alarm_{key}', ALARM_DEFAULT_SOUNDS.get(key, 'hand'))
            sound_idx = SOUND_VALUES.index(sound_val) if sound_val in SOUND_VALUES else 0
            var = tk.StringVar(value=SOUND_OPTIONS[sound_idx])
            combo = ttk.Combobox(row, textvariable=var, values=SOUND_OPTIONS, state='readonly', width=10)
            combo.pack(side=tk.LEFT, padx=(8, 3))
            play_btn = ttk.Button(row, text='▶', width=3, command=lambda k=key: self.preview_sound(k))
            play_btn.pack(side=tk.LEFT)
            self.alarm_vars[key] = var

        inner.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"), width=440, height=260)

        # === 底部按钮 ===
        btn_bar = ttk.Frame(main)
        btn_bar.pack(fill=tk.X)
        ttk.Button(btn_bar, text="保存设置", command=self.save, width=12).pack(side=tk.RIGHT, padx=3)
        ttk.Button(btn_bar, text="取消", command=self.dialog.destroy, width=8).pack(side=tk.RIGHT, padx=3)

    def pick_color(self, key):
        color = colorchooser.askcolor(title=f"选择{STATUS_NAMES[key]}颜色", initialcolor=self.buttons[key].cget('bg'))
        if color[1]:
            self.buttons[key].config(bg=color[1])
            label, preview = self.labels[key]
            label.config(text=color[1])
            preview.config(bg=color[1])

    def preview_sound(self, key):
        display = self.alarm_vars[key].get()
        idx = SOUND_OPTIONS.index(display) if display in SOUND_OPTIONS else 0
        sound = SOUND_VALUES[idx]
        try:
            if sound == 'hand':
                winsound.MessageBeep(winsound.MB_ICONHAND)
            elif sound == 'exclamation':
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sound == 'asterisk':
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sound == 'beep_low':
                winsound.Beep(400, 300)
            elif sound == 'beep_mid':
                winsound.Beep(800, 300)
            elif sound == 'beep_high':
                winsound.Beep(1600, 300)
        except Exception:
            pass

    def choose_path(self):
        filename = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("日志文件","*.log"),("文本文件","*.txt"),("所有文件","*.*")])
        if filename:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, filename)

    def toggle_auto_start(self):
        s1 = tk.NORMAL if self.auto_start_var.get() else tk.DISABLED
        self.auto_hour.config(state=s1)
        self.auto_min.config(state=s1)
        s2 = tk.NORMAL if self.auto_stop_var.get() else tk.DISABLED
        self.auto_stop_hour.config(state=s2)
        self.auto_stop_min.config(state=s2)

    def save(self):
        self.app.config['persist_config'] = self.persist_var.get()
        self.app.config['save_records'] = self.save_var.get()
        self.app.config['auto_start'] = self.auto_start_var.get()
        self.app.config['auto_start_hour'] = int(self.auto_hour.get())
        self.app.config['auto_start_min'] = int(self.auto_min.get())
        self.app.config['auto_stop'] = self.auto_stop_var.get()
        self.app.config['auto_stop_hour'] = int(self.auto_stop_hour.get())
        self.app.config['auto_stop_min'] = int(self.auto_stop_min.get())
        self.app.config['crash_restart'] = self.crash_var.get()
        self.app.config['alarm_enabled'] = self.alarm_var.get()
        for key in STATUS_KEYS:
            if key in self.alarm_vars:
                display = self.alarm_vars[key].get()
                idx = SOUND_OPTIONS.index(display) if display in SOUND_OPTIONS else 0
                self.app.config[f'alarm_{key}'] = SOUND_VALUES[idx]
        try:
            self.app.config['max_log_size'] = int(self.logsize_spin.get())
        except ValueError:
            pass
        for key in STATUS_KEYS:
            self.app.config[f'{key}_color'] = self.labels[key][0].cget('text')
        self.app.save_config()
        self.app.update_colors()
        if self.app.config.get('auto_start') or self.app.config.get('auto_stop'):
            self.app.start_auto_schedule()
        else:
            self.app.stop_auto_schedule()
        self.app.setup_crash_restart()
        self.app.show_toast('设置已保存')
        self.dialog.destroy()


class LongPingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("长Ping监控工具")
        self.root.resizable(True, True)
        self.pinging = False
        self.ping_threads = {}
        self.ip_data = {}
        self.ip_list = []
        self.max_history = 60
        self.ip_remarks = {}
        self.config = self.load_config()
        self.result_queue = queue_module.Queue()
        self._update_scheduled = False
        self._color_map = {}
        self._prev_status = {}
        self._alarm_until = {}
        self._disabled_ips = set(self.config.get('disabled_ips', []))

        self.create_widgets()
        self.update_colors()
        # 如果有保存的IP列表，自动导入
        if self.ip_list:
            self.import_label.config(text=f"已导入 {len(self.ip_list)} 条")
            self.stats_label.config(text=f"总计: {len(self.ip_list)}")
            self.init_display()
        self.setup_crash_restart()
        if self.config.get('auto_start') or self.config.get('auto_stop'):
            self.start_auto_schedule()
        self._update_time()

    def load_config(self):
        default = {'persist_config': True, 'save_records': True, 'max_log_size': 1024, 'saved_ips': [], 'ping_bytes': 32, 'ping_ttl': 128, 'ping_interval': 0, 'ping_timeout': 1, 'display_count': 60, 'auto_start': False, 'auto_start_hour': 8, 'auto_start_min': 0, 'auto_stop': False, 'auto_stop_hour': 18, 'auto_stop_min': 0, 'crash_restart': False, 'alarm_enabled': True}
        for key in STATUS_KEYS:
            default[f'{key}_color'] = STATUS_DEFAULTS[key]
            default[f'alarm_{key}'] = ALARM_DEFAULT_SOUNDS.get(key, 'none')
        try:
            if os.path.exists(os.path.join(BASE_DIR, 'ping_config.json')):
                with open(os.path.join(BASE_DIR, 'ping_config.json'), 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    merged = {**default, **cfg}
                    self.ip_list = merged.get('saved_ips', [])
                    self.ip_remarks = merged.get('ip_remarks', {})
                    return merged
        except Exception:
            pass
        return default

    def save_ip_list(self):
        self.config['saved_ips'] = self.ip_list
        self.config['ip_remarks'] = self.ip_remarks
        self.save_config()

    def save_config(self):
        if not self.config.get('persist_config', True):
            return
        try:
            with open(os.path.join(BASE_DIR, 'ping_config.json'), 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def write_record(self, ip, status, latency, ttl=None, byte_size=None):
        if not self.config.get('save_records', True):
            return
        try:
            log_dir = os.path.join(BASE_DIR, 'log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_path = os.path.join(log_dir, f'{ip}.log')
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cfg_ttl = self.config.get('ping_ttl', 128)
            cfg_bytes = self.config.get('ping_bytes', 32)
            line = f"[{ts}] {STATUS_NAMES.get(status, status)} {latency:.1f}ms TTL={cfg_ttl} {cfg_bytes}B\n"

            # 检查日志文件大小（KB）
            max_size = self.config.get('max_log_size', 1024)
            if os.path.exists(log_path):
                size_kb = os.path.getsize(log_path) / 1024
                if size_kb >= max_size:
                    # 压缩归档
                    archive_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_name = f'{ip}_{archive_ts}.log.gz'
                    archive_path = os.path.join(log_dir, archive_name)
                    with open(log_path, 'rb') as f_in:
                        with gzip.open(archive_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    # 清空原文件
                    open(log_path, 'w').close()

            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=4)
        style.configure('TLabel', padding=2)
        style.configure('TLabelframe', padding=5)
        style.configure('Green.TLabel', foreground='#00AA00')
        style.configure('Red.TLabel', foreground='#CC0000')

        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        # 参数栏
        param_frame = ttk.Frame(top_frame)
        param_frame.pack(fill=tk.X)
        for t, v, w in [("Ping间隔", self.config.get('ping_interval', 0), 6), ("超时(秒)", self.config.get('ping_timeout', 1), 6), ("显示格数", self.config.get('display_count', 60), 6)]:
            ttk.Label(param_frame, text=f"{t}:").pack(side=tk.LEFT, padx=(8, 1))
            if t == "Ping间隔":
                spin = ttk.Spinbox(param_frame, from_=0, to=60, width=w, command=self.apply_params)
            elif t == "显示格数":
                spin = ttk.Spinbox(param_frame, from_=1, to=200, width=w, command=self.apply_params)
            else:
                spin = ttk.Spinbox(param_frame, from_=1, to=60, width=w, command=self.apply_params)
            spin.bind('<KeyRelease>', lambda e: self.apply_params())
            spin.set(v)
            spin.pack(side=tk.LEFT, padx=(0, 5))
            if t == "Ping间隔":
                self.interval_spin = spin
            elif t == "超时(秒)":
                self.timeout_spin = spin
            else:
                self.history_spin = spin

        # TTL和字节参数
        ttk.Label(param_frame, text="TTL:").pack(side=tk.LEFT, padx=(8, 1))
        self.ttl_spin = ttk.Spinbox(param_frame, from_=1, to=255, width=5, command=self.apply_params)
        self.ttl_spin.bind('<KeyRelease>', lambda e: self.apply_params())
        self.ttl_spin.set(self.config.get('ping_ttl', 128))
        self.ttl_spin.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(param_frame, text="字节:").pack(side=tk.LEFT, padx=(8, 1))
        self.byte_spin = ttk.Spinbox(param_frame, from_=1, to=65500, width=6, command=self.apply_params)
        self.byte_spin.bind('<KeyRelease>', lambda e: self.apply_params())
        self.byte_spin.set(self.config.get('ping_bytes', 32))
        self.byte_spin.pack(side=tk.LEFT, padx=(0, 5))

        # 按钮栏
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(fill=tk.X, pady=6)

        self.import_btn = ttk.Button(btn_frame, text="📂 导入IP列表", command=self.import_ip_list)
        self.import_btn.pack(side=tk.LEFT, padx=3)
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始监控", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT, padx=3)
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止监控", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        self.export_btn = ttk.Button(btn_frame, text="📊 导出报告", command=self.export_report, state=tk.DISABLED)
        self.export_btn.pack(side=tk.LEFT, padx=3)
        self.settings_btn = ttk.Button(btn_frame, text="⚙ 设置", command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=3)
        self.about_btn = ttk.Button(btn_frame, text="ℹ 关于", command=self.show_about)
        self.about_btn.pack(side=tk.RIGHT, padx=3)

        # 图例
        legend_frame = ttk.Frame(self.root)
        legend_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        ttk.Label(legend_frame, text="图例:", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.legend_items = {}
        for key in STATUS_KEYS:
            color = self.config.get(f'{key}_color', STATUS_DEFAULTS[key])
            c = tk.Canvas(legend_frame, width=12, height=12, bg=color, highlightthickness=1, highlightbackground='#ccc')
            c.pack(side=tk.LEFT, padx=(6, 2))
            label = ttk.Label(legend_frame, text=STATUS_NAMES[key], font=("Arial", 8))
            label.pack(side=tk.LEFT, padx=(0, 8))
            self.legend_items[key] = c

        # 列标题
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        ttk.Label(header_frame, text="IP地址", font=("Arial", 9, "bold"), width=15).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="历史状态", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 150))
        ttk.Label(header_frame, text="当前状态", font=("Arial", 9, "bold"), width=16).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="统计", font=("Arial", 9, "bold"), width=18).pack(side=tk.LEFT)

        # 主区域
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 0))

        self.canvas = tk.Canvas(container, bg='white', highlightthickness=0)
        v_scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.inner_frame = tk.Frame(self.canvas, bg='white')
        self.canvas.create_window((0, 0), window=self.inner_frame, anchor=tk.NW)
        self.inner_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # 底部信息栏
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.cell_info_label = tk.Label(bottom_frame, text='', font=('Arial', 9),
                                        bg='#F0F0F0', fg='#555', anchor=tk.W, padx=10, pady=4)
        self.cell_info_label.pack(fill=tk.X)

        # IP手动添加栏
        add_frame = ttk.Frame(bottom_frame)
        add_frame.pack(fill=tk.X, pady=(5, 0))
        self.ip_entry = ttk.Entry(add_frame, width=20, font=('Consolas', 10))
        self.ip_entry.insert(0, '按回车添加IP')
        self.ip_entry.config(foreground='#aaa')
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.bind('<Return>', lambda e: self.add_manual_ip())
        self.ip_entry.bind('<FocusIn>', lambda e: self.clear_placeholder())
        self.ip_entry.bind('<FocusOut>', lambda e: self.restore_placeholder())
        self.add_msg_label = ttk.Label(add_frame, text="", font=("Arial", 8), foreground="#888")
        self.add_msg_label.pack(side=tk.LEFT, padx=10)
        self.import_label = ttk.Label(add_frame, text="", font=("Arial", 9), foreground="#888")
        self.import_label.pack(side=tk.LEFT)
        self.toast_label = ttk.Label(add_frame, text="", font=("Arial", 9), foreground="#00AA00")
        self.toast_label.pack(side=tk.RIGHT, padx=10)
        self.uptime_label = ttk.Label(add_frame, text="", font=("Arial", 9))
        self.uptime_label.pack(side=tk.RIGHT, padx=2)
        self.time_label = ttk.Label(add_frame, text="", font=("Arial", 9))
        self.time_label.pack(side=tk.RIGHT, padx=(0, 2))
        self.stats_label = ttk.Label(add_frame, text="总计: 0", font=("Arial", 11, "bold"))
        self.stats_label.pack(side=tk.RIGHT, padx=10)

        self.ip_widgets = {}
        self.context_menu = tk.Menu(self.root, tearoff=0, font=('Arial', 10))
        self.context_menu.add_command(label="设置备注", command=self.set_remark)
        self.context_menu.add_command(label="禁用监控", command=self.toggle_disable_ip)
        self.context_menu.add_command(label="删除", command=self.remove_context_ip)
        self.context_ip = None

    def show_cell_info(self, event, ip, cell_idx):
        if ip not in self.ip_data:
            return
        data = self.ip_data[ip]
        history = list(data['history'])
        if not history:
            return
        start_idx = max(0, len(history) - len(self.ip_widgets[ip]['cells']))
        real_idx = start_idx + cell_idx
        if real_idx < 0 or real_idx >= len(history):
            self.cell_info_label.config(text='')
            return

        entry = history[real_idx]
        if len(entry) == 5:
            s, lat, ttl, bs, ts = entry
        else:
            s, lat, ts = entry[0], entry[1] if len(entry) > 1 else '-', entry[2] if len(entry) > 2 else '-'
            ttl, bs = None, None

        name = STATUS_NAMES.get(s, s)
        extra = ''
        if s == 'normal':
            extra = f"延迟 {lat:.1f}ms"
        elif s in ('packet_loss_jitter', 'first_packet_timeout'):
            extra = f"延迟 {lat:.0f}ms" if isinstance(lat, (int, float)) else ''
        if ttl is not None:
            extra += f"  TTL={ttl}"
        if bs is not None:
            extra += f"  {bs}字节"

        count = real_idx + 1
        text = f"点击记录  |  {ip}  |  第 {count} 次Ping  |  时间 {ts}  |  状态: {name}"
        if extra:
            text += f"  |  {extra}"
        self.cell_info_label.config(text=text, fg='#333')

    def update_colors(self):
        for key in STATUS_KEYS:
            color = self.config.get(f'{key}_color', STATUS_DEFAULTS[key])
            setattr(self, f'{key}_color', color)
            if hasattr(self, 'legend_items') and key in self.legend_items:
                self.legend_items[key].config(bg=color)
        self._color_map = {
            'normal': self.normal_color, 'timeout': self.timeout_color,
            'unreachable': self.unreachable_color, 'ttl_expired': self.ttl_expired_color,
            'host_not_found': self.host_not_found_color, 'packet_loss_jitter': self.packet_loss_jitter_color,
            'first_packet_timeout': self.first_packet_timeout_color
        }
        # 重新刷新所有已显示的格子
        if hasattr(self, 'ip_widgets'):
            for ip, widgets in self.ip_widgets.items():
                if ip not in self.ip_data:
                    continue
                data = self.ip_data[ip]
                history = list(data['history'])
                cells = widgets['cells']
                start_idx = max(0, len(history) - len(cells))
                for i, cell in enumerate(cells):
                    idx = start_idx + i
                    if idx < len(history):
                        s = history[idx]
                        if isinstance(s, tuple):
                            s = s[0]
                        cell.config(bg=self._color_map.get(s, self.normal_color))
                    else:
                        cell.config(bg='#ddd')

    def open_settings(self):
        SettingsDialog(self.root, self)

    def show_toast(self, msg, fg='#00AA00'):
        self.toast_label.config(text=msg, foreground=fg)
        self.root.after(3000, lambda: self.toast_label.config(text=''))

    def start_auto_schedule(self):
        self.stop_auto_schedule()
        self._auto_cycle_id = None
        self._auto_stop_date = None
        self._auto_schedule_id = self.root.after(10000, self._check_auto_start)

    def stop_auto_schedule(self):
        if hasattr(self, '_auto_schedule_id') and self._auto_schedule_id:
            self.root.after_cancel(self._auto_schedule_id)
        self._auto_schedule_id = None

    def _check_auto_start(self):
        now = datetime.now()
        h = self.config.get('auto_start_hour', 8)
        m = self.config.get('auto_start_min', 0)
        sh = self.config.get('auto_stop_hour', 18)
        sm = self.config.get('auto_stop_min', 0)
        stop_after_start = (sh > h) or (sh == h and sm > m)
        today = now.date()
        today_key = today.isoformat()

        if self.pinging and self.config.get('auto_stop') and self._auto_cycle_id is not None:
            cs = datetime.fromisoformat(self._auto_cycle_id).date()
            stop_day = cs + timedelta(days=1)
            stop_dt = datetime.combine(stop_day, dt_time(sh, sm))
            if now >= stop_dt:
                self.stop_monitoring()
                self.show_toast('定时关闭')
                self._auto_cycle_id = None
                if stop_after_start:
                    self._auto_stop_date = today_key

        if not self.pinging and self.config.get('auto_start') and self.ip_list and self._auto_cycle_id is None:
            start_today = datetime.combine(today, dt_time(h, m))
            if now >= start_today:
                if not stop_after_start or self._auto_stop_date != today_key:
                    self._auto_cycle_id = today_key
                    try:
                        self.start_monitoring()
                        self.show_toast('定时启动')
                    except Exception:
                        pass

        self._auto_schedule_id = self.root.after(60000, self._check_auto_start)

    @staticmethod
    def _is_frozen():
        if getattr(sys, 'frozen', False):
            return True
        try:
            return __compiled__
        except NameError:
            return False

    def setup_crash_restart(self):
        bat_path = os.path.join(BASE_DIR, 'restart.bat')
        if self.config.get('crash_restart'):
            if self._is_frozen():
                exe_path = os.path.join(BASE_DIR, os.path.basename(sys.argv[0]))
            else:
                exe_path = os.path.join(BASE_DIR, os.path.basename(__file__))
            log_dir = os.path.join(BASE_DIR, 'log')
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(f'@echo off\n')
                f.write(f'chcp 65001 >nul\n')
                f.write(f'cd /d "{BASE_DIR}"\n')
                f.write(f'title Restart - Ping Monitor\n')
                f.write(f'Echo Auto restart is running, close this window to stop.\n')
                f.write(f':loop\n')
                if self._is_frozen():
                    f.write(f'start /wait "" "{exe_path}"\n')
                else:
                    f.write(f'start /wait "" pythonw "{exe_path}"\n')
                f.write(f'if exist "error.log" (\n')
                f.write(f'  if not exist "{log_dir}" mkdir "{log_dir}"\n')
                f.write(f'  move /y "error.log" "{os.path.join(log_dir, "crash.log")}" >nul\n')
                f.write(f')\n')
                f.write(f'echo Exited, restarting in 3 seconds...\n')
                f.write(f'ping -n 3 127.0.0.1 >nul\n')
                f.write(f'goto loop\n')
        else:
            if os.path.exists(bat_path):
                os.remove(bat_path)
        self._setup_crash_log()

    def _setup_crash_log(self):
        import traceback
        def excepthook(typ, val, tb):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = os.path.join(BASE_DIR, 'log', f'crash_{ts}.log')
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, 'w', encoding='utf-8') as f:
                    traceback.print_exception(typ, val, tb, file=f)
            except Exception:
                pass
            sys.__excepthook__(typ, val, tb)
        sys.excepthook = excepthook

    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("关于")
        about.resizable(False, False)
        about.transient(self.root)
        about.grab_set()
        about.update_idletasks()
        w, h = 320, 200
        px = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        about.geometry(f"{w}x{h}+{px}+{py}")

        frame = ttk.Frame(about, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="长Ping监控工具", font=("Arial", 14, "bold")).pack(pady=(10, 5))
        ttk.Label(frame, text="版本 1.0", font=("Arial", 10)).pack(pady=2)
        ttk.Label(frame, text="批量IP长Ping监控，支持多种状态检测", font=("Arial", 9), wraplength=280).pack(pady=5)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(frame, text="嘿哟 http://www.heiu.top", font=("Arial", 9), foreground="#0066CC").pack(pady=2)
        ttk.Button(frame, text="关闭", command=about.destroy).pack(pady=10)

    def import_ip_list(self):
        filename = filedialog.askopenfilename(title="选择IP列表文件", filetypes=[("文本文件","*.txt"),("CSV文件","*.csv"),("所有文件","*.*")])
        if not filename:
            return
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            ips = []
            remarks = {}
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                for sep in ['\t', ',', ';']:
                    if sep in line:
                        parts = line.split(sep, 1)
                        ip_part = parts[0].strip()
                        remark = parts[1].strip() if len(parts) > 1 else ''
                        break
                else:
                    ip_part = line
                    remark = ''
                if ip_part:
                    parsed = self.parse_ip_range(ip_part)
                    for p in parsed:
                        if p not in ips:
                            ips.append(p)
                            if remark:
                                remarks[p] = remark
            if not ips:
                messagebox.showwarning("警告", "文件中没有找到有效的IP地址!")
                return
            self.ip_list = ips
            self.ip_remarks.update(remarks)
            self.import_label.config(text=f"已导入 {len(ips)} 条")
            self.stats_label.config(text=f"总计: {len(ips)}")
            self.show_toast(f'导入成功: {len(ips)} 条')
            self.save_ip_list()
            self.init_display()
        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")

    def is_valid_ip(self, ip):
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    def parse_ip_range(self, text):
        """解析IP段，支持格式: 192.168.1.1, 192.168.1.0/24, 192.168.1.1-192.168.1.255, 192.168.1.1-255"""
        text = text.strip()
        if not text:
            return []

        # CIDR格式: 192.168.1.0/24
        if '/' in text:
            try:
                network, cidr = text.split('/')
                cidr = int(cidr)
                if not (0 <= cidr <= 32):
                    return []
                if not self.is_valid_ip(network):
                    return []
                mask = (0xFFFFFFFF << (32 - cidr)) & 0xFFFFFFFF
                net_addr = struct.unpack('!I', socket.inet_aton(network))[0] & mask
                count = 2 ** (32 - cidr)
                # 排除网络地址和广播地址
                start = 1 if count > 2 else 0
                end = count - 1 if count > 2 else count
                result = []
                for i in range(start, end):
                    ip = socket.inet_ntoa(struct.pack('!I', net_addr | i))
                    result.append(ip)
                return result
            except Exception:
                return []

        # 范围格式: 192.168.1.1-192.168.1.255 或 192.168.1.1-255
        if '-' in text:
            parts = text.split('-')
            if len(parts) != 2:
                return []
            start_str, end_str = parts[0].strip(), parts[1].strip()
            # 判断是否为完整IP
            if self.is_valid_ip(start_str):
                start_parts = list(map(int, start_str.split('.')))
                # 判断end是否为完整IP
                if self.is_valid_ip(end_str):
                    end_parts = list(map(int, end_str.split('.')))
                else:
                    # end只是最后一个数字
                    try:
                        end_val = int(end_str)
                        if not (0 <= end_val <= 255):
                            return []
                        end_parts = start_parts[:3] + [end_val]
                    except ValueError:
                        return []
                # 生成范围
                start_num = start_parts[0] << 24 | start_parts[1] << 16 | start_parts[2] << 8 | start_parts[3]
                end_num = end_parts[0] << 24 | end_parts[1] << 16 | end_parts[2] << 8 | end_parts[3]
                if start_num > end_num or end_num - start_num > 65536:
                    return []
                result = []
                for num in range(start_num, end_num + 1):
                    ip = f"{(num >> 24) & 0xFF}.{(num >> 16) & 0xFF}.{(num >> 8) & 0xFF}.{num & 0xFF}"
                    result.append(ip)
                return result
            return []

        # 单个IP
        if self.is_valid_ip(text):
            return [text]
        return []

    def add_manual_ip(self):
        raw = self.ip_entry.get().strip()
        if not raw or raw == '按回车添加IP':
            return
        remark = ''
        for sep in ['\t', ',', ';']:
            if sep in raw:
                parts = raw.split(sep, 1)
                raw = parts[0].strip()
                remark = parts[1].strip()
                break
        ips = self.parse_ip_range(raw)
        if not ips:
            self.add_msg_label.config(text="无效IP或IP段", foreground="#CC0000")
            self.root.after(2000, lambda: self.add_msg_label.config(text=""))
            return
        # 过滤已存在的
        new_ips = [ip for ip in ips if ip not in self.ip_list]
        if not new_ips:
            self.add_msg_label.config(text="IP已存在", foreground="#CC6600")
            self.root.after(2000, lambda: self.add_msg_label.config(text=""))
            return
        self.ip_list.extend(new_ips)
        if remark:
            for ip in new_ips:
                self.ip_remarks[ip] = remark
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.config(foreground='#aaa')
        self.ip_entry.insert(0, '按回车添加IP')
        self.add_msg_label.config(text=f"已添加 {len(new_ips)} 个IP", foreground="#00AA00")
        self.root.after(2000, lambda: self.add_msg_label.config(text=""))
        self.import_label.config(text=f"已导入 {len(self.ip_list)} 条")
        self.stats_label.config(text=f"总计: {len(self.ip_list)}")
        self.save_ip_list()
        self.init_display()
        # 如果正在监控中，对新IP启动监控
        if self.pinging:
            for ip in new_ips:
                if ip not in self.ping_threads:
                    t = threading.Thread(target=self.monitor_ip, args=(ip,), daemon=True)
                    self.ping_threads[ip] = t
                    t.start()

    def init_display(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
        self.ip_widgets.clear()
        self._prev_status.clear()
        self._alarm_until.clear()
        self.ip_data.clear()
        self.max_history = int(self.history_spin.get())

        for idx, ip in enumerate(self.ip_list):
            bg = '#F8F8F8' if idx % 2 == 0 else 'white'
            row_frame = tk.Frame(self.inner_frame, bg=bg)
            row_frame.pack(fill=tk.X, padx=2, pady=1)

            display_text = self.ip_remarks.get(ip, ip)
            ip_label = tk.Label(row_frame, text=display_text, font=('Consolas', 10, 'bold'),
                               bg=bg, fg='#333', width=20, anchor='w', padx=5)
            ip_label.pack(side=tk.LEFT)
            ip_label.bind('<Button-3>', lambda e, i=ip: self.show_context_menu(e, i))
            ip_label.bind('<Double-Button-1>', lambda e, i=ip: self.edit_remark(i))

            cells_frame = tk.Frame(row_frame, bg=bg)
            cells_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            cells = []
            for i in range(self.max_history):
                cell = tk.Canvas(cells_frame, width=8, height=22, bg='#ddd',
                                highlightthickness=1, highlightbackground='#eee', relief=tk.FLAT)
                cell.pack(side=tk.LEFT, padx=0)
                cell.bind('<Button-1>', lambda e, ip=ip, idx=i: self.show_cell_info(e, ip, idx))
                cells.append(cell)

            status_label = tk.Label(row_frame, text='等待中', font=('Consolas', 10),
                                   bg=bg, fg='#999', width=16, anchor='w', padx=8)
            status_label.pack(side=tk.LEFT)

            # 成功率进度条
            progress_canvas = tk.Canvas(row_frame, width=70, height=14, bg='#eee', highlightthickness=0)
            progress_canvas.pack(side=tk.LEFT, padx=(5, 0))
            progress_canvas.create_rectangle(0, 0, 0, 14, fill='#00CC00', outline='', tags='bar')
            progress_canvas.create_text(35, 7, text='0%', font=('Arial', 7), fill='#333', tags='pct')

            stats_label = tk.Label(row_frame, text='', font=('Consolas', 9),
                                  bg=bg, fg='#999', width=14, anchor='w', padx=5)
            stats_label.pack(side=tk.LEFT)

            self.ip_widgets[ip] = {
                'ip': ip_label, 'cells': cells, 'status_label': status_label,
                'stats': stats_label, 'row_bg': bg, 'progress': progress_canvas
            }
            self.ip_data[ip] = {
                'status': '等待中', 'latency': '-',
                'success_count': 0, 'fail_count': 0,
                'history': deque(maxlen=self.max_history),
                'recent_latencies': deque(maxlen=5),
                'total_normal': 0, 'total_pings': 0
            }

        for ip in self.ip_list:
            if ip in self._disabled_ips:
                self._update_disabled_ui(ip)

    def apply_params(self):
        self.config['ping_interval'] = float(self.interval_spin.get())
        self.config['ping_timeout'] = int(self.timeout_spin.get())
        self.config['ping_ttl'] = int(self.ttl_spin.get())
        self.config['ping_bytes'] = int(self.byte_spin.get())
        self.config['display_count'] = int(self.history_spin.get())
        self.save_config()
        new_count = int(self.history_spin.get())
        if new_count != self.max_history:
            self.max_history = new_count
            for ip, widgets in self.ip_widgets.items():
                cells_frame = widgets['cells'][0].master if widgets['cells'] else None
                if not cells_frame:
                    continue
                for c in widgets['cells']:
                    c.destroy()
                new_cells = []
                for i in range(self.max_history):
                    cell = tk.Canvas(cells_frame, width=8, height=22, bg='#ddd',
                                    highlightthickness=1, highlightbackground='#eee', relief=tk.FLAT)
                    cell.pack(side=tk.LEFT, padx=0)
                    cell.bind('<Button-1>', lambda e, ip=ip, idx=i: self.show_cell_info(e, ip, idx))
                    new_cells.append(cell)
                widgets['cells'] = new_cells
                self.ip_data[ip]['history'] = deque(self.ip_data[ip]['history'], maxlen=self.max_history)
                if self.ip_data[ip]['history']:
                    self.root.after(0, lambda i=ip: self.refresh_cells(i))

    def refresh_cells(self, ip):
        widgets = self.ip_widgets.get(ip)
        data = self.ip_data.get(ip)
        if not widgets or not data:
            return
        history = list(data['history'])
        cells = widgets['cells']
        start_idx = max(0, len(history) - len(cells))
        for i, cell in enumerate(cells):
            idx = start_idx + i
            if idx < len(history):
                s = history[idx]
                if isinstance(s, tuple):
                    s = s[0]
                cell.config(bg=self._color_map.get(s, self.normal_color))
            else:
                cell.config(bg='#ddd')

    def show_context_menu(self, event, ip):
        self.context_ip = ip
        self.context_menu.entryconfig(1, label="启用监控" if ip in self._disabled_ips else "禁用监控")
        self.context_menu.post(event.x_root, event.y_root)

    def remove_context_ip(self):
        ip = self.context_ip
        if ip is None or ip not in self.ip_list:
            return
        self.ip_list.remove(ip)
        if ip in self.ip_data:
            del self.ip_data[ip]
        if ip in self.ping_threads:
            del self.ping_threads[ip]
        if ip in self.ip_widgets:
            self.ip_widgets[ip]['ip'].master.destroy()
            del self.ip_widgets[ip]
        self.ip_remarks.pop(ip, None)
        self._prev_status.pop(ip, None)
        self._disabled_ips.discard(ip)
        self._alarm_until.pop(ip, None)
        self.import_label.config(text=f"已导入 {len(self.ip_list)} 条")
        self.stats_label.config(text=f"总计: {len(self.ip_list)}")
        self.save_ip_list()

    def toggle_disable_ip(self):
        ip = self.context_ip
        if ip is None or ip not in self.ip_list:
            return
        if ip in self._disabled_ips:
            self._disabled_ips.discard(ip)
        else:
            self._disabled_ips.add(ip)
        self._update_disabled_ui(ip)
        self._save_disabled_ips()

    def _update_disabled_ui(self, ip):
        if ip not in self.ip_widgets:
            return
        row_frame = self.ip_widgets[ip]['ip'].master
        disabled = ip in self._disabled_ips
        row_bg = '#f0f0f0' if disabled else '#fff'
        fg = '#999' if disabled else '#333'
        row_frame.config(bg=row_bg)
        base = self.ip_remarks.get(ip, ip)
        self.ip_widgets[ip]['ip'].config(text=('# ' + base) if disabled else base, bg=row_bg, fg=fg)
        self.ip_widgets[ip]['status_label'].config(
            text='已禁用' if disabled else '-',
            fg='#aaa' if disabled else '#999', bg=row_bg)
        for cell in self.ip_widgets[ip]['cells']:
            cell.config(bg='#eee' if disabled else '#ddd')
        self.ip_widgets[ip]['stats'].config(text='禁用' if disabled else '-', bg=row_bg, fg=fg)

    def _save_disabled_ips(self):
        self.config['disabled_ips'] = list(self._disabled_ips)
        self.save_config()

    def edit_remark(self, ip):
        if ip is None or ip not in self.ip_list:
            return
        self._show_remark_dialog(ip)

    def set_remark(self):
        ip = self.context_ip
        if ip is None or ip not in self.ip_list:
            return
        self._show_remark_dialog(ip)

    def _show_remark_dialog(self, ip):
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        w, h = 320, 200
        px = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{px}+{py}")
        frame = ttk.Frame(dialog, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="IP地址:").pack(anchor=tk.W)
        ip_entry = ttk.Entry(frame, width=30, font=('Consolas', 10))
        ip_entry.insert(0, ip)
        ip_entry.pack(fill=tk.X, pady=(2, 8))
        ttk.Label(frame, text="备注:").pack(anchor=tk.W)
        remark_entry = ttk.Entry(frame, width=30, font=('Arial', 10))
        cur = self.ip_remarks.get(ip, '')
        remark_entry.insert(0, cur)
        remark_entry.pack(fill=tk.X, pady=(2, 5))
        remark_entry.focus_set()
        def save():
            new_ip = ip_entry.get().strip()
            remark = remark_entry.get().strip()
            if not new_ip or not self.is_valid_ip(new_ip):
                return
            if new_ip != ip:
                if new_ip in self.ip_list:
                    return
                idx = self.ip_list.index(ip)
                self.ip_list[idx] = new_ip
                if ip in self.ip_data:
                    self.ip_data[new_ip] = self.ip_data.pop(ip)
                if ip in self.ip_widgets:
                    widgets = self.ip_widgets.pop(ip)
                    widgets['ip'].config(text=remark if remark else new_ip)
                    self.ip_widgets[new_ip] = widgets
                if ip in self.ping_threads:
                    self.ping_threads[new_ip] = self.ping_threads.pop(ip)
                if ip in self.ip_remarks:
                    self.ip_remarks[new_ip] = self.ip_remarks.pop(ip)
                if self.context_ip == ip:
                    self.context_ip = new_ip
            if remark:
                self.ip_remarks[new_ip if new_ip != ip else ip] = remark
            elif (new_ip if new_ip != ip else ip) in self.ip_remarks:
                del self.ip_remarks[new_ip if new_ip != ip else ip]
            self.save_ip_list()
            if new_ip in self.ip_widgets:
                self.ip_widgets[new_ip]['ip'].config(text=self.ip_remarks.get(new_ip, new_ip))
                self.ip_widgets[new_ip]['ip'].unbind('<Button-3>')
                self.ip_widgets[new_ip]['ip'].bind('<Button-3>', lambda e, i=new_ip: self.show_context_menu(e, i))
                self.ip_widgets[new_ip]['ip'].unbind('<Double-Button-1>')
                self.ip_widgets[new_ip]['ip'].bind('<Double-Button-1>', lambda e, i=new_ip: self.edit_remark(i))
            dialog.destroy()
        remark_entry.bind('<Return>', lambda e: save())
        ttk.Button(frame, text="确定", command=save).pack(pady=(10, 0))

    def detect_status(self, ip, timeout):
        byte_size = int(self.config.get('ping_bytes', 32))
        ttl_val = int(self.config.get('ping_ttl', 128))
        if os.name == 'nt':
            cmd = ['ping', '-n', '2', '-l', str(byte_size), '-i', str(ttl_val), '-w', str(timeout * 1000), ip]
        else:
            cmd = ['ping', '-c', '2', '-s', str(byte_size), '-t', str(ttl_val), '-W', str(timeout), ip]
        try:
            start = time.time()
            kw = {'capture_output': True, 'text': True, 'timeout': timeout * 2 + 2}
            if os.name == 'nt':
                kw['creationflags'] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.run(cmd, **kw)
            stdout, stderr = proc.stdout, proc.stderr
            elapsed = (time.time() - start) * 1000

            if '找不到主机' in stdout or 'could not find host' in stderr:
                return 'host_not_found', elapsed, None, None
            if '目标不可达' in stdout or 'Destination unreachable' in stdout:
                return 'unreachable', elapsed, None, None
            if 'TTL 传输中过期' in stdout or 'TTL expired' in stdout:
                return 'ttl_expired', elapsed, None, None

            latencies, timeouts, last_ttl, last_bytes = [], 0, None, None
            for line in stdout.split('\n'):
                if '请求超时' in line or 'Request timed out' in line:
                    timeouts += 1
                    continue
                m = re.search(r'时间[=<]\s*(\d+)', line) or re.search(r'time[=<](\d+\.?\d*)', line)
                if m:
                    latencies.append(float(m.group(1)))
                # 解析TTL
                ttl_m = re.search(r'TTL[=<]\s*(\d+)', line, re.IGNORECASE)
                if ttl_m:
                    last_ttl = int(ttl_m.group(1))
                # 解析字节
                byte_m = re.search(r'字节[=<]\s*(\d+)|bytes[=<]\s*(\d+)', line, re.IGNORECASE)
                if byte_m:
                    last_bytes = int(byte_m.group(1) or byte_m.group(2))

            if len(latencies) == 0:
                return 'timeout', elapsed, None, None
            if timeouts == 1 and len(latencies) >= 1:
                return 'first_packet_timeout', latencies[-1], last_ttl, last_bytes
            if timeouts == 1 or len(latencies) == 1:
                return 'packet_loss_jitter', latencies[0] if latencies else elapsed, last_ttl, last_bytes

            avg = sum(latencies) / len(latencies)
            data = self.ip_data.get(ip)
            if data:
                data['recent_latencies'].append(avg)
                recent = list(data['recent_latencies'])
                if len(recent) >= 3 and statistics.stdev(recent) > 15:
                    return 'packet_loss_jitter', avg, last_ttl, last_bytes
            if abs(latencies[0] - latencies[-1]) > 20:
                return 'packet_loss_jitter', avg, last_ttl, last_bytes
            return 'normal', avg, last_ttl, last_bytes
        except subprocess.TimeoutExpired:
            return 'timeout', 0, None, None
        except Exception:
            return 'timeout', 0, None, None

    def update_ip_cell(self, ip, status, latency, ttl, bytesize):
        if ip not in self.ip_widgets:
            return
        widgets = self.ip_widgets[ip]
        data = self.ip_data[ip]

        data['history'].append((status, latency, ttl, bytesize, datetime.now().strftime("%H:%M:%S")))
        data['status'] = STATUS_NAMES.get(status, status)
        data['latency'] = f"{latency:.1f}" if status == 'normal' else '-'
        data['total_pings'] += 1
        if status == 'normal':
            data['success_count'] += 1
            data['fail_count'] = 0
            data['total_normal'] += 1
        else:
            data['fail_count'] += 1
            data['success_count'] = 0

        # 告警：持续正常后出现异常，持续3秒告警
        prev = self._prev_status.get(ip)
        now_t = time.time()
        if self.config.get('alarm_enabled', True):
            if prev == 'normal' and status != 'normal':
                self._alarm_until[ip] = now_t + 3
            if self._alarm_until.get(ip, 0) > now_t and status != 'normal':
                self._play_alarm(status)
        self._prev_status[ip] = status

        # 更新格子
        history = list(data['history'])
        cells = widgets['cells']
        start_idx = max(0, len(history) - len(cells))
        for i, cell in enumerate(cells):
            idx = start_idx + i
            if idx < len(history):
                s = history[idx]
                if isinstance(s, tuple):
                    s = s[0]
                cell.config(bg=self._color_map.get(s, self.normal_color))
            else:
                cell.config(bg='#ddd')

        # 状态文本 - 显示用户配置的TTL/字节
        cfg_ttl = self.config.get('ping_ttl', 128)
        cfg_bytes = self.config.get('ping_bytes', 32)
        status_text_map = {
            'normal': f'{latency:.1f}ms TTL={cfg_ttl} {cfg_bytes}B', 'timeout': '请求超时', 'unreachable': '目标不可达',
            'ttl_expired': 'TTL过期', 'host_not_found': '找不到主机',
            'packet_loss_jitter': f'丢包/抖动 {latency:.0f}ms',
            'first_packet_timeout': f'首包超时 {latency:.0f}ms'
        }
        color = self._color_map.get(status, '#999')
        widgets['status_label'].config(text=status_text_map.get(status, status), fg=color)
        widgets['ip'].config(fg=color)
        widgets['stats'].config(text=f'✓{data["total_normal"]} ✗{data["total_pings"] - data["total_normal"]}')

        # 更新进度条
        rate = (data['total_normal'] / data['total_pings'] * 100) if data['total_pings'] else 0
        prog = widgets['progress']
        prog.delete('all')
        bar_w = max(0, rate / 100 * 68)
        if rate >= 90:
            bar_color = '#00CC00'
        elif rate >= 70:
            bar_color = '#CCCC00'
        else:
            bar_color = '#CC0000'
        prog.create_rectangle(0, 0, bar_w, 14, fill=bar_color, outline='', tags='bar')
        prog.create_text(35, 7, text=f'{rate:.0f}%', font=('Arial', 7), fill='#333' if rate > 40 else '#fff', tags='pct')

    def _play_alarm(self, status):
        sound = self.config.get(f'alarm_{status}', ALARM_DEFAULT_SOUNDS.get(status, 'hand'))
        try:
            if sound == 'hand':
                winsound.MessageBeep(winsound.MB_ICONHAND)
            elif sound == 'exclamation':
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sound == 'asterisk':
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sound == 'beep_low':
                winsound.Beep(400, 300)
            elif sound == 'beep_mid':
                winsound.Beep(800, 300)
            elif sound == 'beep_high':
                winsound.Beep(1600, 300)
        except Exception:
            pass

    def monitor_ip(self, ip):
        while self.pinging:
            try:
                if ip in self._disabled_ips:
                    time.sleep(1)
                    continue
                interval = float(self.config.get('ping_interval', 0))
                timeout = int(self.config.get('ping_timeout', 1))
                status, latency, ttl, byte_size = self.detect_status(ip, timeout)
                self.write_record(ip, status, latency, ttl, byte_size)
                self.result_queue.put((ip, status, latency, ttl, byte_size))
                self._schedule_process()
            except Exception as e:
                print(f"{ip} error: {e}")
            time.sleep(interval)

    def _update_stats_uptime(self):
        total = len(self.ip_data)
        normal = sum(1 for d in self.ip_data.values() if d['status'] == '正常连通')
        elapsed = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        m, s = int(elapsed // 60), int(elapsed % 60)
        self.stats_label.config(text=f"正常: {normal}  异常: {total - normal}  总计: {total}")
        self.import_label.config(text="")
        self.uptime_label.config(text=f"运行: {m}分{s}秒")

    def _update_time(self):
        self.time_label.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_time)

    def _schedule_periodic_stats(self):
        if self.pinging:
            self._update_stats_uptime()
            self.root.after(1000, self._schedule_periodic_stats)

    def _schedule_process(self):
        if not self._update_scheduled:
            self._update_scheduled = True
            self.root.after(50, self._process_results)

    def _process_results(self):
        self._update_scheduled = False
        items = []
        try:
            while True:
                items.append(self.result_queue.get_nowait())
        except queue_module.Empty:
            pass
        if not items:
            return
        for ip, status, latency, ttl, byte_size in items:
            self.update_ip_cell(ip, status, latency, ttl, byte_size)
        if not self.result_queue.empty():
            self._schedule_process()

    def start_monitoring(self):
        if not self.ip_list:
            messagebox.showwarning("警告", "请先导入IP列表!")
            return
        self.pinging = True
        self.start_time = time.time()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.import_btn.config(state=tk.DISABLED)
        self.export_btn.config(state=tk.NORMAL)
        for ip in self.ip_list:
            if ip not in self.ping_threads:
                t = threading.Thread(target=self.monitor_ip, args=(ip,), daemon=True)
                self.ping_threads[ip] = t
            t.start()
        self._schedule_periodic_stats()

    def clear_placeholder(self):
        if self.ip_entry.get() in ('按回车添加IP', '按回车添加IP'):
            self.ip_entry.delete(0, tk.END)
            self.ip_entry.config(foreground='#000')

    def restore_placeholder(self):
        if not self.ip_entry.get().strip():
            self.ip_entry.insert(0, '按回车添加IP')
            self.ip_entry.config(foreground='#aaa')

    def stop_monitoring(self):
        self.pinging = False
        self.ping_threads.clear()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.import_btn.config(state=tk.NORMAL)
        self.root.after(100, self._process_results)
        self.root.after(200, self._update_stats_uptime)

    def export_report(self):
        filename = filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("文本文件","*.txt")],
            initialfile=f"ping_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        if not filename:
            return
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n长Ping监控报告\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                for ip in self.ip_list:
                    d = self.ip_data.get(ip, {})
                    h = list(d.get('history', []))
                    n = sum(1 for x in h if (isinstance(x, tuple) and x[0] == 'normal') or x == 'normal')
                    t = len(h)
                    r = n / t * 100 if t else 0
                    f.write(f"IP: {ip}\n状态: {d.get('status','-')}\n延迟: {d.get('latency','-')}ms\n正常: {n}/{t} ({r:.1f}%)\n")
                    f.write("-" * 30 + "\n")
            messagebox.showinfo("成功", "报告已导出")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")


def center_window(win, width, height):
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{width}x{height}+{(sw - width)//2}+{(sh - height)//2}")


if __name__ == '__main__':
    try:
        root = tk.Tk()
        center_window(root, 1000, 600)
        app = LongPingApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = [os.path.join(BASE_DIR, 'error.log'), os.path.join(BASE_DIR, f'error_{ts}.log')]
        log_dir = os.path.join(BASE_DIR, 'log')
        if os.path.exists(log_dir):
            paths.append(os.path.join(log_dir, f'crash_{ts}.log'))
        for p in paths:
            try:
                with open(p, 'w', encoding='utf-8') as f:
                    traceback.print_exc(file=f)
            except Exception:
                pass
        raise
