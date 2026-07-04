from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .locator import GLOBAL_FILE, SaveLocation, discover_save_locations, infer_save_dir_from_game_dir, list_save_files
from .model import (
    PARAM_LABELS,
    ActorSummary,
    SaveSlot,
    SaveSnapshot,
    apply_actor_param_plus,
    apply_gold,
    apply_sp,
    buff_party,
    fill_inventory_section,
    list_slots,
    load_snapshot,
    make_backup,
    rebuild_snapshot,
    save_snapshot,
)

TITLE_FONT = ("Microsoft YaHei UI", 16, "bold")
BODY_FONT = ("Microsoft YaHei UI", 10)
SMALL_FONT = ("Microsoft YaHei UI", 9)
ACCENT = "#c89b3c"
BG = "#14181f"
CARD = "#1b212b"
CARD_2 = "#232b38"
TEXT = "#eef2f7"
MUTED = "#9ea8b7"
BORDER = "#303845"
SELECT = "#314158"


class SaveEditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("山河小侠存档编辑器")
        self.geometry("1240x760")
        self.minsize(1120, 680)
        self.configure(bg=BG)

        self.locations: list[SaveLocation] = []
        self.current_location: SaveLocation | None = None
        self.slots_by_id: dict[int, SaveSlot] = {}
        self.current_slot: SaveSlot | None = None
        self.snapshot: SaveSnapshot | None = None
        self.current_actor_id: int | None = None
        self.loading_ui = False
        self.dirty = False

        self.location_var = tk.StringVar()
        self.location_info_var = tk.StringVar(value="等待自动扫描 Steam 存档目录")
        self.status_var = tk.StringVar(value="准备就绪")
        self.slot_file_var = tk.StringVar(value="-")
        self.slot_title_var = tk.StringVar(value="-")
        self.slot_place_var = tk.StringVar(value="-")
        self.slot_playtime_var = tk.StringVar(value="-")
        self.slot_time_var = tk.StringVar(value="-")
        self.gold_var = tk.StringVar(value="0")
        self.sp_var = tk.StringVar(value="0")
        self.actor_name_var = tk.StringVar(value="未选择角色")
        self.actor_detail_var = tk.StringVar(value="-")
        self.buff_var = tk.StringVar(value="50")
        self.items_var = tk.StringVar(value="999")
        self.weapons_var = tk.StringVar(value="99")
        self.armors_var = tk.StringVar(value="99")
        self.param_vars = [tk.StringVar(value="0") for _ in PARAM_LABELS]

        self._install_traces()
        self._build_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(80, lambda: self.refresh_locations(force=True))

    def _install_traces(self) -> None:
        for var in [self.gold_var, self.sp_var, *self.param_vars]:
            var.trace_add("write", self._on_editor_modified)

    def _on_editor_modified(self, *_args: object) -> None:
        if self.loading_ui or not self.snapshot:
            return
        self._set_dirty(True)

    def _set_dirty(self, value: bool) -> None:
        self.dirty = value
        if value:
            self.status_var.set("有未保存修改，保存时会自动生成 .bak 备份")
        elif self.snapshot:
            self.status_var.set(f"已载入 {self.snapshot.slot.file_name}，可以直接修改后保存")
        else:
            self.status_var.set("准备就绪")

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG, foreground=TEXT, font=BODY_FONT)
        style.configure("Root.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure(
            "Section.TLabelframe",
            background=CARD,
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.configure("Section.TLabelframe.Label", background=CARD, foreground=ACCENT, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=TITLE_FONT)
        style.configure("Intro.TLabel", background=BG, foreground=MUTED, font=SMALL_FONT)
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=SMALL_FONT)
        style.configure("Value.TLabel", background=CARD, foreground=TEXT, font=BODY_FONT)
        style.configure("Header.TLabel", background=CARD, foreground=ACCENT, font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TButton", background=CARD_2, foreground=TEXT, bordercolor=BORDER, focuscolor=SELECT, padding=(10, 7))
        style.map("TButton", background=[("active", SELECT), ("pressed", CARD_2)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#111111", bordercolor=ACCENT)
        style.map("Accent.TButton", background=[("active", "#d8ae52"), ("pressed", ACCENT)])
        style.configure("TEntry", fieldbackground=CARD_2, foreground=TEXT, bordercolor=BORDER, insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground=CARD_2, foreground=TEXT, bordercolor=BORDER, arrowsize=16)
        style.map("TCombobox", fieldbackground=[("readonly", CARD_2)], selectbackground=[("readonly", SELECT)], selectforeground=[("readonly", TEXT)])
        style.configure("Treeview", background=CARD_2, fieldbackground=CARD_2, foreground=TEXT, bordercolor=BORDER, rowheight=28)
        style.configure("Treeview.Heading", background=CARD, foreground=ACCENT, bordercolor=BORDER, font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
        style.configure("Status.TLabel", background="#0e1218", foreground=MUTED, padding=(10, 8), font=SMALL_FONT)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="Root.TFrame", padding=(18, 16, 18, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="山河小侠存档编辑器", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="轻量 Tk 版，自动发现 Steam 存档，直接加载、修改、备份、保存", style="Intro.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        toolbar = ttk.Frame(header, style="Root.TFrame")
        toolbar.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(toolbar, text="重新扫描", command=self.refresh_locations).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(toolbar, text="手动选择目录", command=self.choose_save_dir).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="打开存档目录", command=self.open_current_save_dir).grid(row=0, column=2)

        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))

        left = ttk.Frame(main, style="Card.TFrame", padding=14)
        right = ttk.Frame(main, style="Card.TFrame", padding=14)
        main.add(left, weight=38)
        main.add(right, weight=62)

        self._build_left_panel(left)
        self._build_right_panel(right)

        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel", anchor="w").grid(row=2, column=0, sticky="ew")

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        location_box = ttk.LabelFrame(parent, text="存档位置", style="Section.TLabelframe", padding=12)
        location_box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        location_box.columnconfigure(0, weight=1)

        self.location_combo = ttk.Combobox(location_box, textvariable=self.location_var, state="readonly")
        self.location_combo.grid(row=0, column=0, sticky="ew")
        self.location_combo.bind("<<ComboboxSelected>>", self._on_location_selected)
        ttk.Label(location_box, textvariable=self.location_info_var, style="Muted.TLabel", wraplength=360, justify="left").grid(row=1, column=0, sticky="ew", pady=(10, 0))

        slot_box = ttk.LabelFrame(parent, text="存档槽位", style="Section.TLabelframe", padding=10)
        slot_box.grid(row=1, column=0, sticky="nsew")
        slot_box.columnconfigure(0, weight=1)
        slot_box.rowconfigure(0, weight=1)

        self.slot_tree = ttk.Treeview(slot_box, columns=("slot", "place", "playtime", "time"), show="headings", selectmode="browse")
        self.slot_tree.heading("slot", text="槽位")
        self.slot_tree.heading("place", text="地点")
        self.slot_tree.heading("playtime", text="时长")
        self.slot_tree.heading("time", text="保存时间")
        self.slot_tree.column("slot", width=60, anchor="center", stretch=False)
        self.slot_tree.column("place", width=140, anchor="w")
        self.slot_tree.column("playtime", width=80, anchor="center", stretch=False)
        self.slot_tree.column("time", width=150, anchor="center", stretch=False)
        self.slot_tree.grid(row=0, column=0, sticky="nsew")
        self.slot_tree.bind("<<TreeviewSelect>>", self._on_slot_selected)
        scroll = ttk.Scrollbar(slot_box, orient="vertical", command=self.slot_tree.yview)
        self.slot_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        meta_box = ttk.LabelFrame(parent, text="当前存档", style="Section.TLabelframe", padding=12)
        meta_box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for idx in range(4):
            meta_box.columnconfigure(idx, weight=1)
        self._kv(meta_box, 0, 0, "文件", self.slot_file_var)
        self._kv(meta_box, 0, 1, "标题", self.slot_title_var)
        self._kv(meta_box, 1, 0, "地点", self.slot_place_var)
        self._kv(meta_box, 1, 1, "时长", self.slot_playtime_var)
        self._kv(meta_box, 2, 0, "保存时间", self.slot_time_var, span=3)

        resource_box = ttk.LabelFrame(parent, text="基础资源", style="Section.TLabelframe", padding=12)
        resource_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for idx in range(4):
            resource_box.columnconfigure(idx, weight=1)
        ttk.Label(resource_box, text="金钱", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(resource_box, textvariable=self.gold_var).grid(row=0, column=1, sticky="ew", padx=(8, 12))
        ttk.Button(resource_box, text="设为 99999999", command=lambda: self._set_numeric(self.gold_var, 99999999)).grid(row=0, column=2, sticky="ew")
        ttk.Label(resource_box, text="学点", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(resource_box, textvariable=self.sp_var).grid(row=1, column=1, sticky="ew", padx=(8, 12), pady=(10, 0))
        ttk.Button(resource_box, text="设为 9999", command=lambda: self._set_numeric(self.sp_var, 9999)).grid(row=1, column=2, sticky="ew", pady=(10, 0))
        ttk.Label(resource_box, text="提示：保存时会自动备份为 .bak，可放心反复试", style="Muted.TLabel").grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))

        party_box = ttk.LabelFrame(parent, text="队伍角色与属性加成", style="Section.TLabelframe", padding=12)
        party_box.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        party_box.columnconfigure(0, weight=3)
        party_box.columnconfigure(1, weight=4)
        party_box.rowconfigure(0, weight=1)

        actor_list_frame = ttk.Frame(party_box, style="Card.TFrame")
        actor_list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        actor_list_frame.columnconfigure(0, weight=1)
        actor_list_frame.rowconfigure(0, weight=1)

        self.actor_tree = ttk.Treeview(actor_list_frame, columns=("name", "hp", "mp"), show="headings", selectmode="browse", height=10)
        self.actor_tree.heading("name", text="角色")
        self.actor_tree.heading("hp", text="HP")
        self.actor_tree.heading("mp", text="MP")
        self.actor_tree.column("name", width=180, anchor="w")
        self.actor_tree.column("hp", width=70, anchor="center", stretch=False)
        self.actor_tree.column("mp", width=70, anchor="center", stretch=False)
        self.actor_tree.grid(row=0, column=0, sticky="nsew")
        self.actor_tree.bind("<<TreeviewSelect>>", self._on_actor_selected)
        actor_scroll = ttk.Scrollbar(actor_list_frame, orient="vertical", command=self.actor_tree.yview)
        self.actor_tree.configure(yscrollcommand=actor_scroll.set)
        actor_scroll.grid(row=0, column=1, sticky="ns")

        editor = ttk.Frame(party_box, style="Card.TFrame")
        editor.grid(row=0, column=1, sticky="nsew")
        for idx in range(4):
            editor.columnconfigure(idx, weight=1)
        ttk.Label(editor, textvariable=self.actor_name_var, style="Header.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(editor, textvariable=self.actor_detail_var, style="Muted.TLabel", wraplength=420, justify="left").grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 12))

        for idx, label in enumerate(PARAM_LABELS):
            row = 2 + idx // 2
            col = (idx % 2) * 2
            ttk.Label(editor, text=label, style="Value.TLabel").grid(row=row, column=col, sticky="w", pady=6)
            ttk.Entry(editor, textvariable=self.param_vars[idx]).grid(row=row, column=col + 1, sticky="ew", padx=(8, 14), pady=6)

        quick_box = ttk.LabelFrame(parent, text="快捷操作", style="Section.TLabelframe", padding=12)
        quick_box.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        for idx in range(4):
            quick_box.columnconfigure(idx, weight=1)
        ttk.Label(quick_box, text="全队属性 +", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(quick_box, textvariable=self.buff_var, width=8).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(quick_box, text="应用到当前队伍", command=self.apply_party_buff).grid(row=0, column=2, sticky="ew")

        ttk.Label(quick_box, text="道具数量", style="Header.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(quick_box, textvariable=self.items_var, width=8).grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
        ttk.Button(quick_box, text="填满道具栏", command=lambda: self.fill_inventory("_items", self.items_var, "道具栏")).grid(row=1, column=2, sticky="ew", pady=(10, 0))

        ttk.Label(quick_box, text="武器数量", style="Header.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(quick_box, textvariable=self.weapons_var, width=8).grid(row=2, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
        ttk.Button(quick_box, text="填满武器栏", command=lambda: self.fill_inventory("_weapons", self.weapons_var, "武器栏")).grid(row=2, column=2, sticky="ew", pady=(10, 0))

        ttk.Label(quick_box, text="护甲数量", style="Header.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(quick_box, textvariable=self.armors_var, width=8).grid(row=3, column=1, sticky="ew", padx=(8, 8), pady=(10, 0))
        ttk.Button(quick_box, text="填满护甲栏", command=lambda: self.fill_inventory("_armors", self.armors_var, "护甲栏")).grid(row=3, column=2, sticky="ew", pady=(10, 0))

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.grid(row=4, column=0, sticky="ew")
        for idx in range(4):
            actions.columnconfigure(idx, weight=1)
        ttk.Button(actions, text="只创建备份", command=self.backup_current).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(actions, text="重新加载当前存档", command=self.reload_current_slot).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(actions, text="导出 JSON", command=self.export_current_json).grid(row=0, column=2, sticky="ew", padx=(0, 8))
        ttk.Button(actions, text="保存修改", style="Accent.TButton", command=self.save_current_slot).grid(row=0, column=3, sticky="ew")

    def _kv(self, parent: ttk.LabelFrame, row: int, column_group: int, label: str, variable: tk.StringVar, span: int = 1) -> None:
        column = column_group * 2
        ttk.Label(parent, text=label, style="Header.TLabel").grid(row=row, column=column, sticky="w", pady=4)
        ttk.Label(parent, textvariable=variable, style="Value.TLabel").grid(row=row, column=column + 1, columnspan=span, sticky="w", padx=(8, 18), pady=4)

    def refresh_locations(self, force: bool = False) -> None:
        if not force and not self._confirm_discard_changes():
            return
        self.status_var.set("正在扫描 Steam 存档目录...")
        starts = [Path.cwd(), Path(sys.argv[0]).resolve().parent, Path(__file__).resolve().parent]
        found: list[SaveLocation] = []
        seen: set[str] = set()
        for start in starts:
            for item in discover_save_locations(start):
                try:
                    key = str(item.save_dir.resolve()).lower()
                except OSError:
                    key = str(item.save_dir).lower()
                if key not in seen:
                    found.append(item)
                    seen.add(key)

        self.locations = found
        self.location_combo["values"] = [self._location_label(item) for item in found]

        if not found:
            self.current_location = None
            self.location_var.set("")
            self.location_info_var.set("未自动找到存档目录，可以点击“手动选择目录”并选中 save 文件夹")
            self._populate_slots([])
            self._clear_snapshot_ui()
            self.status_var.set("未找到存档目录，请手动选择")
            return

        current_dir = str(self.current_location.save_dir) if self.current_location else None
        index = 0
        if current_dir:
            for idx, item in enumerate(found):
                if str(item.save_dir) == current_dir:
                    index = idx
                    break
        self.location_combo.current(index)
        self._activate_location(found[index])

    def _location_label(self, location: SaveLocation) -> str:
        return f"{location.save_dir}  [{location.source}]"

    def _on_location_selected(self, _event: tk.Event | None = None) -> None:
        index = self.location_combo.current()
        if index < 0 or index >= len(self.locations):
            return
        location = self.locations[index]
        if self.current_location and str(location.save_dir) != str(self.current_location.save_dir):
            if not self._confirm_discard_changes():
                self._restore_current_location_selection()
                return
        self._activate_location(location)

    def _activate_location(self, location: SaveLocation) -> None:
        self.current_location = location
        detail = [f"存档目录: {location.save_dir}", f"来源: {location.source}"]
        if location.manifest_path:
            detail.append(f"Manifest: {location.manifest_path}")
        self.location_info_var.set("\n".join(detail))
        self.load_slots_for_current_location()

    def choose_save_dir(self) -> None:
        if not self._confirm_discard_changes():
            return
        initial = str(self.current_location.save_dir if self.current_location else Path.home())
        selected = filedialog.askdirectory(title="选择 save 目录或游戏目录", initialdir=initial)
        if not selected:
            return
        chosen = Path(selected)
        resolved = infer_save_dir_from_game_dir(chosen) or (chosen if (chosen / GLOBAL_FILE).exists() else None)
        if resolved is None and list_save_files(chosen):
            resolved = chosen
        if resolved is None:
            messagebox.showerror("目录无效", "未在该目录中找到 global.rmmzsave 或 file*.rmmzsave")
            return
        manual = SaveLocation(save_dir=resolved, source="manual")
        self.locations = [manual, *[item for item in self.locations if str(item.save_dir) != str(resolved)]]
        self.location_combo["values"] = [self._location_label(item) for item in self.locations]
        self.location_combo.current(0)
        self._activate_location(manual)

    def load_slots_for_current_location(self) -> None:
        if not self.current_location:
            self._populate_slots([])
            return
        try:
            slots = list_slots(self.current_location.save_dir)
        except Exception as exc:
            self._populate_slots([])
            self._clear_snapshot_ui()
            messagebox.showerror("读取失败", f"读取存档列表失败：\n{exc}")
            self.status_var.set("读取存档列表失败")
            return
        self._populate_slots(slots)
        if slots:
            first_slot = slots[0]
            self.slot_tree.selection_set(str(first_slot.slot_id))
            self.slot_tree.focus(str(first_slot.slot_id))
            self.load_slot(first_slot)
        else:
            self._clear_snapshot_ui()
            self.status_var.set("该目录下没有找到 file*.rmmzsave 存档")

    def _populate_slots(self, slots: list[SaveSlot]) -> None:
        self.slots_by_id = {slot.slot_id: slot for slot in slots}
        self.slot_tree.delete(*self.slot_tree.get_children())
        for slot in slots:
            self.slot_tree.insert("", "end", iid=str(slot.slot_id), values=(f"file{slot.slot_id}", slot.save_name or "-", slot.playtime or "-", slot.timestamp or "-"))

    def _on_slot_selected(self, _event: tk.Event | None = None) -> None:
        selected = self.slot_tree.selection()
        if not selected:
            return
        slot = self.slots_by_id.get(int(selected[0]))
        if not slot:
            return
        if self.current_slot and slot.slot_id != self.current_slot.slot_id:
            if not self._confirm_discard_changes():
                self._restore_current_slot_selection()
                return
        self.load_slot(slot)

    def load_slot(self, slot: SaveSlot) -> None:
        try:
            snapshot = load_snapshot(slot)
        except Exception as exc:
            messagebox.showerror("读取失败", f"读取存档失败：\n{exc}")
            self.status_var.set("读取存档失败")
            return
        self.current_slot = slot
        self.snapshot = snapshot
        self.current_actor_id = None
        self._fill_snapshot_ui(snapshot)
        self._set_dirty(False)

    def _fill_snapshot_ui(self, snapshot: SaveSnapshot) -> None:
        self.loading_ui = True
        try:
            self.slot_file_var.set(snapshot.slot.file_name)
            self.slot_title_var.set(snapshot.slot.title or "-")
            self.slot_place_var.set(snapshot.slot.save_name or "-")
            self.slot_playtime_var.set(snapshot.slot.playtime or "-")
            self.slot_time_var.set(snapshot.slot.timestamp or "-")
            self.gold_var.set(str(snapshot.gold))
            self.sp_var.set(str(snapshot.sp))
            self._populate_actor_tree(snapshot.actors)
            if snapshot.actors:
                first_actor = snapshot.actors[0]
                self.actor_tree.selection_set(str(first_actor.actor_id))
                self.actor_tree.focus(str(first_actor.actor_id))
                self._show_actor(first_actor)
                self.current_actor_id = first_actor.actor_id
            else:
                self.current_actor_id = None
                self.actor_name_var.set("当前队伍没有角色")
                self.actor_detail_var.set("-")
                for var in self.param_vars:
                    var.set("0")
        finally:
            self.loading_ui = False

    def _populate_actor_tree(self, actors: list[ActorSummary]) -> None:
        self.actor_tree.delete(*self.actor_tree.get_children())
        for actor in actors:
            self.actor_tree.insert("", "end", iid=str(actor.actor_id), values=(actor.label, actor.hp, actor.mp))

    def _find_actor(self, actor_id: int | None) -> ActorSummary | None:
        if actor_id is None or not self.snapshot:
            return None
        for actor in self.snapshot.actors:
            if actor.actor_id == actor_id:
                return actor
        return None

    def _on_actor_selected(self, _event: tk.Event | None = None) -> None:
        if not self.snapshot:
            return
        selected = self.actor_tree.selection()
        if not selected:
            return
        new_actor_id = int(selected[0])
        if self.current_actor_id is not None and new_actor_id != self.current_actor_id:
            if not self._flush_actor_editor(show_error=True):
                self.actor_tree.selection_set(str(self.current_actor_id))
                self.actor_tree.focus(str(self.current_actor_id))
                return
        actor = self._find_actor(new_actor_id)
        if actor:
            self.current_actor_id = new_actor_id
            self._show_actor(actor)

    def _show_actor(self, actor: ActorSummary) -> None:
        self.loading_ui = True
        try:
            self.actor_name_var.set(actor.name)
            nickname = f"，绰号：{actor.nickname}" if actor.nickname else ""
            self.actor_detail_var.set(f"角色 ID: {actor.actor_id}，等级: {actor.level}，HP: {actor.hp}，MP: {actor.mp}，TP: {actor.tp}{nickname}")
            values = actor.param_plus[: len(PARAM_LABELS)]
            values.extend([0] * (len(PARAM_LABELS) - len(values)))
            for var, value in zip(self.param_vars, values):
                var.set(str(value))
        finally:
            self.loading_ui = False

    def _clear_snapshot_ui(self) -> None:
        self.loading_ui = True
        try:
            self.current_slot = None
            self.snapshot = None
            self.current_actor_id = None
            self.slot_file_var.set("-")
            self.slot_title_var.set("-")
            self.slot_place_var.set("-")
            self.slot_playtime_var.set("-")
            self.slot_time_var.set("-")
            self.gold_var.set("0")
            self.sp_var.set("0")
            self.actor_name_var.set("未选择角色")
            self.actor_detail_var.set("-")
            self.actor_tree.delete(*self.actor_tree.get_children())
            for var in self.param_vars:
                var.set("0")
        finally:
            self.loading_ui = False
        self._set_dirty(False)

    def _set_numeric(self, variable: tk.StringVar, value: int) -> None:
        variable.set(str(value))

    def _parse_int(self, value: str, label: str) -> int:
        text = value.strip()
        if not text:
            raise ValueError(f"{label} 不能为空")
        return int(text)

    def _flush_actor_editor(self, show_error: bool) -> bool:
        if not self.snapshot or self.current_actor_id is None:
            return True
        actor = self._find_actor(self.current_actor_id)
        if not actor:
            return True
        try:
            values = [self._parse_int(var.get(), label) for var, label in zip(self.param_vars, PARAM_LABELS)]
        except ValueError as exc:
            if show_error:
                messagebox.showerror("输入错误", str(exc))
            return False
        apply_actor_param_plus(self.snapshot.data, actor.actor_id, values)
        actor.param_plus = values
        return True

    def _apply_form_to_snapshot(self) -> bool:
        if not self.snapshot:
            return False
        if not self._flush_actor_editor(show_error=True):
            return False
        try:
            gold = self._parse_int(self.gold_var.get(), "金钱")
            sp = self._parse_int(self.sp_var.get(), "学点")
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
            return False
        apply_gold(self.snapshot.data, gold)
        apply_sp(self.snapshot.data, sp)
        self.snapshot.gold = gold
        self.snapshot.sp = sp
        return True

    def apply_party_buff(self) -> None:
        if not self.snapshot:
            messagebox.showinfo("提示", "请先选择一个存档")
            return
        if not self._apply_form_to_snapshot():
            return
        try:
            amount = self._parse_int(self.buff_var.get(), "全队属性加成")
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
            return
        changed = buff_party(self.snapshot.data, amount)
        rebuild_snapshot(self.snapshot)
        self._fill_snapshot_ui(self.snapshot)
        self._set_dirty(True)
        self.status_var.set(f"已给当前队伍 {len(changed)} 名角色的 8 项属性各增加 {amount}")

    def fill_inventory(self, section: str, variable: tk.StringVar, title: str) -> None:
        if not self.snapshot:
            messagebox.showinfo("提示", "请先选择一个存档")
            return
        if not self._apply_form_to_snapshot():
            return
        try:
            amount = self._parse_int(variable.get(), title)
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc))
            return
        count = fill_inventory_section(self.snapshot.data, section, amount)
        self._set_dirty(True)
        self.status_var.set(f"已将 {title} 中的 {count} 种条目数量统一设为 {amount}")

    def backup_current(self) -> None:
        if not self.current_slot:
            messagebox.showinfo("提示", "请先选择一个存档")
            return
        try:
            backup = make_backup(self.current_slot)
        except Exception as exc:
            messagebox.showerror("备份失败", f"创建备份失败：\n{exc}")
            return
        self.status_var.set(f"已准备备份: {backup.name}")
        messagebox.showinfo("备份完成", f"已创建或保留备份：\n{backup}")

    def reload_current_slot(self) -> None:
        if not self.current_slot:
            messagebox.showinfo("提示", "请先选择一个存档")
            return
        if self.dirty and not messagebox.askyesno("放弃修改", "当前有未保存修改，重新加载会丢弃这些更改，是否继续？"):
            return
        self.load_slot(self.current_slot)

    def export_current_json(self) -> None:
        if not self.current_slot or not self.snapshot:
            messagebox.showinfo("提示", "请先选择一个存档")
            return
        target = filedialog.asksaveasfilename(
            title="导出 JSON",
            initialfile=f"{self.current_slot.file_path.name}.json",
            initialdir=str(self.current_slot.file_path.parent),
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
        )
        if not target:
            return
        if not self._apply_form_to_snapshot():
            return
        try:
            Path(target).write_text(json.dumps(self.snapshot.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("导出失败", f"导出 JSON 失败：\n{exc}")
            return
        self.status_var.set(f"已导出 JSON: {target}")
        messagebox.showinfo("导出完成", f"已导出到：\n{target}")

    def save_current_slot(self) -> None:
        if not self.current_slot or not self.snapshot:
            messagebox.showinfo("提示", "请先选择一个存档")
            return
        if not self._apply_form_to_snapshot():
            return
        try:
            backup = make_backup(self.current_slot)
            save_path = save_snapshot(self.snapshot)
        except Exception as exc:
            messagebox.showerror("保存失败", f"保存存档失败：\n{exc}")
            return
        self.load_slot(self.current_slot)
        self.status_var.set(f"保存成功: {save_path.name}，备份: {backup.name}")
        messagebox.showinfo("保存成功", f"存档已写回：\n{save_path}\n\n备份文件：\n{backup}")

    def open_current_save_dir(self) -> None:
        if not self.current_location:
            messagebox.showinfo("提示", "请先找到或选择一个存档目录")
            return
        path = self.current_location.save_dir
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("打开失败", f"无法打开目录：\n{exc}")

    def _confirm_discard_changes(self) -> bool:
        if not self.dirty:
            return True
        return messagebox.askyesno("放弃未保存修改", "当前有未保存修改，继续会丢失这些更改，是否继续？")

    def _restore_current_slot_selection(self) -> None:
        if not self.current_slot:
            return
        slot_id = str(self.current_slot.slot_id)
        if self.slot_tree.exists(slot_id):
            self.slot_tree.selection_set(slot_id)
            self.slot_tree.focus(slot_id)

    def _restore_current_location_selection(self) -> None:
        if not self.current_location:
            return
        current_dir = str(self.current_location.save_dir)
        for idx, item in enumerate(self.locations):
            if str(item.save_dir) == current_dir:
                self.location_combo.current(idx)
                return

    def on_close(self) -> None:
        if not self._confirm_discard_changes():
            return
        self.destroy()


def main() -> int:
    app = SaveEditorApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
