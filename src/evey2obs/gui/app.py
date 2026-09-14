"""Main application window — settings persistence, wizard, task queue."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import httpx

from evey2obs.config_file import load_settings, save_config
from evey2obs.gui.asyncio_bridge import AsyncioBridge
from evey2obs.gui.constants import (
    COLOR_ACTIVE,
    COLOR_FAILED,
    COLOR_QUEUED,
    COLOR_SUCCESS,
    PLATFORM_LABELS,
    STAGE_LABELS,
    TEMPLATE_LABELS,
)
from evey2obs.inputs import extract_urls
from evey2obs.models import SourceInput, TaskStatus
from evey2obs.security import KeyringStore
from evey2obs.settings import AppSettings, LLMSettings, ObsidianSettings

logger = logging.getLogger(__name__)
POLL_INTERVAL_MS = 150

# ── Helpers ─────────────────────────────────────────────────────────────────

def _open_file(path: str) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", path])


def _labeled_row(parent, label: str, row: int, var: tk.StringVar, **kw) -> tk.Widget:
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
    w = ttk.Entry(parent, textvariable=var, **kw)
    w.grid(row=row, column=1, sticky="ew", pady=4)
    return w


# ── App ──────────────────────────────────────────────────────────────────────


class App(tk.Tk):
    """Main evey2obs desktop application."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        super().__init__()
        self.title("evey2obs — 多源内容笔记工具")
        self.geometry("960x740")
        self.minsize(700, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Style
        style = ttk.Style()
        try:
            style.theme_use("aqua")  # macOS native
        except tk.TclError:
            pass
        style.configure("TLabel", font=("Helvetica Neue", 11))
        style.configure("TButton", font=("Helvetica Neue", 11))
        style.configure("TEntry", font=("Helvetica Neue", 11))
        style.configure("TLabelframe.Label", font=("Helvetica Neue", 12, "bold"))
        style.configure("Header.TLabel", font=("Helvetica Neue", 14, "bold"))

        # Load persisted settings
        self._settings = settings or load_settings()
        self._bridge: AsyncioBridge | None = None

        # Menu
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="待导出草稿箱...", command=self._open_pending_exports)
        file_menu.add_command(label="设置...", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)
        self.config(menu=menubar)

        # Check if configured
        if not self._settings.obsidian.vault_path or not self._settings.llm.api_key:
            self._show_wizard()
        else:
            self._init_bridge()
            self._build_main_view()

    # ── Bridge ────────────────────────────────────────────────────────────

    def _init_bridge(self) -> None:
        if self._bridge:
            self._bridge.shutdown()
        self._bridge = AsyncioBridge(self._settings)

    def _reload_settings(self, new_settings: AppSettings) -> None:
        self._settings = new_settings
        save_config(new_settings)
        self._init_bridge()

    # ══════════════════════════════════════════════════════════════════════
    # WELCOME WIZARD
    # ══════════════════════════════════════════════════════════════════════

    def _show_wizard(self) -> None:
        wizard = tk.Toplevel(self)
        wizard.title("欢迎使用 evey2obs — 首次配置")
        wizard.geometry("560x460")
        wizard.resizable(False, False)
        wizard.transient(self)
        wizard.grab_set()

        notebook = ttk.Notebook(wizard)
        notebook.pack(fill="both", expand=True, padx=15, pady=15)

        # ── Page 1: LLM ──────────────────────────────────────────────────
        llm = ttk.Frame(notebook, padding=20)
        notebook.add(llm, text="1. 大模型")

        ttk.Label(llm, text="配置 AI 总结服务", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        proto_var = tk.StringVar(value=self._settings.llm.protocol or "anthropic")
        ttk.Label(llm, text="协议:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(llm, textvariable=proto_var, values=["anthropic", "openai"],
                     width=22, state="readonly").grid(row=1, column=1, pady=4)

        url_var = tk.StringVar(value=self._settings.llm.base_url)
        _labeled_row(llm, "Base URL:", 2, url_var, width=45)

        key_var = tk.StringVar(value=self._settings.llm.api_key)
        _labeled_row(llm, "API Key:", 3, key_var, width=45, show="*")

        model_var = tk.StringVar(value=self._settings.llm.model)
        _labeled_row(llm, "模型名:", 4, model_var, width=45)

        def _test_llm():
            try:
                async def _do():
                    headers = {"Content-Type": "application/json"}
                    if proto_var.get() == "anthropic":
                        headers["x-api-key"] = key_var.get()
                        headers["anthropic-version"] = "2023-06-01"
                        ep = f"{url_var.get().rstrip('/')}/messages"
                    else:
                        headers["Authorization"] = f"Bearer {key_var.get()}"
                        ep = f"{url_var.get().rstrip('/')}/chat/completions"
                    payload = {"model": model_var.get(), "max_tokens": 5,
                               "messages": [{"role": "user", "content": "ok"}]}
                    async with httpx.AsyncClient(timeout=10) as c:
                        r = await c.post(ep, json=payload, headers=headers)
                        r.raise_for_status()
                asyncio.run(_do())
                messagebox.showinfo("连接成功", "LLM 连接测试通过！", parent=wizard)
            except Exception as e:
                messagebox.showerror("连接失败", str(e)[:200], parent=wizard)

        ttk.Button(llm, text="测试连接", command=_test_llm).grid(
            row=5, column=1, sticky="e", pady=15)

        # ── Page 2: Obsidian ─────────────────────────────────────────────
        obs = ttk.Frame(notebook, padding=20)
        notebook.add(obs, text="2. Obsidian")

        ttk.Label(obs, text="设置笔记输出位置", style="Header.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        vault_var = tk.StringVar(value=self._settings.obsidian.vault_path)
        ttk.Label(obs, text="Vault 路径:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(obs, textvariable=vault_var, width=35).grid(row=1, column=1, pady=4)
        ttk.Button(obs, text="浏览...",
                   command=lambda: vault_var.set(filedialog.askdirectory())
                   ).grid(row=1, column=2, padx=(5, 0), pady=4)

        subdir_var = tk.StringVar(value=self._settings.obsidian.subdir)
        _labeled_row(obs, "子目录:", 2, subdir_var, width=35)

        def _validate():
            p = Path(vault_var.get()).expanduser().resolve()
            if p.is_dir():
                try:
                    (p / ".evey2obs_test").touch()
                    (p / ".evey2obs_test").unlink()
                    messagebox.showinfo("路径有效", f"Vault 可写:\n{p}", parent=wizard)
                except OSError:
                    messagebox.showerror("权限不足", "路径不可写", parent=wizard)
            else:
                messagebox.showerror("路径无效", f"路径不存在:\n{p}", parent=wizard)

        ttk.Button(obs, text="验证路径", command=_validate).grid(
            row=3, column=1, sticky="e", pady=15)

        # ── Page 3: Finish ──────────────────────────────────────────────
        done = ttk.Frame(notebook, padding=20)
        notebook.add(done, text="3. 完成")

        ttk.Label(done, text="配置完成！", font=("Helvetica Neue", 18)).pack(pady=(30, 10))
        ttk.Label(done, text="你可以随时在 文件 → 设置 中修改配置。", font=("Helvetica Neue", 11)).pack(pady=5)
        ttk.Label(done, text="现在开始处理你的第一条内容吧。", font=("Helvetica Neue", 11)).pack(pady=20)

        def _finish():
            new_settings = AppSettings(
                llm=LLMSettings(
                    protocol=proto_var.get(), base_url=url_var.get(),
                    api_key=key_var.get(), model=model_var.get()),
                obsidian=ObsidianSettings(
                    vault_path=vault_var.get(), subdir=subdir_var.get()),
                whisper_model=self._settings.whisper_model,
            )
            self._reload_settings(new_settings)
            wizard.destroy()
            self._build_main_view()

        ttk.Button(done, text="开始使用", command=_finish).pack(pady=30)

        self.wait_window(wizard)

    # ══════════════════════════════════════════════════════════════════════
    # SETTINGS DIALOG
    # ══════════════════════════════════════════════════════════════════════

    def _open_settings(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("设置")
        dlg.geometry("520x440")
        dlg.transient(self)
        dlg.grab_set()

        nb = ttk.Notebook(dlg)
        nb.pack(fill="both", expand=True, padx=15, pady=15)

        # LLM
        llm = ttk.Frame(nb, padding=15)
        nb.add(llm, text="大模型")
        llm.columnconfigure(1, weight=1)

        proto_v = tk.StringVar(value=self._settings.llm.protocol)
        ttk.Label(llm, text="协议:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(llm, textvariable=proto_v, values=["anthropic", "openai"],
                     width=22, state="readonly").grid(row=0, column=1, pady=4)

        url_v = tk.StringVar(value=self._settings.llm.base_url)
        _labeled_row(llm, "Base URL:", 1, url_v, width=40)
        key_v = tk.StringVar(value=self._settings.llm.api_key)
        _labeled_row(llm, "API Key:", 2, key_v, width=40, show="*")
        model_v = tk.StringVar(value=self._settings.llm.model)
        _labeled_row(llm, "模型名:", 3, model_v, width=40)

        tpl_v = tk.StringVar(value=self._settings.llm.template or "general")
        ttk.Label(llm, text="默认模板:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(llm, textvariable=tpl_v,
                     values=["general", "course", "meeting", "short_video", "article"],
                     width=22, state="readonly").grid(row=4, column=1, sticky="w", pady=4)

        use_keyring = tk.BooleanVar(value=KeyringStore().is_available())
        if KeyringStore().is_available():
            ttk.Checkbutton(llm, text="保存 API Key 到系统钥匙串 (Keychain/Keyring)", variable=use_keyring).grid(
                row=5, column=0, columnspan=2, sticky="w", pady=6
            )

        # Obsidian
        obs = ttk.Frame(nb, padding=15)
        nb.add(obs, text="Obsidian")
        obs.columnconfigure(1, weight=1)

        vault_v = tk.StringVar(value=self._settings.obsidian.vault_path)
        _labeled_row(obs, "Vault 路径:", 0, vault_v, width=35)
        subdir_v = tk.StringVar(value=self._settings.obsidian.subdir)
        _labeled_row(obs, "子目录:", 1, subdir_v, width=35)

        # Advanced
        adv = ttk.Frame(nb, padding=15)
        nb.add(adv, text="高级")
        adv.columnconfigure(1, weight=1)

        proxy_v = tk.StringVar(value=self._settings.proxy or "")
        _labeled_row(adv, "HTTP 代理:", 0, proxy_v, width=35)
        cookies_v = tk.StringVar(value=self._settings.cookies_from_browser or "")
        ttk.Label(adv, text="浏览器 Cookie:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(adv, textvariable=cookies_v,
                     values=["", "chrome", "firefox", "safari", "edge"],
                     width=22).grid(row=1, column=1, sticky="w", pady=4)

        # Save button
        def _save():
            api_k = key_v.get()
            if use_keyring.get() and api_k:
                KeyringStore().set_password("llm_api_key", api_k)

            new_settings = AppSettings(
                llm=LLMSettings(protocol=proto_v.get(), base_url=url_v.get(),
                                api_key=api_k, model=model_v.get(),
                                template=tpl_v.get()),
                obsidian=ObsidianSettings(vault_path=vault_v.get(),
                                          subdir=subdir_v.get()),
                whisper_model=self._settings.whisper_model,
                proxy=proxy_v.get() or None,
                cookies_from_browser=cookies_v.get() or None,
            )
            self._reload_settings(new_settings)
            dlg.destroy()
            messagebox.showinfo("已保存", "设置已保存到本地配置文件", parent=self)

        ttk.Button(dlg, text="保存设置", command=_save).pack(pady=(0, 15))

    # ══════════════════════════════════════════════════════════════════════
    # MAIN VIEW
    # ══════════════════════════════════════════════════════════════════════

    def _build_main_view(self) -> None:
        for w in self.winfo_children():
            if isinstance(w, tk.Menu):
                continue
            w.destroy()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Input area ────────────────────────────────────────────────────
        input_frame = ttk.LabelFrame(self, text="链接或分享口令", padding=12)
        input_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        input_frame.columnconfigure(0, weight=1)

        self._input_text = tk.Text(input_frame, height=6, font=("Helvetica Neue", 12),
                                   wrap="word", relief="solid", borderwidth=1,
                                   padx=8, pady=8)
        self._input_text.grid(row=0, column=0, sticky="ew")

        ctrl = ttk.Frame(input_frame)
        ctrl.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(ctrl, text="📁 选择本地文件", command=self._pick_files).pack(side="left", padx=(0, 5))
        ttk.Button(ctrl, text="🔍 识别链接", command=self._preview_urls).pack(side="left", padx=5)

        ttk.Label(ctrl, text="场景模板:").pack(side="left", padx=(10, 2))
        self._template_var = tk.StringVar(value=self._settings.llm.template or "general")
        template_display = [f"{v} ({k})" for k, v in TEMPLATE_LABELS.items()]
        self._template_combo = ttk.Combobox(
            ctrl,
            values=template_display,
            width=15,
            state="readonly",
        )
        cur_tpl = self._template_var.get()
        self._template_combo.set(f"{TEMPLATE_LABELS.get(cur_tpl, '通用知识笔记')} ({cur_tpl})")
        self._template_combo.pack(side="left", padx=(0, 5))

        self._force_refresh_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="强制重转", variable=self._force_refresh_var).pack(side="left", padx=5)

        ttk.Button(ctrl, text="▶ 开始处理", command=self._start_processing).pack(side="right", padx=(5, 0))

        self._preview_lbl = ttk.Label(ctrl, text="", foreground="#6b6b6b")
        self._preview_lbl.pack(side="right", padx=15)

        # ── Task queue ────────────────────────────────────────────────────
        task_frame = ttk.LabelFrame(self, text="任务队列", padding=12)
        task_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        task_frame.columnconfigure(0, weight=1)
        task_frame.rowconfigure(0, weight=1)

        cols = ("title", "platform", "stage", "progress")
        self._tree = ttk.Treeview(task_frame, columns=cols, show="headings", height=6)
        self._tree.heading("title", text="标题 / 链接")
        self._tree.heading("platform", text="平台")
        self._tree.heading("stage", text="阶段")
        self._tree.heading("progress", text="进度")
        self._tree.column("title", width=430)
        self._tree.column("platform", width=80, anchor="center")
        self._tree.column("stage", width=140)
        self._tree.column("progress", width=70, anchor="center")
        self._tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(task_frame, orient="vertical", command=self._tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=scrollbar.set)

        ttk.Button(task_frame, text="清理已完成",
                   command=self._clear_completed).grid(row=1, column=0, sticky="e", pady=(8, 0))

        # ── Result area ───────────────────────────────────────────────────
        result_frame = ttk.LabelFrame(self, text="结果详情", padding=12)
        result_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 15))
        result_frame.columnconfigure(0, weight=1)

        self._result_text = tk.Text(result_frame, height=8,
                                    font=("Helvetica Neue", 11),
                                    wrap="word", relief="solid", borderwidth=1,
                                    padx=8, pady=8)
        self._result_text.grid(row=0, column=0, sticky="ew")

        actions = ttk.Frame(result_frame)
        actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="在 Obsidian 中打开", command=self._open_in_obsidian).pack(side="left", padx=(0, 5))
        ttk.Button(actions, text="打开 Markdown", command=self._open_markdown).pack(side="left", padx=5)
        ttk.Button(actions, text="复制摘要", command=self._copy_summary).pack(side="left", padx=5)
        ttk.Button(actions, text="打开原文", command=self._open_source).pack(side="left", padx=5)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Tag styles
        self._tree.tag_configure("success", foreground=COLOR_SUCCESS)
        self._tree.tag_configure("failed", foreground=COLOR_FAILED)
        self._tree.tag_configure("cancelled", foreground=COLOR_QUEUED)
        self._tree.tag_configure("active", foreground=COLOR_ACTIVE)

        self._poll_events()

    # ── Actions ───────────────────────────────────────────────────────────

    def _pick_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="选择音视频文件",
            filetypes=[("音视频", "*.mp3 *.m4a *.wav *.mp4 *.mov *.mkv"), ("所有", "*.*")])
        if files:
            self._input_text.insert("end", "\n".join(files))

    def _preview_urls(self) -> None:
        text = self._input_text.get("1.0", "end").strip()
        urls = extract_urls(text)
        if not urls:
            self._preview_lbl.config(text="未识别到链接", foreground="#999")
            return
        from evey2obs.inputs import identify_source
        platforms = [PLATFORM_LABELS.get(identify_source(u), "?") for u in urls]
        unique = len(set(urls))
        self._preview_lbl.config(
            text=f"识别 {len(urls)} 条（{unique} 不重复）: {', '.join(platforms[:4])}",
            foreground="#1565c0")
        self._pending_urls = urls

    def _start_processing(self) -> None:
        if not self._bridge:
            messagebox.showwarning("未配置", "请先完成设置")
            return
        text = self._input_text.get("1.0", "end").strip()
        if not text:
            return
        urls = extract_urls(text)
        # Detect local files: lines that are valid paths (not URLs)
        files = []
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("http"):
                continue
            # Expand ~ and resolve relative to home
            p = Path(line).expanduser()
            if not p.is_absolute():
                p = Path.home() / p
            if p.exists():
                files.append(str(p.resolve()))
        si = SourceInput(raw_text=text, urls=tuple(urls), local_files=tuple(files))
        if not urls and not files:
            messagebox.showwarning("未识别",
                "未检测到有效链接或本地文件。\n\n"
                "链接：粘贴 http:// 或 https:// 开头的网址\n"
                "文件：使用「选择本地文件」按钮，或输入绝对路径")
            return
        # Determine template
        selected_display = self._template_combo.get()
        template_key = "general"
        for k in TEMPLATE_LABELS:
            if f"({k})" in selected_display:
                template_key = k
                break
        force_refresh = self._force_refresh_var.get()

        tasks = self._bridge.submit(
            si, force_refresh=force_refresh, template=template_key
        )
        for t in tasks:
            title = text[:60].replace("\n", " ")
            self._tree.insert("", "end", iid=t.id,
                              values=(title, "识别中...", "排队中", "0%"))
        self._input_text.delete("1.0", "end")
        self._preview_lbl.config(text=f"已提交 {len(tasks)} 个任务", foreground="#2e7d32")

    def _poll_events(self) -> None:
        if self._bridge:
            for ev in self._bridge.poll_events():
                if ev.task_id in self._tree.get_children(""):
                    stage_lbl = STAGE_LABELS.get(ev.status, ev.status.value)
                    pct = f"{int(ev.progress * 100)}%"
                    vals = list(self._tree.item(ev.task_id, "values"))
                    vals[2] = stage_lbl
                    vals[3] = pct
                    tags = []
                    if ev.status == TaskStatus.SUCCEEDED:
                        tags = ["success"]
                    elif ev.status == TaskStatus.FAILED:
                        tags = ["failed"]
                    elif ev.status == TaskStatus.CANCELLED:
                        tags = ["cancelled"]
                    elif ev.status.is_active:
                        tags = ["active"]
                    self._tree.item(ev.task_id, values=tuple(vals), tags=tags)
        self.after(POLL_INTERVAL_MS, self._poll_events)

    def _on_select(self, _event: object) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        tid = sel[0]
        if self._bridge:
            doc, export = self._bridge.get_result(tid)
            if doc:
                platform = PLATFORM_LABELS.get(doc.source_type, doc.source_type.value)
                self._result_text.delete("1.0", "end")
                self._result_text.insert("end", f"标题: {doc.title or '(无)'}\n")
                self._result_text.insert("end", f"平台: {platform}  |  "
                                         f"作者: {doc.author or '未知'}  |  "
                                         f"提取: {doc.extraction_method.value}\n")
                self._result_text.insert("end", f"来源: {doc.source_url}\n")
                if export:
                    self._result_text.insert("end", f"导出: {export.note_path}\n")
                    self._current_note_path = export.note_path
                self._result_text.insert("end", f"\n── 摘要 ──\n{doc.summary or '(无)'}\n")
                self._result_text.insert("end", "\n── 关键观点 ──\n")
                for kp in doc.key_points:
                    self._result_text.insert("end", f"• {kp}\n")
                self._result_text.insert("end", "\n── 行动项 ──\n")
                for ai in doc.action_items:
                    self._result_text.insert("end", f"☐ {ai}\n")
                self._current_source_url = doc.source_url

    def _clear_completed(self) -> None:
        for item in list(self._tree.get_children("")):
            tags = self._tree.item(item, "tags")
            if tags and any(t in ("success", "failed", "cancelled") for t in tags):
                self._tree.delete(item)

    def _open_markdown(self) -> None:
        if hasattr(self, "_current_note_path") and self._settings.obsidian.vault_path:
            p = Path(self._settings.obsidian.vault_path) / self._current_note_path
            if p.exists():
                _open_file(str(p))

    def _copy_summary(self) -> None:
        text = self._result_text.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)

    def _open_in_obsidian(self) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        task_id = sel[0]
        _, result = self._bridge.get_result(task_id) if self._bridge else (None, None)
        if result and getattr(result, "obsidian_uri", None):
            import webbrowser
            webbrowser.open(result.obsidian_uri)
        elif hasattr(self, "_current_note_path") and self._settings.obsidian.vault_path:
            p = Path(self._settings.obsidian.vault_path) / self._current_note_path
            if p.exists():
                _open_file(str(p))
            else:
                messagebox.showinfo("提示", "未找到导出的笔记文件", parent=self)
        else:
            messagebox.showinfo("提示", "当前任务尚未生成 Obsidian 笔记", parent=self)

    def _open_pending_exports(self) -> None:
        if not self._bridge:
            messagebox.showwarning("未初始化", "服务未初始化", parent=self)
            return

        drafts = self._bridge.pipeline.pending_exports.list()
        dlg = tk.Toplevel(self)
        dlg.title("待导出草稿箱")
        dlg.geometry("680x400")
        dlg.transient(self)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="因 Vault 路径或权限问题暂存的本地笔记草稿：").pack(anchor="w", pady=(0, 6))

        cols = ("id", "title", "platform", "time")
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        tree.heading("id", text="草稿 ID")
        tree.heading("title", text="标题")
        tree.heading("platform", text="平台")
        tree.heading("time", text="暂存时间")
        tree.column("id", width=80, anchor="center")
        tree.column("title", width=300)
        tree.column("platform", width=80, anchor="center")
        tree.column("time", width=160)
        tree.pack(fill="both", expand=True)

        for d in drafts:
            tree.insert("", "end", iid=d.id, values=(d.id[:8], d.title, d.source_type, d.created_at[:19]))

        btn_bar = ttk.Frame(frame)
        btn_bar.pack(fill="x", pady=(10, 0))

        def _retry():
            sel = tree.selection()
            if not sel:
                return
            draft_id = sel[0]
            try:
                result = self._bridge.retry_export(draft_id)
                tree.delete(draft_id)
                messagebox.showinfo("成功", f"草稿已成功导出到 Obsidian:\n{result.note_path}", parent=dlg)
            except Exception as e:
                messagebox.showerror("导出失败", f"导出失败: {e}", parent=dlg)

        def _delete():
            sel = tree.selection()
            if not sel:
                return
            draft_id = sel[0]
            self._bridge.pipeline.pending_exports.remove(draft_id)
            tree.delete(draft_id)

        ttk.Button(btn_bar, text="重新导出到 Obsidian", command=_retry).pack(side="left", padx=(0, 5))
        ttk.Button(btn_bar, text="删除草稿", command=_delete).pack(side="left", padx=5)
        ttk.Button(btn_bar, text="关闭", command=dlg.destroy).pack(side="right")

    def _on_close(self) -> None:
        if self._bridge:
            self._bridge.shutdown()
        self.destroy()
