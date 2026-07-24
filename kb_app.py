#!/usr/bin/env python3
"""
知识库 — Apple Notes 风格桌面应用
Canvas: Notes Cream #FFFBED · Accent: Notes Orange #F09A38
Paper-flat, no card chrome, the canvas IS the paper.
"""
import sys, os, json, threading, sqlite3, subprocess
from pathlib import Path
from datetime import datetime

# 数据目录（用户数据）和代码目录（bundle 内脚本）
DATA_DIR = Path.home() / "Documents" / "knowledge-system"
if getattr(sys, 'frozen', False):
    CODE_DIR = Path(sys._MEIPASS)  # PyInstaller bundle
else:
    CODE_DIR = DATA_DIR

sys.path.insert(0, str(CODE_DIR))
if CODE_DIR != DATA_DIR:
    sys.path.insert(0, str(DATA_DIR))

import customtkinter as ctk
from tkinter import filedialog, messagebox

# ─── Apple Notes Color Tokens ──────────────────────
C = {
    # Canvas
    "cream": "#FFFBED",             # Notes Cream — the paper
    "cream_surface_1": "#FAF6E3",   # Search field, pressed bg
    "cream_surface_2": "#F2EDD6",   # Chip fills
    "divider": "#EDEAD8",           # Hairlines
    # Brand
    "orange": "#F09A38",            # Notes Orange — primary action
    "orange_pressed": "#D87E1F",
    "orange_tint": "#FFF1DD",       # Selected row bg
    "folder_yellow": "#F5D773",     # Folder glyph fill
    # Text
    "ink": "#1C1C1E",              # Primary text
    "slate": "#8E8E93",            # Secondary text
    "mute": "#C7C7CC",             # Tertiary/placeholder
    # Dark mode
    "dark_paper": "#1A1A1A",
    "dark_surface": "#262626",
    "dark_surface_2": "#333333",
    "dark_divider": "#2A2A2A",
    "dark_text": "#F2F2F2",
    # Semantic
    "success": "#34C759",
    "warning": "#FFCC00",
    "danger": "#FF3B30",
}

FONT = {
    "nav": ("SF Pro Display", 28, "bold"),      # 模仿 34pt Heavy 的感觉
    "title": ("SF Pro Display", 22, "bold"),
    "headline": ("SF Pro Text", 20, "bold"),
    "body": ("SF Pro Text", 17),
    "body_bold": ("SF Pro Text", 17, "bold"),
    "caption": ("SF Pro Text", 14),
    "caption_strong": ("SF Pro Text", 14, "bold"),
    "date": ("SF Pro Text", 12),
    "stat": ("SF Pro Display", 44, "bold"),
    "stat_label": ("SF Pro Text", 13),
    "tag": ("SF Pro Text", 14),
    "button": ("SF Pro Text", 17, "bold"),
}

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._auto_init()
        self.title("知识库")
        self.geometry("1100x750")
        self.minsize(860, 560)
        self.configure(fg_color=C["cream"])

        # ── Top nav bar (Notes-style large title) ──
        self.nav_title = "📒  知识库"
        self.nav = ctk.CTkFrame(self, fg_color=C["cream"], corner_radius=0, height=56)
        self.nav.pack(fill="x", padx=20, pady=(12, 0))

        ctk.CTkLabel(self.nav, text=self.nav_title, font=FONT["nav"],
                    text_color=C["ink"]).pack(side="left")

        # Tag-style nav tabs
        self.nav_btns = {}
        tabs = ctk.CTkFrame(self.nav, fg_color="transparent")
        tabs.pack(side="right")
        for name, cmd in [("概览", self.show_dashboard), ("导入", self.show_import),
                           ("Wiki", self.show_wiki), ("对话", self.show_holo),
                           ("搜索", self.show_rag), ("设置", self.show_settings)]:
            btn = ctk.CTkButton(tabs, text=name, fg_color="transparent",
                               text_color=C["slate"], font=FONT["caption"],
                               hover_color=C["cream_surface_1"], height=32, width=56,
                               corner_radius=16, command=cmd)
            btn.pack(side="left", padx=1)
            self.nav_btns[name] = btn

        # ── Divider ──
        self.div = ctk.CTkFrame(self, height=1, fg_color=C["divider"], corner_radius=0)
        self.div.pack(fill="x", padx=20, pady=(4, 0))

        # ── Main (paper canvas) ──
        self.main = ctk.CTkFrame(self, fg_color=C["cream"], corner_radius=0)
        self.main.pack(side="right", fill="both", expand=True)

        # 检查组件安装状态
        if not self._all_components_ready():
            self.show_installer()
        else:
            self.show_dashboard()

    def _all_components_ready(self):
        """检查所有组件是否已安装"""
        return all(self._check_component(c) for c in self._get_components())

    def _get_components(self):
        return [
            {"id": "core", "name": "核心引擎", "desc": "数据清理器 + 文件处理器",
             "check": lambda: all((DATA_DIR/d).exists() for d in ["cleaner/format_check.py","processors/docx_processor.py","pipeline.py"])},
            {"id": "holo", "name": "Holographic 对话记忆", "desc": "对话归档 + 语义搜索",
             "check": lambda: (DATA_DIR/"holographic"/"search.py").exists()},
            {"id": "rag", "name": "RAG 知识检索", "desc": "文档向量化 + 语义搜索",
             "check": lambda: (DATA_DIR/"rag_search.py").exists()},
            {"id": "wiki", "name": "LLM Wiki", "desc": "结构化知识库",
             "check": lambda: (DATA_DIR/"wiki"/"SCHEMA.md").exists()},
            {"id": "pageindex", "name": "PageIndex", "desc": "代码符号索引",
             "check": lambda: (DATA_DIR/"pageindex"/"pageindex.py").exists()},
        ]

    def _check_component(self, comp):
        try: return comp["check"]()
        except: return False

    def show_installer(self):
        """安装向导"""
        self._clear()

        # 顶部标题区（固定）
        top = ctk.CTkFrame(self.main, fg_color="transparent")
        top.pack(fill="x", padx=48, pady=(40, 12))
        ctk.CTkLabel(top, text="📦  组件安装向导", font=FONT["nav"],
                    text_color=C["ink"]).pack(anchor="w")
        ctk.CTkLabel(top, text="勾选需要安装的组件，核心引擎为必选",
                    font=FONT["body"], text_color=C["slate"]).pack(anchor="w")

        # 可滚动组件列表
        scroll = ctk.CTkScrollableFrame(self.main, fg_color="transparent", height=280)
        scroll.pack(fill="both", expand=True, padx=48)

        self.install_vars = {}
        for comp in self._get_components():
            installed = self._check_component(comp)
            row = ctk.CTkFrame(scroll, fg_color=C["cream_surface_1"], corner_radius=12)
            row.pack(fill="x", pady=2)

            var = ctk.BooleanVar(value=not installed or comp["id"] == "core")
            cb = ctk.CTkCheckBox(row, text="", variable=var, width=20,
                                fg_color=C["orange"], hover_color=C["orange_pressed"])
            if comp["id"] == "core" or installed:
                cb.configure(state="disabled")
            cb.pack(side="left", padx=(12, 0), pady=10)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=8, pady=6)
            status = "✅ 已安装" if installed else ("🔒 必选" if comp["id"] == "core" else "☐ 勾选安装")
            ctk.CTkLabel(info, text=f"{comp['name']}  {status}", font=FONT["body_bold"],
                        text_color=C["ink"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=comp["desc"], font=FONT["caption"],
                        text_color=C["slate"], anchor="w").pack(anchor="w")

            self.install_vars[comp["id"]] = var

        # 底部按钮区（固定）
        self.install_log = ctk.CTkTextbox(self.main, height=100, fg_color=C["cream_surface_1"],
                                          text_color=C["ink"], font=("Menlo", 11),
                                          border_width=0, corner_radius=10)
        self.install_log.pack(fill="x", padx=48, pady=(8, 4))

        bar = ctk.CTkFrame(self.main, fg_color="transparent", height=50)
        bar.pack(fill="x", padx=48, pady=(0, 16))
        bar.pack_propagate(False)
        PillButton(bar, "🚀  开始安装", True, command=self._do_install).pack(side="left", padx=4)
        PillButton(bar, "跳过", False, command=self.show_dashboard).pack(side="left", padx=4)

    def _do_install(self):
        self.install_log.delete("1.0", "end")
        self.install_log.insert("end", "📦 开始安装...\n\n")

        to_install = [c for c in self._get_components()
                     if self.install_vars.get(c["id"], ctk.BooleanVar(value=False)).get()]

        for comp in to_install:
            if self._check_component(comp):
                self.install_log.insert("end", f"  ⏭ {comp['name']}: 已安装\n")
                # Holographic: 即使已安装也尝试注册 cron
                if comp["id"] == "holo":
                    self._register_holographic_cron()
                continue

            self.install_log.insert("end", f"  ⏳ {comp['name']}: 安装中...\n")
            self.install_log.see("end")
            self.update()

            success, msg = self._install_component(comp["id"])

            if success:
                self.install_log.insert("end", f"  ✅ {comp['name']}: 完成\n")
            else:
                self.install_log.insert("end", f"  ❌ {comp['name']}: {msg}\n")
            self.install_log.see("end")
            self.update()

        self.install_log.insert("end", "\n✅ 安装完成！\n")
        self.after(1500, self.show_dashboard)

    def _install_component(self, comp_id):
        """安装指定组件（从 App bundle 复制脚本）"""
        import shutil, subprocess

        # PyInstaller bundle 中的数据文件位置
        if getattr(sys, 'frozen', False):
            bundle_dir = Path(sys._MEIPASS)
        else:
            bundle_dir = DATA_DIR

        try:
            if comp_id == "core":
                # 先装 Python 依赖
                self.install_log.insert("end", "  📦 安装 Python 依赖包...\n")
                self.install_log.see("end"); self.update()
                import subprocess
                venv_python = str(Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3")
                r = subprocess.run(
                    [venv_python, "-m", "pip", "install", "--quiet",
                     "qdrant-client", "python-docx", "openpyxl", "python-pptx",
                     "pymupdf", "Pillow", "watchdog", "pyyaml", "customtkinter"],
                    capture_output=True, text=True, timeout=120
                )
                if r.returncode == 0:
                    self.install_log.insert("end", "  ✅ 依赖包安装完成\n")
                else:
                    self.install_log.insert("end", f"  ⚠️ 部分包安装失败，功能可能受限\n")

                src = bundle_dir
                for f in ["pipeline.py", "rag_index.py", "rag_search.py", "wiki_ingest.py", "wiki_auto.py", "health_check.py"]:
                    s = src / f
                    if s.exists(): shutil.copy2(s, DATA_DIR / f)
                for d in ["cleaner", "processors"]:
                    sd = src / d
                    if sd.exists():
                        if (DATA_DIR / d).exists(): shutil.rmtree(DATA_DIR / d)
                        shutil.copytree(sd, DATA_DIR / d)
                for d in ["vault","quarantine","processed/text","processed/images",
                         "processed/vision","processed/speech","processed/merged","logs"]:
                    (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
                # 安装 config.yaml
                cf = src / "config.yaml"
                if cf.exists() and not (DATA_DIR / "config.yaml").exists():
                    shutil.copy2(cf, DATA_DIR / "config.yaml")
                return True, ""

            elif comp_id == "holo":
                sd = bundle_dir / "holographic"
                if sd.exists():
                    if (DATA_DIR / "holographic").exists(): shutil.rmtree(DATA_DIR / "holographic")
                    shutil.copytree(sd, DATA_DIR / "holographic")
                    (DATA_DIR / "holographic" / "qdrant_data").mkdir(parents=True, exist_ok=True)
                    (DATA_DIR / "holographic" / "conversations").mkdir(parents=True, exist_ok=True)
                # cron wrapper
                script_dir = Path.home() / ".hermes" / "scripts"
                script_dir.mkdir(parents=True, exist_ok=True)
                wrapper = script_dir / "holographic-archive.sh"
                wrapper.write_text("#!/bin/bash\n~/.hermes/hermes-agent/venv/bin/python3 ~/Documents/knowledge-system/holographic/session_archiver.py\n")
                wrapper.chmod(0o755)

                # 尝试自动注册 cron job（写入 Hermes cron 配置）
                self._register_holographic_cron()

                return True, ""

            elif comp_id == "rag":
                (DATA_DIR / "rag" / "qdrant_data").mkdir(parents=True, exist_ok=True)
                return True, ""

            elif comp_id == "wiki":
                for d in ["wiki/raw/articles","wiki/entities","wiki/concepts",
                         "wiki/comparisons","wiki/queries","wiki/_archive"]:
                    (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
                for f in ["wiki/SCHEMA.md","wiki/index.md","wiki/log.md"]:
                    s = bundle_dir / f
                    if s.exists() and not (DATA_DIR / f).exists():
                        shutil.copy2(s, DATA_DIR / f)
                return True, ""

            elif comp_id == "pageindex":
                sd = bundle_dir / "pageindex"
                if sd.exists():
                    if (DATA_DIR / "pageindex").exists(): shutil.rmtree(DATA_DIR / "pageindex")
                    shutil.copytree(sd, DATA_DIR / "pageindex")
                return True, ""

            return True, ""
        except Exception as e:
            return False, str(e)[:200]

    def _register_holographic_cron(self):
        """注册 Holographic 定时归档任务（通过 hermes CLI）"""
        import subprocess
        try:
            r = subprocess.run(
                ["hermes", "cron", "create", "--script", "holographic-archive.sh",
                 "--schedule", "*/30 * * * *", "--name", "Holographic 对话归档",
                 "--no-agent"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                self.install_log.insert("end", "  ✅ 定时归档任务已注册 (每30分钟)\n")
            else:
                raise Exception(r.stderr or "未知错误")
        except FileNotFoundError:
            self.install_log.insert("end", "  ⚠️ hermes CLI 不可用\n")
            self.install_log.insert("end", "     请在 Hermes 对话中输入: /cron add --script holographic-archive.sh --schedule '*/30 * * * *' --name 'Holographic 对话归档' --no-agent\n")
        except Exception as e:
            self.install_log.insert("end", f"  ⚠️ 自动注册失败: {e}\n")
            self.install_log.insert("end", "     请在 Hermes 对话中输入: /cron add --script holographic-archive.sh --schedule '*/30 * * * *' --name 'Holographic 对话归档' --no-agent\n")

    @staticmethod
    def get_api_keys():
        """从 Hermes 配置/环境变量读取所有 API Key，返回 {provider: key}"""
        import yaml, os, json
        keys = {}
        # 1. 环境变量
        for env_var in ["DEEPSEEK_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
            key = os.environ.get(env_var, "")
            if key:
                provider = env_var.replace("_API_KEY", "").lower()
                keys[provider] = key
        # 2. config.yaml
        config_path = Path.home() / ".hermes" / "config.yaml"
        if config_path.exists():
            cfg = yaml.safe_load(config_path.read_text())
            aux_key = cfg.get("auxiliary", {}).get("vision", {}).get("api_key", "")
            if aux_key: keys["dashscope"] = aux_key
            for pid, p in cfg.get("providers", {}).items():
                k = p.get("api_key", "") or p.get("key", "")
                if k: keys[pid] = k
        # 3. auth.json
        auth_path = Path.home() / ".hermes" / "auth.json"
        if auth_path.exists():
            auth = json.loads(auth_path.read_text())
            for provider, creds in auth.get("credential_pool", {}).items():
                for c in creds:
                    src = c.get("source", "")
                    if src.startswith("env:"):
                        env_name = src[4:]
                        key = os.environ.get(env_name, "")
                        if key: keys[provider] = key
        # 4. ~/.hermes/.env 文件
        env_path = Path.home() / ".hermes" / ".env"
        if env_path.exists():
            for line in env_path.read_text().split("\n"):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k.endswith("_API_KEY") and v:
                        provider = k.replace("_API_KEY", "").lower()
                        keys[provider] = v
        return keys

    @staticmethod
    def get_api_key(prefer="dashscope"):
        """获取单个 API Key，优先指定 provider"""
        keys = App.get_api_keys()
        # 优先匹配
        for k, v in keys.items():
            if prefer in k.lower(): return v
        # 返回第一个
        return next(iter(keys.values()), None) if keys else None

    def _auto_init(self):
        """首次启动自动创建目录和数据库"""
        dirs = [DATA_DIR, DATA_DIR/"cleaner", DATA_DIR/"processors",
                DATA_DIR/"vault", DATA_DIR/"quarantine",
                DATA_DIR/"processed"/"text", DATA_DIR/"processed"/"images",
                DATA_DIR/"rag"/"qdrant_data", DATA_DIR/"logs",
                DATA_DIR/"wiki"/"raw"/"articles", DATA_DIR/"wiki"/"entities",
                DATA_DIR/"wiki"/"concepts",
                DATA_DIR/"pageindex", DATA_DIR/"holographic"/"conversations",
                DATA_DIR/"holographic"/"qdrant_data"]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        try:
            from cleaner.state import init_db; init_db()
        except: pass

    def _set_nav(self, active):
        for n, b in self.nav_btns.items():
            if n == active:
                b.configure(fg_color=C["orange_tint"], text_color=C["orange"])
            else:
                b.configure(fg_color="transparent", text_color=C["slate"])

    def _clear(self):
        for w in self.main.winfo_children():
            w.destroy()

    def _db(self, sql, db=None):
        db = db or str(DATA_DIR / "state.db")
        try:
            c = sqlite3.connect(db); r = c.execute(sql).fetchall(); c.close(); return r
        except: return []

    # ═══════════ 概览 ═══════════
    def show_dashboard(self):
        self._clear(); self._set_nav("概览")

        # Stats row
        holo_n = rag_n = 0
        try:
            from qdrant_client import QdrantClient
            r = QdrantClient(path=str(DATA_DIR / "rag" / "qdrant_data"))
            try:
                rp, _ = r.scroll("rag_knowledge", limit=2000)
                rag_n = len(rp)
            except: pass
        except: pass
        try:
            from qdrant_client import QdrantClient
            h = QdrantClient(path=str(DATA_DIR / "holographic" / "qdrant_data"))
            try:
                hp, _ = h.scroll("holographic_conversations", limit=2000)
                holo_n = len(hp)
            except: pass
        except: pass

        state_n = len(self._db("SELECT 1 FROM files"))
        wiki_n = 0
        if (DATA_DIR / "wiki" / "index.md").exists():
            wiki_n = len([l for l in (DATA_DIR / "wiki" / "index.md").read_text().split("\n") if l.startswith("- [")])

        grid = ctk.CTkFrame(self.main, fg_color="transparent")
        grid.pack(padx=32, pady=(32, 20))
        grid.columnconfigure((0, 1, 2, 3), weight=1)

        for i, (label, val, color) in enumerate([
            ("文档", str(state_n), C["orange"]),
            ("向量", str(rag_n), C["success"]),
            ("对话", str(holo_n), C["warning"]),
            ("Wiki", str(wiki_n), C["ink"]),
        ]):
            card = ctk.CTkFrame(grid, fg_color=C["cream_surface_1"], corner_radius=12)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            ctk.CTkLabel(card, text=val, font=FONT["stat"], text_color=color).pack(pady=(20, 0))
            ctk.CTkLabel(card, text=label, font=FONT["stat_label"], text_color=C["slate"]).pack(pady=(2, 16))

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.pack(fill="x", padx=36, pady=(8, 4))
        ctk.CTkLabel(header, text="处理进度", font=FONT["caption_strong"],
                    text_color=C["slate"]).pack(side="left")

        # 处理进度条 + 状态分解
        statuses = self._db("SELECT status, COUNT(*) FROM files GROUP BY status")
        status_map = dict(statuses) if statuses else {}
        total = sum(status_map.values()) if status_map else 0

        if total > 0:
            indexed = status_map.get("indexed", 0)
            ready = status_map.get("ready_for_wiki", 0)
            done = indexed + ready
            validated = status_map.get("validated", 0)
            pct = int(done / total * 100) if total else 0

            bar_frame = ctk.CTkFrame(self.main, fg_color="transparent")
            bar_frame.pack(fill="x", padx=36, pady=(0, 4))
            bar_bg = ctk.CTkFrame(bar_frame, fg_color=C["cream_surface_1"], height=8, corner_radius=4)
            bar_bg.pack(fill="x")
            bar_fg = ctk.CTkFrame(bar_bg, fg_color=C["orange"], height=8, corner_radius=4,
                                   width=max(pct * 3, 10))
            bar_fg.pack(side="left")

            status_row = ctk.CTkFrame(self.main, fg_color="transparent")
            status_row.pack(fill="x", padx=36, pady=(0, 8))
            for label, count, color in [
                (f"✅ 完成 {done}", done, C["success"]),
                (f"⏳ 进行中 {validated}", validated, C["warning"]),
                (f"📦 总计 {total}", total, C["slate"]),
            ]:
                ctk.CTkLabel(status_row, text=label, font=FONT["caption"],
                            text_color=color).pack(side="left", padx=(0, 20))
        else:
            ctk.CTkLabel(self.main, text="暂无文件，导入文档后这里会显示处理进度",
                        font=FONT["caption"], text_color=C["mute"]).pack(padx=36, pady=(0, 12))

        # Note-style activity list
        act_header = ctk.CTkFrame(self.main, fg_color="transparent")
        act_header.pack(fill="x", padx=36, pady=(8, 4))
        ctk.CTkLabel(act_header, text="最近导入", font=FONT["caption_strong"],
                    text_color=C["slate"]).pack(side="left")

        activity = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        activity.pack(fill="both", expand=True, padx=20)

        rows = self._db("SELECT original_name, file_type, created_at FROM files ORDER BY created_at DESC LIMIT 20")
        for name, ftype, ts in rows:
            row = ctk.CTkFrame(activity, fg_color="transparent", height=52)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)
            icon_map = {"docx": "📄", "xlsx": "📊", "pptx": "📽", "pdf": "📕", "text": "📝",
                       "md": "📝", "image": "🖼", "code": "💻"}
            icon = icon_map.get(ftype, "📎")
            ctk.CTkLabel(row, text=f"{icon}  {name}", font=FONT["body"],
                        text_color=C["ink"], anchor="w").pack(side="left", padx=16, fill="x", expand=True)
            ctk.CTkLabel(row, text=ts[:16], font=FONT["date"],
                        text_color=C["slate"]).pack(side="right", padx=16)
            # subtle divider
            div = ctk.CTkFrame(activity, height=0.5, fg_color=C["divider"])
            div.pack(fill="x", padx=16)

        # FAB-style import button
        PillButton(self.main, "📝  导入文档", command=self.show_import).pack(side="bottom", anchor="e", padx=20, pady=20)

    # ═══════════ 导入 ═══════════
    def show_import(self):
        self._clear(); self._set_nav("导入")

        ctk.CTkLabel(self.main, text="导入文档", font=FONT["nav"],
                    text_color=C["ink"]).pack(anchor="w", padx=32, pady=(24, 4))
        ctk.CTkLabel(self.main, text="Word · Excel · PPT · PDF · 图片 · 音视频 · 思维导图 · Visio · 文本 · 代码",
                    font=FONT["caption"], text_color=C["slate"]).pack(anchor="w", padx=32, pady=(0, 20))

        entry_style = {"fg_color": C["cream_surface_1"], "border_color": C["divider"],
                       "border_width": 1, "height": 44, "corner_radius": 10,
                       "font": FONT["body"], "text_color": C["ink"]}

        fr = ctk.CTkFrame(self.main, fg_color="transparent")
        fr.pack(fill="x", padx=32)
        self.imp_file = ctk.CTkEntry(fr, placeholder_text="选择文件...", **entry_style)
        self.imp_file.pack(side="left", fill="x", expand=True, padx=(0, 8))
        PillButton(fr, "浏览", primary=False, command=self._pick_file, height=44, width=70).pack(side="left")

        dr = ctk.CTkFrame(self.main, fg_color="transparent")
        dr.pack(fill="x", padx=32, pady=(8, 0))
        self.imp_dir = ctk.CTkEntry(dr, placeholder_text="选择目录...", **entry_style)
        self.imp_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        PillButton(dr, "浏览", primary=False, command=self._pick_dir, height=44, width=70).pack(side="left")

        PillButton(self.main, "开始导入", command=self._do_import).pack(anchor="w", padx=32, pady=(16, 0))

        self.imp_log = ctk.CTkTextbox(self.main, height=200, fg_color=C["cream_surface_1"],
                                      text_color=C["ink"], font=("Menlo", 11),
                                      border_width=0, corner_radius=10)
        self.imp_log.pack(fill="both", expand=True, padx=32, pady=(16, 24))
        for name, ts in self._db("SELECT original_name, created_at FROM files ORDER BY created_at DESC LIMIT 12"):
            self.imp_log.insert("end", f"  [{ts[:16]}]  {name}\n")

    def _pick_file(self):
        f = filedialog.askopenfilename()
        if f: self.imp_file.delete(0, "end"); self.imp_file.insert(0, f)

    def _pick_dir(self):
        d = filedialog.askdirectory()
        if d: self.imp_dir.delete(0, "end"); self.imp_dir.insert(0, d)

    def _do_import(self):
        t = self.imp_file.get() or self.imp_dir.get()
        if not t: return
        self.imp_log.insert("end", f"\n  ⏳ {t}...\n"); self.imp_log.see("end")
        threading.Thread(target=lambda: self._imp_thread(t), daemon=True).start()

    def _imp_thread(self, t):
        try:
            v = str(Path.home()/".hermes"/"hermes-agent"/"venv"/"bin"/"python3")
            r = subprocess.run([v, str(DATA_DIR/"pipeline.py"), t],
                              capture_output=True, text=True, timeout=300, cwd=str(DATA_DIR))
            o = r.stdout[-2000:] if r.stdout else r.stderr[-2000:]
            self.after(0, lambda: self.imp_log.insert("end", o))

            # 自动处理 Wiki raw → 结构化页面
            wiki_raw = DATA_DIR / "wiki" / "raw" / "articles"
            if wiki_raw.exists() and list(wiki_raw.glob("*.md")):
                self.after(0, lambda: self.imp_log.insert("end", "\n📖 生成 Wiki 知识页面...\n"))
                r2 = subprocess.run([v, str(DATA_DIR/"wiki_auto.py")],
                                   capture_output=True, text=True, timeout=120, cwd=str(DATA_DIR))
                self.after(0, lambda: self.imp_log.insert("end", r2.stdout[-1000:] if r2.stdout else r2.stderr[-500:]))

            self.after(0, lambda: self.imp_log.see("end"))
        except Exception as e:
            self.after(0, lambda: self.imp_log.insert("end", f"  ❌ {e}\n"))

    # ═══════════ Wiki ═══════════
    def show_wiki(self):
        self._clear(); self._set_nav("Wiki")
        ctk.CTkLabel(self.main, text="Wiki 知识", font=FONT["nav"],
                    text_color=C["ink"]).pack(anchor="w", padx=32, pady=(24, 16))

        paned = ctk.CTkFrame(self.main, fg_color="transparent")
        paned.pack(fill="both", expand=True, padx=20)

        # 页面列表 (folder-style)
        left = ctk.CTkFrame(paned, fg_color="transparent", width=200)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        self.wl = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.wl.pack(fill="both", expand=True)
        self.wp = {}

        # 结构化页面
        has_pages = False
        for d, label in [("entities", "实体"), ("concepts", "概念")]:
            p = DATA_DIR / "wiki" / d
            if p.exists():
                files = sorted(p.glob("*.md"))
                if files:
                    has_pages = True
                    ctk.CTkLabel(self.wl, text=label, font=FONT["caption_strong"],
                                text_color=C["slate"]).pack(anchor="w", padx=12, pady=(12, 4))
                    for f in files:
                        n = f.stem; self.wp[n] = str(f)
                        ctk.CTkButton(self.wl, text=n, anchor="w", fg_color="transparent",
                                     text_color=C["ink"], font=FONT["body"], height=32,
                                     hover_color=C["cream_surface_1"], corner_radius=10,
                                     command=lambda nn=n: self._load_wiki(nn)).pack(fill="x")

        # Raw 文件（待处理的导入来源）
        raw_dir = DATA_DIR / "wiki" / "raw" / "articles"
        if raw_dir.exists():
            raws = sorted(raw_dir.glob("*.md"))
            if raws:
                ctk.CTkLabel(self.wl, text="待处理", font=FONT["caption_strong"],
                            text_color=C["warning"]).pack(anchor="w", padx=12, pady=(16, 4))
                for f in raws:
                    n = f"📄 {f.stem[:30]}"
                    self.wp[n] = str(f)
                    ctk.CTkButton(self.wl, text=n, anchor="w", fg_color="transparent",
                                 text_color=C["slate"], font=FONT["caption"], height=28,
                                 hover_color=C["cream_surface_1"], corner_radius=10,
                                 command=lambda nn=n: self._load_wiki(nn)).pack(fill="x")

        if not has_pages and not raws:
            ctk.CTkLabel(self.wl, text="暂无页面\n导入文档后自动生成",
                        font=FONT["body"], text_color=C["mute"]).pack(pady=20)

        # 编辑器 (note-style)
        right = ctk.CTkFrame(paned, fg_color=C["cream_surface_1"], corner_radius=12)
        right.pack(side="right", fill="both", expand=True)

        self.wt = ctk.CTkLabel(right, text="选择页面", font=FONT["headline"], text_color=C["ink"])
        self.wt.pack(anchor="w", padx=18, pady=(14, 6))

        self.we = ctk.CTkTextbox(right, fg_color=C["cream_surface_1"], text_color=C["ink"],
                                 font=("Menlo", 12), border_width=0, corner_radius=10)
        self.we.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=8, pady=(0, 8))
        PillButton(bar, "保存", command=self._save_wiki).pack(side="left", padx=3)
        ctk.CTkButton(bar, text="删除", fg_color=C["danger"], corner_radius=999,
                      font=FONT["caption"], height=36, command=self._del_wiki).pack(side="left", padx=3)
        self._wfile = None

    def _load_wiki(self, name):
        self._wfile = self.wp.get(name)
        self.wt.configure(text=name)
        self.we.delete("1.0", "end")
        self.we.insert("1.0", Path(self._wfile).read_text(encoding="utf-8"))

    def _save_wiki(self):
        if not self._wfile: return
        Path(self._wfile).write_text(self.we.get("1.0", "end-1c"), encoding="utf-8")
        messagebox.showinfo("已保存", "✅")

    def _del_wiki(self):
        if not self._wfile: return
        if messagebox.askyesno("确认", "删除此页面？"):
            Path(self._wfile).unlink(); self.we.delete("1.0", "end"); self._wfile = None
            self.wt.configure(text="已删除")

    # ═══════════ 对话 ═══════════
    def show_holo(self):
        self._clear(); self._set_nav("对话")
        ctk.CTkLabel(self.main, text="对话记忆", font=FONT["nav"],
                    text_color=C["ink"]).pack(anchor="w", padx=32, pady=(24, 16))

        sr = ctk.CTkFrame(self.main, fg_color="transparent")
        sr.pack(fill="x", padx=32)
        es = {"fg_color": C["cream_surface_1"], "border_color": C["divider"], "border_width": 1,
              "height": 44, "corner_radius": 10, "font": FONT["body"], "text_color": C["ink"]}
        self.hq = ctk.CTkEntry(sr, placeholder_text="搜索对话...", **es)
        self.hq.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.hq.bind("<Return>", lambda e: self._h_search())
        PillButton(sr, "搜索", command=self._h_search).pack(side="left")

        self.hr = ctk.CTkTextbox(self.main, fg_color=C["cream_surface_1"], text_color=C["ink"],
                                 font=("Menlo", 12), border_width=0, corner_radius=10)
        self.hr.pack(fill="both", expand=True, padx=32, pady=(16, 24))

    def _h_search(self):
        q = self.hq.get()
        if not q: return
        self.hr.delete("1.0", "end"); self.hr.insert("end", f"🔍 {q}\n\n")
        try:
            import yaml; from qdrant_client import QdrantClient; from openai import OpenAI
            keys = self.get_api_keys()
            key = keys.get("dashscope") or keys.get("deepseek")
            if not key:
                self.hr.insert("end", "❌ 未找到 API Key，请在设置中配置\n")
                return
            cl = OpenAI(api_key=key,
                       base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
            e = cl.embeddings.create(model="text-embedding-v3", input=[q])
            qd = QdrantClient(path=str(DATA_DIR/"holographic"/"qdrant_data"))
            pts = qd.query_points("holographic_conversations", query=e.data[0].embedding, limit=10)
            for h in pts.points:
                p = h.payload
                self.hr.insert("end", f"[{p.get('date','?')}]  {p.get('session_title','')}\n")
                self.hr.insert("end", f"{p.get('text_preview','')[:300]}\n\n")
                self.hr.insert("end", "─"*50+"\n")
            self.hr.see("end")
        except Exception as e:
            self.hr.insert("end", f"❌ {str(e)[:200]}\n")

    # ═══════════ 搜索 ═══════════
    def show_rag(self):
        self._clear(); self._set_nav("搜索")
        ctk.CTkLabel(self.main, text="知识搜索", font=FONT["nav"],
                    text_color=C["ink"]).pack(anchor="w", padx=32, pady=(24, 16))

        sr = ctk.CTkFrame(self.main, fg_color="transparent")
        sr.pack(fill="x", padx=32)
        es = {"fg_color": C["cream_surface_1"], "border_color": C["divider"], "border_width": 1,
              "height": 44, "corner_radius": 10, "font": FONT["body"], "text_color": C["ink"]}
        self.rq = ctk.CTkEntry(sr, placeholder_text="搜索知识库...", **es)
        self.rq.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.rq.bind("<Return>", lambda e: self._r_search())
        PillButton(sr, "搜索", command=self._r_search).pack(side="left")

        self.rr = ctk.CTkTextbox(self.main, fg_color=C["cream_surface_1"], text_color=C["ink"],
                                 font=("Menlo", 12), border_width=0, corner_radius=10)
        self.rr.pack(fill="both", expand=True, padx=32, pady=(16, 24))

    def _r_search(self):
        q = self.rq.get()
        if not q: return
        self.rr.delete("1.0", "end"); self.rr.insert("end", f"🔍 {q}\n\n")
        try:
            import yaml; from qdrant_client import QdrantClient; from openai import OpenAI
            keys = self.get_api_keys()
            key = keys.get("dashscope") or keys.get("deepseek")
            if not key:
                self.rr.insert("end", "❌ 未找到 API Key，请在设置中配置\n")
                return
            cl = OpenAI(api_key=key,
                       base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
            e = cl.embeddings.create(model="text-embedding-v3", input=[q])
            qd = QdrantClient(path=str(DATA_DIR/"rag"/"qdrant_data"))
            pts = qd.query_points("rag_knowledge", query=e.data[0].embedding, limit=8)
            for h in pts.points:
                p = h.payload
                self.rr.insert("end", f"[{p.get('file_type','?')}]  {p.get('title','')}\n")
                self.rr.insert("end", f"{p.get('text','')[:300]}\n\n")
                self.rr.insert("end", "─"*50+"\n")
            self.rr.see("end")
        except Exception as e:
            self.rr.insert("end", f"❌ {str(e)[:200]}\n")
    # ═══════════ 设置 ═══════════
    def show_settings(self):
        self._clear(); self._set_nav("设置")

        scroll = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll, text="设置", font=FONT["nav"],
                    text_color=C["ink"]).pack(anchor="w", padx=32, pady=(24, 16))

        # ── API 配置 ──
        ctk.CTkLabel(scroll, text="API 配置", font=FONT["caption_strong"],
                    text_color=C["slate"]).pack(anchor="w", padx=32)
        ctk.CTkLabel(scroll, text="DashScope 统一 API Key（视觉识别 / 语音转写 / 向量嵌入）",
                    font=FONT["caption"], text_color=C["mute"]).pack(anchor="w", padx=32, pady=(2, 8))

        # 读取当前配置
        try:
            import yaml; cp = DATA_DIR / "config.yaml"
            cfg = yaml.safe_load(cp.read_text()) if cp.exists() else {}
        except: cfg = {}

        api_key = cfg.get("auxiliary", {}).get("vision", {}).get("api_key", "")
        vision_model = cfg.get("auxiliary", {}).get("vision", {}).get("model", "qwen-vl-max")
        asr_model = cfg.get("processors", {}).get("audio", {}).get("model", "fun-asr-flash-2026-06-15")

        # DashScope API Key
        row1 = ctk.CTkFrame(scroll, fg_color="transparent")
        row1.pack(fill="x", padx=32, pady=4)
        ctk.CTkLabel(row1, text="API Key", font=FONT["body"], text_color=C["ink"], width=100, anchor="w").pack(side="left")
        self.api_key_var = ctk.StringVar(value=api_key)
        self.api_key_entry = ctk.CTkEntry(row1, textvariable=self.api_key_var, show="•",
                                          fg_color=C["cream_surface_1"], border_color=C["divider"],
                                          border_width=1, height=36, corner_radius=10,
                                          font=FONT["body"], text_color=C["ink"])
        self.api_key_entry.pack(side="left", fill="x", expand=True)

        # 视觉模型
        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", padx=32, pady=4)
        ctk.CTkLabel(row2, text="视觉模型", font=FONT["body"], text_color=C["ink"], width=100, anchor="w").pack(side="left")
        self.vision_model_var = ctk.StringVar(value=vision_model)
        self.vision_combo = ctk.CTkComboBox(row2, values=["qwen-vl-max", "qwen3-vl-flash", "qwen2.5-vl-72b-instruct"],
                                           variable=self.vision_model_var, width=200,
                                           fg_color=C["cream_surface_1"], border_color=C["divider"],
                                           font=FONT["body"], text_color=C["ink"])
        self.vision_combo.pack(side="left")

        # 语音模型
        row3 = ctk.CTkFrame(scroll, fg_color="transparent")
        row3.pack(fill="x", padx=32, pady=4)
        ctk.CTkLabel(row3, text="语音模型", font=FONT["body"], text_color=C["ink"], width=100, anchor="w").pack(side="left")
        self.asr_model_var = ctk.StringVar(value=asr_model)
        ctk.CTkEntry(row3, textvariable=self.asr_model_var, width=280,
                    fg_color=C["cream_surface_1"], border_color=C["divider"],
                    border_width=1, height=36, corner_radius=10,
                    font=FONT["body"], text_color=C["ink"]).pack(side="left")

        PillButton(scroll, "💾 保存 API 配置", command=self._save_api).pack(anchor="w", padx=32, pady=(12, 24))

        # ── 分隔 ──
        ctk.CTkFrame(scroll, height=1, fg_color=C["divider"]).pack(fill="x", padx=32, pady=(0, 20))

        # ── 监听目录 ──
        ctk.CTkLabel(scroll, text="监听目录", font=FONT["caption_strong"],
                    text_color=C["slate"]).pack(anchor="w", padx=32)
        ctk.CTkLabel(scroll, text="新文件自动导入", font=FONT["caption"],
                    text_color=C["mute"]).pack(anchor="w", padx=32, pady=(2, 10))

        wd = cfg.get("watch_dirs", [])
        for d in wd:
            row = ctk.CTkFrame(scroll, fg_color="transparent", height=36)
            row.pack(fill="x", padx=28, pady=1)
            ctk.CTkLabel(row, text=str(Path(d).expanduser()), font=FONT["body"],
                        text_color=C["ink"], anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="✕", width=28, fg_color="transparent",
                         text_color=C["slate"], hover_color=C["cream_surface_2"],
                         font=FONT["caption"], command=lambda dd=d: self._rm_watch(dd)).pack(side="right")
            ctk.CTkFrame(scroll, height=0.5, fg_color=C["divider"]).pack(fill="x", padx=32)

        ctk.CTkButton(scroll, text="+  添加目录", command=self._add_watch,
                      height=36, corner_radius=16, font=FONT["caption"],
                      fg_color=C["cream_surface_1"], text_color=C["orange"],
                      hover_color=C["orange_tint"]).pack(anchor="w", padx=32, pady=10)

    def _save_api(self):
        try:
            import yaml; cp = DATA_DIR / "config.yaml"
            cfg = yaml.safe_load(cp.read_text()) if cp.exists() else {}
            cfg.setdefault("auxiliary", {}).setdefault("vision", {})
            cfg["auxiliary"]["vision"]["api_key"] = self.api_key_var.get()
            cfg["auxiliary"]["vision"]["model"] = self.vision_model_var.get()
            cfg.setdefault("processors", {}).setdefault("audio", {})
            cfg["processors"]["audio"]["model"] = self.asr_model_var.get()
            cp.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))
            messagebox.showinfo("已保存", "✅ API 配置已更新\n重启 App 后生效")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _add_watch(self):
        d = filedialog.askdirectory()
        if not d: return
        try:
            import yaml; cp = DATA_DIR / "config.yaml"
            cfg = yaml.safe_load(cp.read_text()) if cp.exists() else {}
            cfg.setdefault("watch_dirs", []).append(d)
            cp.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))
            messagebox.showinfo("已添加", "✅")
        except Exception as e: messagebox.showerror("错误", str(e))

    def _rm_watch(self, d):
        try:
            import yaml; cp = DATA_DIR / "config.yaml"
            cfg = yaml.safe_load(cp.read_text())
            cfg["watch_dirs"] = [x for x in cfg.get("watch_dirs",[])
                                if Path(x).expanduser() != Path(d).expanduser()]
            cp.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False))
            messagebox.showinfo("已移除", "✅")
        except Exception as e: messagebox.showerror("错误", str(e))


# ─── Pill Button (Notes Orange style) ──────────────
class PillButton(ctk.CTkButton):
    def __init__(self, parent, text, primary=True, command=None, height=38, **kw):
        bg = C["orange"] if primary else C["cream_surface_1"]
        fg = "#ffffff" if primary else C["orange"]
        hov = C["orange_pressed"] if primary else C["orange_tint"]
        super().__init__(parent, text=text, fg_color=bg, text_color=fg,
                        corner_radius=999, height=height,
                        font=FONT["button"], hover_color=hov,
                        border_width=0 if primary else 1,
                        border_color=C["orange"] if not primary else None,
                        command=command, **kw)


if __name__ == "__main__":
    App().mainloop()
