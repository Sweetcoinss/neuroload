#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NeuroLoad for Windows — تنزيل فيديوهات YouTube بواجهة أنيقة.

المحرك: yt-dlp + ffmpeg (عبر imageio-ffmpeg).
للاستخدام الشخصي / محتوى Creative Commons فقط — احترم شروط YouTube.
"""
import os
import queue
import re
import shutil
import threading
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import StringVar, filedialog

import customtkinter as ctk
import imageio_ffmpeg
from PIL import Image

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
APP_BG = "#0B1020"
PANEL = "#151D38"
PANEL_2 = "#1F2947"
PANEL_3 = "#262F55"
CYAN = "#22D3EE"
VIOLET = "#8B5CF6"
TEXT = "#E8ECFB"
TEXT_DIM = "#98A2C6"
GREEN = "#34D399"
AMBER = "#FBBF24"
RED = "#F87171"
FONT = "Segoe UI"

QUALITY_FORMATS = {
    "1080p": "bestvideo[height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]",
    "MP3": "bestaudio/best",
}


class Cancelled(Exception):
    pass


@dataclass
class DownloadItem:
    id: int
    url: str
    title: str = "…"
    format_label: str = ""
    progress: float = 0.0
    eta: str = ""
    status: str = "downloading"  # downloading | done | failed | cancelled
    error: str = ""
    file_path: str = ""
    cancel_event: threading.Event = field(default_factory=threading.Event)


def format_duration(total_seconds) -> str:
    try:
        total = int(total_seconds)
    except (TypeError, ValueError):
        return "?:??"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_bytes(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024
    return f"{num:.1f} GB"


def gradient_image(width: int, height: int, c1=CYAN, c2=VIOLET, radius: int = 0) -> Image.Image:
    """Horizontal linear gradient image."""
    img = Image.new("RGB", (width, height))
    def hex2rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    start, end = hex2rgb(c1), hex2rgb(c2)
    for x in range(width):
        t = x / max(width - 1, 1)
        color = tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(3))
        for y in range(height):
            img.putpixel((x, y), color)
    return img


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


class GradientButton(ctk.CTkFrame):
    """True cyan→violet gradient button: full-frame image label + text label."""

    def __init__(self, master, text, command=None, height=52, radius=14, font=None, **kwargs):
        super().__init__(master, fg_color="transparent", height=height, corner_radius=0)
        self.command = command
        self._text = text
        self._radius = radius
        self._enabled = True
        self._hover = False
        self._font = font or (FONT, 14, "bold")
        self._image_ref = None

        self._img_label = ctk.CTkLabel(self, text="", corner_radius=radius, fg_color="transparent")
        self._img_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._text_label = ctk.CTkLabel(self, text=text, font=self._font,
                                        text_color="#071018", fg_color="transparent", cursor="hand2")
        self._text_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        for widget in (self._img_label, self._text_label):
            widget.bind("<Button-1>", self._on_click)
            widget.bind("<Enter>", lambda e: self._set_hover(True))
            widget.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Configure>", self._redraw)

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, str):
            return self.cget(cnf)
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
        if "text" in kwargs:
            self._text = kwargs.pop("text")
            self._text_label.configure(text=self._text)
        state = kwargs.pop("state", None)
        if "enabled" in kwargs:
            state = "normal" if kwargs.pop("enabled") else "disabled"
        if state is not None:
            self._enabled = state == "normal"
        if kwargs:
            super().configure(**kwargs)
        self._redraw()

    def cget(self, key):
        special = {
            "text": self._text,
            "state": "normal" if self._enabled else "disabled",
            "fg_color": "transparent",
            "corner_radius": self._radius,
            "cursor": "hand2",
        }
        if key in special:
            return special[key]
        return super().cget(key)

    def _set_hover(self, hover: bool):
        self._hover = hover
        self._redraw()

    def _on_click(self, _event):
        if self._enabled and self.command:
            self.command()

    def _redraw(self, _event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 4 or h < 4:
            return
        c1, c2, text_color = self._palette()
        img = gradient_image(w, h, c1, c2)
        img.putalpha(rounded_mask((w, h), self._radius))
        self._image_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
        self._img_label.configure(image=self._image_ref, corner_radius=self._radius)
        self._text_label.configure(text_color=text_color)

    def _palette(self):
        if not self._enabled:
            return PANEL_2, PANEL_2, TEXT_DIM
        if self._hover:
            return "#3BE4FF", "#A78BFA", "#071018"
        return CYAN, VIOLET, "#071018"


class DownloadRow(ctk.CTkFrame):
    def __init__(self, master, item: DownloadItem, on_cancel, on_open, on_folder, on_remove):
        super().__init__(master, fg_color=PANEL, corner_radius=14, border_width=1, border_color=PANEL_2)
        self.item = item
        self.on_remove = on_remove
        self.grid_columnconfigure(1, weight=1)

        icon_color = VIOLET if item.format_label.startswith("MP3") else CYAN
        badge = ctk.CTkLabel(
            self, text="MP3" if item.format_label.startswith("MP3") else "MP4",
            width=44, height=44, corner_radius=10, fg_color=PANEL_2,
            text_color=icon_color, font=(FONT, 13, "bold"),
        )
        badge.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=12, sticky="n")

        self.title_label = ctk.CTkLabel(
            self, text=item.title[:90], anchor="w", justify="left",
            text_color=TEXT, font=(FONT, 12, "bold"), wraplength=520,
        )
        self.title_label.grid(row=0, column=1, sticky="ew", pady=(12, 0))

        self.meta_label = ctk.CTkLabel(
            self, text=item.format_label, anchor="w",
            text_color=TEXT_DIM, font=(FONT, 10),
        )
        self.meta_label.grid(row=1, column=1, sticky="ew", pady=(2, 0))

        self.progress = ctk.CTkProgressBar(self, height=8, corner_radius=4, progress_color=CYAN, fg_color=PANEL_2)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 4))

        self.status_row = ctk.CTkFrame(self, fg_color="transparent")
        self.status_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        self.status_label = ctk.CTkLabel(self.status_row, text="Starting…", text_color=TEXT_DIM, font=(FONT, 10))
        self.status_label.pack(side="left")

        self.action_box = ctk.CTkFrame(self.status_row, fg_color="transparent")
        self.action_box.pack(side="right")

        self.cancel_btn = ctk.CTkButton(
            self.action_box, text="Cancel", width=64, height=26, corner_radius=8,
            fg_color="#3A1620", hover_color="#4B1C28", text_color=RED, font=(FONT, 10, "bold"),
            command=lambda: on_cancel(item.id),
        )
        self.cancel_btn.pack(side="right")

        self.open_btn = ctk.CTkButton(
            self.action_box, text="Open", width=56, height=26, corner_radius=8,
            fg_color=PANEL_2, hover_color=PANEL_3, text_color=CYAN, font=(FONT, 10, "bold"),
            command=lambda: on_open(item.id),
        )
        self.folder_btn = ctk.CTkButton(
            self.action_box, text="Folder", width=56, height=26, corner_radius=8,
            fg_color=PANEL_2, hover_color=PANEL_3, text_color=CYAN, font=(FONT, 10, "bold"),
            command=lambda: on_folder(item.id),
        )
        self.remove_btn = ctk.CTkButton(
            self, text="✕", width=30, height=30, corner_radius=8,
            fg_color="transparent", hover_color=PANEL_2, text_color=TEXT_DIM,
            font=(FONT, 13), command=lambda: self._remove(),
        )
        self.remove_btn.grid(row=0, column=2, padx=(0, 8), pady=10, sticky="ne")

    def _remove(self):
        self.on_remove(self.id)

    @property
    def id(self):
        return self.item.id

    def refresh(self):
        item = self.item
        self.title_label.configure(text=(item.title or "…")[:110])
        self.meta_label.configure(text=item.format_label)
        if item.status == "downloading":
            self.progress.grid()
            self.progress.set(min(max(item.progress, 0.0), 1.0))
            self.status_label.configure(text=f"{item.progress * 100:.1f}%  ·  ETA {item.eta or '…'}", text_color=CYAN)
            self.cancel_btn.pack(side="right")
            self.open_btn.pack_forget()
            self.folder_btn.pack_forget()
        elif item.status == "done":
            self.progress.set(1.0)
            self.status_label.configure(text="Completed  ✓", text_color=GREEN)
            self.cancel_btn.pack_forget()
            self.folder_btn.pack(side="right", padx=(0, 6))
            self.open_btn.pack(side="right")
        elif item.status == "failed":
            self.progress.set(0.0)
            self.status_label.configure(text=f"Failed: {item.error[:80]}", text_color=RED)
            self.cancel_btn.pack_forget()
        elif item.status == "cancelled":
            self.progress.set(0.0)
            self.status_label.configure(text="Cancelled", text_color=TEXT_DIM)
            self.cancel_btn.pack_forget()


class NeuroLoadApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NeuroLoad for Windows")
        self.geometry("980x640")
        self.minsize(900, 600)
        self.configure(fg_color=APP_BG)
        self._place_and_focus()
        self._set_icon()

        self.output_dir = StringVar(value=self._default_output_dir())
        self._url_var = StringVar()
        self._quality_var = StringVar(value="720p")
        self._items: dict[int, DownloadItem] = {}
        self._rows: dict[int, DownloadRow] = {}
        self._counter = 0
        self._messages: "queue.Queue[tuple]" = queue.Queue()
        self._current_info = None
        self._thumb_ref = None

        self._layout_sidebar()
        self._layout_content()
        self.after(120, self._poll_messages)

    # ---------------- UI LAYOUT ----------------
    def _set_icon(self):
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            ico = os.path.join(base, "neuroload.ico")
            if not os.path.exists(ico):
                self._make_icon(ico)
            self.iconbitmap(ico)
        except Exception:
            pass

    def _make_icon(self, path):
        size = 256
        img = gradient_image(size, size, CYAN, VIOLET)
        mask = rounded_mask((size, size), 56)
        img.putalpha(mask)
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        w = size // 9
        cx = size // 2
        d.line([(cx, 46), (cx, 148)], fill="#071018", width=w)
        d.line([(cx - 52, 106), (cx, 162), (cx + 52, 106)], fill="#071018", width=w, joint="curve")
        d.line([(64, 200), (size - 64, 200)], fill="#071018", width=w)
        img.save(path, sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])

    def _default_output_dir(self) -> str:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads", "NeuroLoad")
        os.makedirs(downloads, exist_ok=True)
        return downloads

    def _place_and_focus(self):
        """Center on screen and make sure the window is visible (no SmartScreen/off-screen surprises)."""
        try:
            self.update_idletasks()
            w, h = 980, 640
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(1500, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _layout_sidebar(self):
        side = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=PANEL)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        logo = ctk.CTkLabel(side, text="⬇", width=74, height=74, corner_radius=20,
                            fg_color=CYAN, text_color="#071018", font=(FONT, 38, "bold"))
        logo.pack(pady=(34, 14))
        ctk.CTkLabel(side, text="NeuroLoad", text_color=TEXT, font=(FONT, 24, "bold")).pack()
        ctk.CTkLabel(side, text="Fast · Clean · Personal", text_color=TEXT_DIM, font=(FONT, 11)).pack(pady=(2, 0))

        chip = ctk.CTkLabel(side, text="YouTube → PC", corner_radius=50, fg_color=PANEL_2,
                            text_color=CYAN, font=(FONT, 11, "bold"), padx=16, pady=6)
        chip.pack(pady=(16, 30))

        ctk.CTkLabel(side, text="SAVE TO", text_color=TEXT_DIM, font=(FONT, 10, "bold")).pack(anchor="w", padx=20)
        self.path_label = ctk.CTkLabel(side, text=self.output_dir.get(), wraplength=190,
                                       justify="left", anchor="w", text_color=TEXT,
                                       font=("Consolas", 10))
        self.path_label.pack(anchor="w", padx=20, pady=(4, 8))
        ctk.CTkButton(side, text="Change folder…", height=30, corner_radius=8,
                      fg_color=PANEL_2, hover_color=PANEL_3, text_color=TEXT,
                      font=(FONT, 11, "bold"), command=self._choose_folder).pack(anchor="w", padx=20)

        spacer = ctk.CTkFrame(side, fg_color="transparent")
        spacer.pack(expand=True, fill="both")

        ctk.CTkLabel(
            side,
            text="For personal use &\nCreative Commons only.\nRespect YouTube ToS.",
            text_color=TEXT_DIM, font=(FONT, 9), justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 20))

    def _layout_content(self):
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=22, pady=18)
        content.grid_rowconfigure(5, weight=1)
        content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(content, text="VIDEO LINK", text_color=TEXT_DIM,
                     font=(FONT, 10, "bold")).grid(row=0, column=0, sticky="w")

        url_row = ctk.CTkFrame(content, fg_color="transparent")
        url_row.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        url_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_row, textvariable=self._url_var, height=46, corner_radius=12,
            fg_color=PANEL, border_color=PANEL_3, border_width=1,
            placeholder_text="https://www.youtube.com/watch?v=…",
            text_color=TEXT, placeholder_text_color=TEXT_DIM, font=(FONT, 12),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(url_row, text="Paste", width=78, height=46, corner_radius=12,
                      fg_color=PANEL_2, hover_color=PANEL_3, text_color=CYAN,
                      font=(FONT, 12, "bold"), command=self._paste_clipboard).grid(row=0, column=1)

        GradientButton(content, text="⚡  Analyze link", height=46,
                       command=self._analyze).grid(row=2, column=0, sticky="ew", pady=(10, 0))

        # --- video preview card (hidden until analyzed) ---
        self.info_card = ctk.CTkFrame(content, fg_color=PANEL, corner_radius=16,
                                      border_width=1, border_color=PANEL_2)
        self.info_card.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.info_card.grid_columnconfigure(1, weight=1)
        self.info_card.grid_remove()

        self.thumb_label = ctk.CTkLabel(self.info_card, text="thumb", width=176, height=99,
                                        corner_radius=12, fg_color=PANEL_2)
        self.thumb_label.grid(row=0, column=0, rowspan=2, padx=12, pady=12)
        self.title_label = ctk.CTkLabel(self.info_card, text="", anchor="w", justify="left",
                                        text_color=TEXT, font=(FONT, 13, "bold"), wraplength=430)
        self.title_label.grid(row=0, column=1, sticky="ew", pady=(14, 0), padx=(0, 12))
        self.uploader_label = ctk.CTkLabel(self.info_card, text="", anchor="w",
                                           text_color=TEXT_DIM, font=(FONT, 11))
        self.uploader_label.grid(row=1, column=1, sticky="w", padx=(0, 12))
        self.license_label = ctk.CTkLabel(self.info_card, text="", corner_radius=8, height=22,
                                          font=(FONT, 9, "bold"), padx=10)
        self.license_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 12))

        self.quality_row = ctk.CTkFrame(content, fg_color="transparent")
        self.quality_row.grid(row=4, column=0, sticky="w", pady=(12, 0))
        ctk.CTkLabel(self.quality_row, text="FORMAT & QUALITY", text_color=TEXT_DIM,
                     font=(FONT, 10, "bold")).pack(anchor="w")
        self.quality_seg = ctk.CTkSegmentedButton(
            self.quality_row, values=list(QUALITY_FORMATS.keys()), variable=self._quality_var,
            height=36, corner_radius=10, fg_color=PANEL,
            selected_color=CYAN, selected_hover_color="#1FB9D4", unselected_color=PANEL,
            unselected_hover_color=PANEL_2, text_color=TEXT,
            font=(FONT, 12, "bold"),
        )
        self.quality_seg.pack(pady=(6, 0))

        self.download_btn = GradientButton(content, text="⬇  Download video", height=56,
                                           font=(FONT, 16, "bold"), command=self._start_download)
        self.download_btn.configure(state="disabled")
        self.download_btn.grid(row=5, column=0, sticky="new", pady=(12, 0))

        ctk.CTkLabel(content, text="DOWNLOADS", text_color=TEXT_DIM,
                     font=(FONT, 10, "bold")).grid(row=6, column=0, sticky="sw", pady=(12, 0))

        self.list_frame = ctk.CTkScrollableFrame(content, fg_color="transparent")
        self.list_frame.grid(row=7, column=0, sticky="nsew", pady=(6, 0))

        self._empty_hint = ctk.CTkLabel(
            self.list_frame,
            text="☁  Nothing here yet\nPaste a link, hit Analyze, then Download",
            text_color=TEXT_DIM, font=(FONT, 12), justify="center")
        self._empty_hint.pack(pady=34)

        self.status_bar = ctk.CTkLabel(content, text="Ready.", anchor="w",
                                       text_color=TEXT_DIM, font=(FONT, 10))
        self.status_bar.grid(row=8, column=0, sticky="ew", pady=(8, 0))

        content.grid_rowconfigure(7, weight=1)

    # ---------------- ACTIONS ----------------
    def _paste_clipboard(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            text = ""
        if text:
            self._url_var.set(text)

    def _choose_folder(self):
        path = filedialog.askdirectory(initialdir=self.output_dir.get())
        if path:
            self.output_dir.set(path)
            self.path_label.configure(text=path)

    def _set_status(self, text, color=TEXT_DIM):
        self.status_bar.configure(text=text, text_color=color)

    def _analyze(self):
        url = self._url_var.get().strip()
        if not url.startswith(("http://", "https://")):
            self._set_status("Paste a valid http(s) link first.", AMBER)
            return
        self._set_status("Fetching video info…", CYAN)
        threading.Thread(target=self._analyze_worker, args=(url,), daemon=True).start()

    def _analyze_worker(self, url):
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            self._messages.put(("info", info))
        except Exception as e:
            self._messages.put(("error", f"Could not fetch video info: {e}"))

    def _start_download(self):
        fmt = self._quality_var.get()
        url = self._url_var.get().strip()
        self._counter += 1
        item = DownloadItem(
            id=self._counter,
            url=url,
            title=(self._current_info or {}).get("title") or "Untitled",
            format_label=("MP3 · Audio" if fmt == "MP3" else f"MP4 · {fmt}"),
        )
        self._items[item.id] = item
        self._add_row(item)
        threading.Thread(target=self._download_worker, args=(item, fmt), daemon=True).start()

    def _download_worker(self, item: DownloadItem, fmt: str):
        out_dir = self.output_dir.get()
        os.makedirs(out_dir, exist_ok=True)
        is_audio = fmt == "MP3"
        try:
            import yt_dlp

            options = {
                "format": QUALITY_FORMATS[fmt],
                "outtmpl": os.path.join(out_dir, "%(title)s [%(id)s].%(ext)s"),
                "noplaylist": True,
                "no_mtime": True,
                "concurrent_fragment_downloads": 16,
                "ffmpeg_location": FFMPEG_PATH,
                "progress_hooks": [lambda d, it=item: self._progress_hook(d, it)],
                "quiet": True,
                "no_warnings": True,
            }
            if is_audio:
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }]
            else:
                options["merge_output_format"] = "mp4"

            if shutil.which("aria2c"):
                options["external_downloader"] = "aria2c"
                options["external_downloader_args"] = {"aria2c": ["-x16", "-s16", "-k1M"]}

            started = datetime.now().timestamp() - 5
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([item.url])

            if item.cancel_event.is_set():
                item.status = "cancelled"
                self._messages.put(("item", item.id))
                return

            newest = None
            for name in os.listdir(out_dir):
                path = os.path.join(out_dir, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if mtime >= started and os.path.isfile(path) and not name.endswith((".part", ".ytdl")):
                    if newest is None or mtime > newest[1]:
                        newest = (path, mtime)
            item.file_path = newest[0] if newest else ""
            item.status = "done"
            item.progress = 1.0
            item.eta = ""
            self._messages.put(("item", item.id))
            self._messages.put(("status", f"✓ Saved: {os.path.basename(item.file_path)}", GREEN))
        except Cancelled:
            item.status = "cancelled"
            self._messages.put(("item", item.id))
        except Exception as e:
            msg = str(e)
            if item.cancel_event.is_set() or "killed" in msg.lower():
                item.status = "cancelled"
            else:
                item.status = "failed"
                item.error = re.sub(r"\s+", " ", msg)[:200]
            self._messages.put(("item", item.id))
            if item.status == "failed":
                self._messages.put(("status", "Download failed. See the card for details.", RED))

    def _progress_hook(self, d, item: DownloadItem):
        if item.cancel_event.is_set():
            raise Cancelled()
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            item.progress = (downloaded / total) if total else 0.0
            item.eta = d.get("_eta_str", "").strip() or "…"
            self._messages.put(("item", item.id))
        elif d.get("status") == "finished":
            item.progress = 0.99
            item.eta = "merging…"
            self._messages.put(("item", item.id))

    def _add_row(self, item: DownloadItem):
        self._empty_hint.pack_forget()
        row = DownloadRow(
            self.list_frame, item,
            on_cancel=self._cancel_item,
            on_open=self._open_item,
            on_folder=self._open_folder,
            on_remove=self._remove_item,
        )
        row.pack(fill="x", pady=6)
        self._rows[item.id] = row

    def _cancel_item(self, item_id):
        item = self._items.get(item_id)
        if item:
            item.cancel_event.set()
            self._set_status("Cancelling…", AMBER)

    def _open_item(self, item_id):
        item = self._items.get(item_id)
        if item and item.file_path and os.path.exists(item.file_path):
            os.startfile(item.file_path)  # noqa: S606 (user's own files)
        else:
            self._set_status("File not found.", RED)

    def _open_folder(self, item_id):
        item = self._items.get(item_id)
        path = item.file_path if item and item.file_path else self.output_dir.get()
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        try:
            os.startfile(folder)  # noqa: S606
        except Exception:
            os.startfile(self.output_dir.get())

    def _remove_item(self, item_id):
        row = self._rows.pop(item_id, None)
        if row:
            row.destroy()
        self._items.pop(item_id, None)
        if not self._rows:
            self._empty_hint.pack(pady=34)

    # ---------------- MESSAGE PUMP ----------------
    def _poll_messages(self):
        try:
            while True:
                msg = self._messages.get_nowait()
                kind = msg[0]
                if kind == "info":
                    self._show_info(msg[1])
                elif kind == "error":
                    self._set_status(msg[1], RED)
                elif kind == "item":
                    row = self._rows.get(msg[1])
                    if row:
                        row.item = self._items[msg[1]]
                        row.refresh()
                elif kind == "status":
                    self._set_status(msg[1], msg[2])
        except queue.Empty:
            pass
        self.after(120, self._poll_messages)

    def _show_info(self, info: dict):
        self._current_info = info
        title = info.get("title") or "Untitled"
        self.title_label.configure(text=title)
        duration = format_duration(info.get("duration"))
        uploader = info.get("uploader") or "Unknown channel"
        self.uploader_label.configure(text=f"{uploader}   ·   {duration}")
        license_text = (info.get("license") or "").strip()
        if license_text:
            is_cc = "creative commons" in license_text.lower()
            self.license_label.configure(
                text=license_text[:80],
                fg_color="#123B2E" if is_cc else "#3B3012",
                text_color=GREEN if is_cc else AMBER,
            )
        else:
            self.license_label.configure(text="License unknown — check rights before downloading",
                                         fg_color="#3B3012", text_color=AMBER)
        thumb_url = info.get("thumbnail")
        if thumb_url:
            threading.Thread(target=self._load_thumbnail, args=(thumb_url,), daemon=True).start()
        self.info_card.grid()
        self.download_btn.configure(state="normal", text="⬇  Download video")
        self._set_status("Video info fetched. Choose a quality and press Download.", GREEN)

    def _load_thumbnail(self, url: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            import io
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail((352, 198))
            self._thumb_ref = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.after(0, lambda: self.thumb_label.configure(image=self._thumb_ref, text=""))
        except Exception:
            pass


def main():
    ctk.set_appearance_mode("dark")
    app = NeuroLoadApp()
    app.mainloop()


if __name__ == "__main__":
    main()
