# manager.py (v4.2.0 - 健壮路径版)
import customtkinter as ctk
import subprocess
import sys
import os
import threading
import queue
import time
import pyperclip
import json
from datetime import datetime
from configobj import ConfigObj
from tkinter import filedialog, messagebox

# ---【路径修正：第一部分】---
# 获取 manager.py 自身的绝对目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 根据自身目录，定义所有依赖项的绝对路径
PROFILES_DIR = os.path.join(script_dir, 'profiles')
CREDENTIALS_DIR = os.path.join(script_dir, 'credentials')
GROUPS_FILE = os.path.join(script_dir, 'groups.json')
BASE_CONFIG_TEMPLATE = os.path.join(script_dir, 'yt.ini')
STREAMER_SCRIPT_PATH = os.path.join(script_dir, 'streamer.py')
# ---【修正结束】---

# ====================================================================
#                      设定项中文翻译字典
# ====================================================================
TRANSLATIONS = {
    "Douyin": {"douyin_id": "抖音主播ID", "wait_time": "页面加载等待时间 (秒)", "check_interval": "直播检测间隔 (秒)"},
    "YouTube": {"token_file": "凭证档案 (credentials/)", "broadcast_title": "直播标题", "broadcast_description": "直播说明/描述", "category_id": "直播分类ID", "privacy_status": "隐私状态", "enable_auto_start": "自动开始直播", "enable_auto_stop": "自动结束直播", "enable_dvr": "启用 DVR (回看功能)", "record_from_start": "从推流开始录製"},
    "FFmpeg": {"ffmpeg_path": "ffmpeg程式路径", "bitrate": "影片码率 (例如 4000k)"},
    "System": {"chrome_path": "浏览器程式路径"},
    "Proxy": {"proxy_url": "代理伺服器URL (http/socks5)"},
    "Custom": {"remarks": "主播备注", "group": "主播分组"},
}

# ====================================================================
#                      设定视窗类别
# ====================================================================
class EditSettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, profile_path):
        super().__init__(master)
        self.transient(master)
        self.profile_path = profile_path
        self.config_filepath = os.path.join(profile_path, 'config.ini')
        self.master = master
        self.widgets = {}

        try:
            self.config = ConfigObj(self.config_filepath, encoding='UTF8', indent_type='  ')
        except Exception as e:
            self.log_to_main(f"错误: 无法加载设定档 {self.config_filepath}: {e}")
            self.destroy()
            return
            
        douyin_id = self.config.get('Douyin', {}).get('douyin_id', os.path.basename(profile_path))
        self.title(f"修改设定 - {douyin_id}")
        self.geometry("700x600")
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=5)
        self.create_tabs()
        
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkButton(button_frame, text="储存并关闭", command=self.save_and_close).pack(side="right", padx=(10, 0))
        ctk.CTkButton(button_frame, text="取消", command=self.cancel, fg_color="gray").pack(side="right")
        
        self.lift()
        self.grab_set()

    def log_to_main(self, message, level='ERROR'):
        if hasattr(self.master, 'log'):
            self.master.log(message, level)

    def create_tabs(self):
        for section, options in TRANSLATIONS.items():
            tab = self.tabview.add(section)
            scrollable_frame = ctk.CTkScrollableFrame(tab, label_text=f"{section} 设定")
            scrollable_frame.pack(expand=True, fill="both", padx=5, pady=5)
            scrollable_frame.grid_columnconfigure(1, weight=1)
            self.widgets[section] = {}

            for i, (option_key, label_text) in enumerate(options.items()):
                label = ctk.CTkLabel(scrollable_frame, text=label_text, anchor="w")
                label.grid(row=i, column=0, padx=10, pady=8, sticky="w")
                
                value = self.config.get(section, {}).get(option_key, "")
                widget_container = self.create_widget_for_option(scrollable_frame, section, option_key, value)
                widget_container.grid(row=i, column=1, padx=10, pady=8, sticky="ew")

    def create_widget_for_option(self, parent, section, option, value):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid_columnconfigure(0, weight=1)
        main_widget = None

        if option.endswith('_path'):
            entry = ctk.CTkEntry(container)
            entry.insert(0, value)
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
            button = ctk.CTkButton(container, text="浏览...", width=60, command=lambda e=entry: self.browse_file(e))
            button.grid(row=0, column=1, sticky="e")
            main_widget = entry
        elif option == 'token_file':
            self.token_label = ctk.CTkLabel(container, text=value, anchor="w")
            self.token_label.grid(row=0, column=0, sticky="ew", padx=(0, 5))
            button = ctk.CTkButton(container, text="选择凭证...", width=90, command=self.browse_token_file)
            button.grid(row=0, column=1, sticky="e")
            main_widget = self.token_label
        elif option.startswith('enable_'):
            switch = ctk.CTkSwitch(container, text="", onvalue=True, offvalue=False)
            if str(value).lower() == 'true': switch.select()
            else: switch.deselect()
            switch.pack(anchor="w")
            main_widget = switch
        elif option == 'privacy_status':
            menu = ctk.CTkOptionMenu(container, values=["public", "private", "unlisted"])
            menu.set(value if value in ["public", "private", "unlisted"] else "private")
            menu.pack(anchor="w")
            main_widget = menu
        elif option in ['broadcast_description', 'remarks']:
            textbox = ctk.CTkTextbox(container, height=120)
            textbox.insert("1.0", value)
            textbox.pack(expand=True, fill="both")
            main_widget = textbox
        else:
            entry = ctk.CTkEntry(container)
            entry.insert(0, str(value))
            entry.pack(expand=True, fill="x")
            if section == "Douyin" and option == "douyin_id":
                entry.configure(state="disabled")
            main_widget = entry

        self.widgets[section][option] = main_widget
        return container

    def browse_file(self, entry_widget):
        filepath = filedialog.askopenfilename()
        if filepath:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, filepath)

    def browse_token_file(self):
        # ---【路径修正】---
        if not os.path.isdir(CREDENTIALS_DIR):
            os.makedirs(CREDENTIALS_DIR)
            self.log_to_main(f"已自动创建 '{CREDENTIALS_DIR}' 资料夹。")
        filepath = filedialog.askopenfilename(title="选择 YouTube 凭证档案", initialdir=CREDENTIALS_DIR, filetypes=(("JSON files", "*.json"), ("All files", "*.*")))
        if filepath:
            filename = os.path.basename(filepath)
            self.token_label.configure(text=filename)

    def save_and_close(self):
        for section, widgets_info in self.widgets.items():
            if section not in self.config: self.config[section] = {}
            for option, widget in widgets_info.items():
                value = ""
                if isinstance(widget, ctk.CTkSwitch): value = "true" if widget.get() else "false"
                elif isinstance(widget, ctk.CTkTextbox): value = widget.get("1.0", "end-1c")
                elif isinstance(widget, ctk.CTkLabel) and option == 'token_file': value = widget.cget("text")
                else: value = widget.get()
                self.config[section][option] = str(value)
        try:
            self.config.write()
            self.log_to_main(f"已储存主播 {os.path.basename(self.profile_path)} 的设定。", "INFO")
        except Exception as e:
            self.log_to_main(f"储存设定档失败: {e}")
        
        self.master.refresh_streamer_list()
        self.destroy()

    def cancel(self):
        self.destroy()

# ====================================================================
#                        分组管理视窗
# ====================================================================
class GroupManagerWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.groups_filepath = GROUPS_FILE # ---【路径修正】---

        self.title("分组管理")
        self.geometry("400x450")
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.grab_set()

        try:
            with open(self.groups_filepath, 'r', encoding='utf-8') as f:
                self.groups = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"读取 {self.groups_filepath} 失败: {e}")
            self.groups = ["默认分组"]

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        add_frame = ctk.CTkFrame(self.main_frame)
        add_frame.pack(fill="x", pady=(0, 10))
        add_frame.grid_columnconfigure(0, weight=1)
        self.add_entry = ctk.CTkEntry(add_frame, placeholder_text="输入新分组名称...")
        self.add_entry.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.add_button = ctk.CTkButton(add_frame, text="✚ 新增", width=60, command=self.add_group)
        self.add_button.grid(row=0, column=1)

        self.scrollable_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="现有分组")
        self.scrollable_frame.pack(expand=True, fill="both")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.populate_groups()

    def populate_groups(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        for i, group_name in enumerate(self.groups):
            row_frame = ctk.CTkFrame(self.scrollable_frame)
            row_frame.grid(row=i, column=0, pady=3, sticky="ew")
            row_frame.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(row_frame, text=group_name)
            label.grid(row=0, column=0, padx=5, sticky="w")
            edit_button = ctk.CTkButton(row_frame, text="✏️ 编辑", width=50, command=lambda g=group_name: self.edit_group(g))
            edit_button.grid(row=0, column=1, padx=5)
            delete_button = ctk.CTkButton(row_frame, text="🗑️ 删除", width=50, fg_color="#D32F2F", hover_color="#B71C1C", command=lambda g=group_name: self.delete_group(g))
            delete_button.grid(row=0, column=2, padx=5)

    def _save_groups(self):
        try:
            with open(self.groups_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.groups, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            messagebox.showerror("错误", f"储存 {self.groups_filepath} 失败: {e}")
            return False

    def add_group(self):
        new_group = self.add_entry.get().strip()
        if not new_group: messagebox.showwarning("提示", "分组名称不能为空。"); return
        if new_group in self.groups: messagebox.showwarning("提示", f"分组 '{new_group}' 已存在。"); return
        self.groups.append(new_group)
        if self._save_groups():
            self.master.log(f"已新增分组: {new_group}", "INFO")
            self.add_entry.delete(0, 'end')
            self.populate_groups()

    def edit_group(self, old_name):
        dialog = ctk.CTkInputDialog(text=f"请输入 '{old_name}' 的新名称:", title="编辑分组")
        new_name = dialog.get_input()
        if not new_name or not new_name.strip(): return
        new_name = new_name.strip()
        if new_name == old_name: return
        if new_name in self.groups: messagebox.showwarning("提示", f"分组 '{new_name}' 已存在。"); return
        self.update_streamer_configs(old_name, new_name)
        index = self.groups.index(old_name)
        self.groups[index] = new_name
        if self._save_groups():
            self.master.log(f"已将分组 '{old_name}' 重新命名为 '{new_name}'。", "INFO")
            self.populate_groups()

    def delete_group(self, group_name):
        if self.is_group_in_use(group_name):
            messagebox.showerror("错误", f"无法删除分组 '{group_name}'，因为有主播正在使用它。\n请先将相关主播移至其他分组。")
            return
        if messagebox.askyesno("确认删除", f"您确定要删除分组 '{group_name}' 吗？此操作无法复原。"):
            self.groups.remove(group_name)
            if self._save_groups():
                self.master.log(f"已删除分组: {group_name}", "INFO")
                self.populate_groups()
    
    def is_group_in_use(self, group_name):
        # ---【路径修正】---
        for profile_id in os.listdir(PROFILES_DIR):
            profile_path = os.path.join(PROFILES_DIR, profile_id)
            if not os.path.isdir(profile_path): continue
            config_path = os.path.join(profile_path, 'config.ini')
            if os.path.exists(config_path):
                try:
                    conf = ConfigObj(config_path, encoding='UTF8')
                    if conf.get('Custom', {}).get('group') == group_name: return True
                except: continue
        return False

    def update_streamer_configs(self, old_name, new_name):
        # ---【路径修正】---
        for profile_id in os.listdir(PROFILES_DIR):
            profile_path = os.path.join(PROFILES_DIR, profile_id)
            if not os.path.isdir(profile_path): continue
            config_path = os.path.join(profile_path, 'config.ini')
            if os.path.exists(config_path):
                try:
                    conf = ConfigObj(config_path, encoding='UTF8', indent_type='  ')
                    if conf.get('Custom', {}).get('group') == old_name:
                        conf['Custom']['group'] = new_name
                        conf.write()
                except: continue
    
    def close_window(self):
        self.master.discover_and_refresh()
        self.destroy()

# ====================================================================
#                        主播卡片类别
# ====================================================================
class StreamerCard(ctk.CTkFrame):
    # (此类别内部无需修改，因为它从外部接收绝对路径)
    def __init__(self, master, profile_path, manager_app):
        super().__init__(master, fg_color=("#f0f0f0", "#282828"), corner_radius=10)
        self.profile_path = profile_path
        self.manager = manager_app
        self.douyin_id = os.path.basename(profile_path)
        self.config = ConfigObj(os.path.join(profile_path, 'config.ini'), encoding='UTF8')
        self.grid_columnconfigure(1, weight=1)
        self.status_color_bar = ctk.CTkFrame(self, width=10, corner_radius=0, fg_color="gray")
        self.status_color_bar.grid(row=0, rowspan=2, column=0, sticky="nsw")
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, rowspan=2, column=1, padx=10, pady=5, sticky="nsew")
        info_frame.grid_columnconfigure(1, weight=1)
        top_info_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        top_info_frame.pack(fill="x", pady=(5,0))
        top_info_frame.grid_columnconfigure(1, weight=1)
        groups = self.manager.groups
        current_group = self.config.get('Custom', {}).get('group', '默认分组')
        if current_group not in groups: groups.append(current_group)
        self.group_menu = ctk.CTkOptionMenu(top_info_frame, values=groups, command=self.update_group, width=120)
        self.group_menu.set(current_group)
        self.group_menu.grid(row=0, column=0, sticky="w")
        id_text = self.config.get('Douyin', {}).get('douyin_id', self.douyin_id)
        self.id_label = ctk.CTkLabel(top_info_frame, text=id_text, font=("", 16, "bold"))
        self.id_label.grid(row=0, column=1, sticky="w", padx=10)
        middle_info_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        middle_info_frame.pack(fill="x", pady=5)
        self.status_label = ctk.CTkLabel(middle_info_frame, text="⚪ 已停止", font=("", 14), width=150, anchor="w")
        self.status_label.pack(side="left")
        self.duration_label = ctk.CTkLabel(middle_info_frame, text="时长: --:--:--", font=("", 12), anchor="w")
        self.duration_label.pack(side="left", padx=10)
        remarks = self.config.get('Custom', {}).get('remarks', '无备注')
        self.remarks_label = ctk.CTkLabel(info_frame, text=f"备注: {remarks}", justify="left", wraplength=400, anchor="w", fg_color="transparent")
        self.remarks_label.pack(fill="x", pady=(0,5))
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, rowspan=2, column=2, padx=10, pady=10, sticky="ns")
        self.start_button = ctk.CTkButton(button_frame, text="▶ 启动", width=80, command=lambda: self.manager.start_streamer(self.profile_path, self.douyin_id))
        self.start_button.pack(pady=3, fill="x")
        self.stop_button = ctk.CTkButton(button_frame, text="■ 停止", width=80, fg_color="#D32F2F", hover_color="#B71C1C", state="disabled", command=lambda: self.manager.stop_streamer(self.douyin_id))
        self.stop_button.pack(pady=3, fill="x")
        self.settings_button = ctk.CTkButton(button_frame, text="⚙️ 设定", width=80, fg_color="gray", command=lambda: self.manager.edit_settings(self.profile_path))
        self.settings_button.pack(pady=3, fill="x")
        self.delete_button = ctk.CTkButton(button_frame, text="🗑️ 删除", width=80, fg_color="#c0392b", hover_color="#e74c3c", command=lambda: self.manager.delete_streamer(self.douyin_id, self.profile_path))
        self.delete_button.pack(pady=(10, 3), fill="x")
    def update_group(self, new_group):
        try:
            self.config['Custom']['group'] = new_group
            self.config.write()
            self.manager.log(f"主播 {self.douyin_id} 的分组已更新为 '{new_group}'。", "INFO")
            self.manager.after(100, self.manager.discover_and_refresh)
        except Exception as e:
            self.manager.log(f"更新分组失败: {e}", "ERROR")

# ====================================================================
#                        总控制台主程式
# ====================================================================
class ManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("抖音转播总控制台 (v4.2.0 - 健壮路径版)")
        self.geometry("950x750")

        self.check_files()
        
        self.running_processes = {}
        self.streamer_cards = {}
        self.log_queue = queue.Queue()
        self.groups = []
        self.current_filter = ctk.StringVar(value="All Groups")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0, minsize=200)

        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(top_frame, text="✚ 新建直播", command=self.create_new_streamer).pack(side="left", padx=5)
        ctk.CTkButton(top_frame, text="↻ 刷新列表", command=self.discover_and_refresh).pack(side="left", padx=5)
        ctk.CTkButton(top_frame, text="🗂️ 管理分组", command=self.open_group_manager).pack(side="left", padx=5)
        ctk.CTkLabel(top_frame, text="").pack(side="left", expand=True) # Spacer
        ctk.CTkLabel(top_frame, text="筛选:").pack(side="left", padx=(15, 5))
        self.group_filter_menu = ctk.CTkOptionMenu(top_frame, variable=self.current_filter, command=lambda _: self.refresh_streamer_list())
        self.group_filter_menu.pack(side="left", padx=5)

        self.dashboard_frame = ctk.CTkScrollableFrame(self, label_text="主播仪表板")
        self.dashboard_frame.grid(row=1, column=0, padx=10, pady=0, sticky="nsew")
        self.dashboard_frame.grid_columnconfigure(0, weight=1)

        log_label_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_label_frame.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="ew")
        ctk.CTkLabel(log_label_frame, text="统一日志中心", font=("", 14, "bold")).pack(side="left")
        ctk.CTkButton(log_label_frame, text="🧹 清理日志", width=80, command=self.clear_logs).pack(side="right")

        self.log_textbox = ctk.CTkTextbox(self, state="disabled", wrap="word", font=("", 13))
        self.log_textbox.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        
        mode = ctk.get_appearance_mode()
        if mode == "Dark": info_color, warn_color, error_color, manager_color = "#FFFFFF", "#FFD700", "#FF6347", "#87CEFA"
        else: info_color, warn_color, error_color, manager_color = "#333333", "#FF8C00", "#B22222", "#00008B"
        self.log_textbox.tag_config("INFO", foreground=info_color); self.log_textbox.tag_config("WARN", foreground=warn_color); self.log_textbox.tag_config("ERROR", foreground=error_color); self.log_textbox.tag_config("DEBUG", foreground="gray"); self.log_textbox.tag_config("MANAGER", foreground=manager_color)

        self.discover_and_refresh()
        self.check_log_queue()
        self.update_durations()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def check_files(self):
        # ---【路径修正】---
        if not os.path.isdir(PROFILES_DIR): os.makedirs(PROFILES_DIR)
        if not os.path.isdir(CREDENTIALS_DIR): os.makedirs(CREDENTIALS_DIR)
        if not os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(["默认分组"], f, ensure_ascii=False, indent=4)
            messagebox.showinfo("提示", "已为您自动建立 'groups.json' 分组设定档。")

    def open_group_manager(self): GroupManagerWindow(self)
    def log(self, message, level="MANAGER"): self.log_queue.put((f"[{time.strftime('%H:%M:%S')}] {message}", level.upper()))
    def clear_logs(self): self.log_textbox.configure(state="normal"); self.log_textbox.delete("1.0", "end"); self.log_textbox.configure(state="disabled")

    def check_log_queue(self):
        try:
            while True:
                message, level = self.log_queue.get_nowait()
                self.log_textbox.configure(state="normal"); self.log_textbox.insert("end", message + "\n", level); self.log_textbox.see("end"); self.log_textbox.configure(state="disabled")
        except queue.Empty: pass
        finally: self.after(250, self.check_log_queue)
    
    def update_durations(self):
        for douyin_id, info in self.running_processes.items():
            if 'start_time' in info and douyin_id in self.streamer_cards:
                duration = int(time.time() - info['start_time'])
                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.streamer_cards[douyin_id].duration_label.configure(text=f"时长: {hours:02}:{minutes:02}:{seconds:02}")
        self.after(1000, self.update_durations)

    def discover_groups(self):
        try:
            # ---【路径修正】---
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f: self.groups = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): self.groups = ["默认分组"]
        filter_menu_values = ["All Groups"] + self.groups
        self.group_filter_menu.configure(values=filter_menu_values)
        if self.current_filter.get() not in filter_menu_values: self.current_filter.set("All Groups")

    def discover_and_refresh(self): self.discover_groups(); self.refresh_streamer_list()

    def refresh_streamer_list(self):
        for card in self.streamer_cards.values(): card.destroy()
        self.streamer_cards.clear()
        selected_group = self.current_filter.get()
        # ---【路径修正】---
        if not os.path.isdir(PROFILES_DIR): return
        profile_ids = sorted(os.listdir(PROFILES_DIR))
        
        for profile_id in profile_ids:
            # ---【路径修正】---
            profile_path = os.path.join(PROFILES_DIR, profile_id)
            if not os.path.isdir(profile_path): continue
            config_path = os.path.join(profile_path, 'config.ini')
            if not os.path.exists(config_path): continue
            try:
                conf = ConfigObj(config_path, encoding='UTF8')
                group = conf.get('Custom', {}).get('group', '默认分组').strip()
                if selected_group == "All Groups" or group == selected_group:
                    card = StreamerCard(self.dashboard_frame, profile_path, self)
                    card.pack(fill="x", padx=10, pady=5)
                    self.streamer_cards[profile_id] = card
            except Exception as e:
                self.log(f"加载主播 {profile_id} 时出错: {e}", "ERROR")
        for douyin_id in self.running_processes.keys():
            self.update_ui_for_process(douyin_id, is_running=True)
            if 'status' in self.running_processes[douyin_id]:
                self.update_status_ui(douyin_id, self.running_processes[douyin_id]['status'])
    
    def start_streamer(self, profile_path, douyin_id):
        if douyin_id in self.running_processes: self.log(f"主播 {douyin_id} 已经在运行中。", "WARN"); return
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        # ---【路径修正】---
        command = [sys.executable, "-u", STREAMER_SCRIPT_PATH, profile_path]
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore', creationflags=creationflags)
            self.running_processes[douyin_id] = {'process': process, 'status': 'starting', 'start_time': time.time()}
            threading.Thread(target=self.read_output, args=(douyin_id, process), daemon=True).start()
            self.log(f"已启动主播 {douyin_id} (PID: {process.pid})")
            self.update_ui_for_process(douyin_id, is_running=True)
            self.update_status_ui(douyin_id, "starting")
        except FileNotFoundError:
             self.log(f"启动失败: 找不到 '{STREAMER_SCRIPT_PATH}'。请确保它与 manager.py 在同一目录下。", "ERROR")
        except Exception as e:
            self.log(f"启动主播 {douyin_id} 时发生未知错误: {e}", "ERROR")

    def read_output(self, douyin_id, process):
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line: continue
            if line.startswith("STATUS:"):
                status = line.split(":", 1)[1]
                if douyin_id in self.running_processes: self.running_processes[douyin_id]['status'] = status
                self.after(0, self.update_status_ui, douyin_id, status)
            elif line.startswith("TITLE:"):
                title = line.split(":", 1)[1]
                self.after(0, self.update_remarks_with_title, douyin_id, title)
            elif line.startswith("LOG:"):
                parts = line.split(":", 2)
                level, message = (parts[1], parts[2]) if len(parts) > 2 else ("INFO", parts[0])
                self.log(f"[{douyin_id}] {message}", level)
            else: self.log(f"[{douyin_id}] {line}", "DEBUG")
        process.wait()
        if douyin_id in self.running_processes:
            self.log(f"检测到主播 {douyin_id} 的程序已终止。")
            del self.running_processes[douyin_id]
            self.after(0, self.update_ui_for_process, douyin_id, False)
            self.after(0, self.update_status_ui, douyin_id, "stopped")

    def stop_streamer(self, douyin_id):
        if douyin_id in self.running_processes:
            process_info = self.running_processes.pop(douyin_id)
            process_info['process'].terminate()
            self.log(f"已发送停止信号给主播 {douyin_id}")
            self.update_ui_for_process(douyin_id, is_running=False)
            self.update_status_ui(douyin_id, "stopped")
        else: self.log(f"尝试停止主播 {douyin_id}，但他不在运行中。", "WARN")

    def update_status_ui(self, douyin_id, status):
        if douyin_id not in self.streamer_cards: return
        card = self.streamer_cards[douyin_id]
        status_map = {"stopped": ("⚪ 已停止", "gray"), "starting": ("⏳ 启动中", "#E0B310"), "checking": ("🟡 正在检查", "#F9A825"), "streaming": ("🟢 正在推流", "#2E7D32"), "offline": ("🌙 主播未开播", "#607D8B"), "error": ("🔴 错误", "#D32F2F")}
        text, color = status_map.get(status, ("❔ 未知", "white"))
        card.status_label.configure(text=text)
        card.status_color_bar.configure(fg_color=color)
        if status in ["stopped", "error"]: card.duration_label.configure(text="时长: --:--:--")

    def update_remarks_with_title(self, douyin_id, title):
        if douyin_id not in self.streamer_cards: return
        card = self.streamer_cards[douyin_id]
        config_path = os.path.join(card.profile_path, 'config.ini')
        try:
            conf = ConfigObj(config_path, encoding='UTF8', indent_type='  ')
            current_remarks = conf.get('Custom', {}).get('remarks', '')
            timestamp = time.strftime('%m-%d %H:%M')
            new_title_line = f"[{timestamp}] {title}"
            if new_title_line in current_remarks: return
            remark_lines = current_remarks.split('\n')
            updated_remarks = "\n".join(remark_lines[-5:] + [new_title_line])
            if 'Custom' not in conf: conf['Custom'] = {}
            conf['Custom']['remarks'] = updated_remarks.strip()
            conf.write()
            self.log(f"已更新主播 {douyin_id} 的备注（标题）。", "INFO")
            card.remarks_label.configure(text=f"备注: {updated_remarks.strip()}")
        except Exception as e:
            self.log(f"更新备注失败: {e}", "ERROR")

    def on_closing(self):
        if self.running_processes and messagebox.askyesno("退出确认", f"还有 {len(self.running_processes)} 个直播正在运行，确定要全部停止并退出吗？"):
            for douyin_id in list(self.running_processes.keys()): self.stop_streamer(douyin_id)
            time.sleep(1) # Give processes a moment to terminate
        self.destroy()

    def edit_settings(self, profile_path):
        EditSettingsWindow(self, profile_path)

    def create_new_streamer(self):
        dialog = ctk.CTkInputDialog(text="请输入新的抖音主播ID:", title="新建直播配置")
        new_id = dialog.get_input()
        if not new_id or not new_id.strip(): self.log("新建操作已取消。", "WARN"); return
        new_id = new_id.strip()
        # ---【路径修正】---
        new_profile_path = os.path.join(PROFILES_DIR, new_id)
        if os.path.exists(new_profile_path): messagebox.showerror("错误", f"主播 '{new_id}' 的设定档已存在！"); return
        if not os.path.exists(BASE_CONFIG_TEMPLATE): messagebox.showerror("错误", f"找不到基础设定模板 '{BASE_CONFIG_TEMPLATE}'！"); return
        try:
            os.makedirs(new_profile_path)
            new_config = ConfigObj(BASE_CONFIG_TEMPLATE, encoding='UTF8', indent_type='  ')
            new_config.filename = os.path.join(new_profile_path, 'config.ini')
            if 'Douyin' not in new_config: new_config['Douyin'] = {}
            new_config['Douyin']['douyin_id'] = new_id
            if 'Custom' not in new_config: new_config['Custom'] = {}
            new_config['Custom']['remarks'] = f"新主播: {new_id}"
            new_config['Custom']['group'] = "默认分组"
            new_config.write()
            self.log(f"已根据模板创建新的设定档: {new_profile_path}")
            self.discover_and_refresh()
        except Exception as e:
            self.log(f"创建新主播时出错: {e}", "ERROR")

    def update_ui_for_process(self, douyin_id, is_running):
        if douyin_id in self.streamer_cards:
            card = self.streamer_cards[douyin_id]
            card.start_button.configure(state="disabled" if is_running else "normal")
            card.stop_button.configure(state="normal" if is_running else "disabled")
            card.settings_button.configure(state="disabled" if is_running else "normal")
            card.delete_button.configure(state="disabled" if is_running else "normal")
            card.group_menu.configure(state="disabled" if is_running else "normal")

    def delete_streamer(self, douyin_id, profile_path):
        dialog = ctk.CTkInputDialog(text=f"您确定要永久删除主播 {douyin_id} 吗？\n这将会删除其整个设定档资料夹，此操作无法复原！\n\n请输入 '{douyin_id}' 来确认：", title="删除确认")
        confirmation = dialog.get_input()
        if confirmation and confirmation.strip() == douyin_id:
            try:
                import shutil
                shutil.rmtree(profile_path)
                self.log(f"主播 {douyin_id} 的设定档资料夹已被成功删除。", "INFO")
                self.refresh_streamer_list()
            except Exception as e:
                self.log(f"删除主播 {douyin_id} 时发生错误: {e}", "ERROR")
        else: self.log(f"已取消删除主播 {douyin_id}。", "WARN")

if __name__ == "__main__":
    try:
        from ctypes import windll
        myappid = 'mycompany.myproduct.subproduct.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except (ImportError, AttributeError): pass
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ManagerApp()
    app.mainloop()
