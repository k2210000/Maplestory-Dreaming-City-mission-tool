from __future__ import annotations
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import List, Dict, Optional

try:
    from PIL import Image, ImageTk
except ImportError as e:
    raise SystemExit("This app requires Pillow. Install with `pip install pillow`.\n" + str(e))

APP_TITLE = "午夜追擊者-小工具"
OPTIONS_JSON = "options.json"
CELL_WIDTH = 220   # 固定格子寬 (像素)
CELL_HEIGHT = 220  # 固定格子高 (像素)

@dataclass
class Option:
    id: int
    name: str
    image_path: str

class ImageCache:
    def __init__(self):
        self._orig_cache: Dict[str, Image.Image] = {}
        self._thumb_cache: Dict[str, ImageTk.PhotoImage] = {}

    def _load_orig(self, path: str) -> Optional[Image.Image]:
        if not path or not os.path.exists(path):
            return None
        if path in self._orig_cache:
            return self._orig_cache[path]
        try:
            img = Image.open(path).convert("RGBA")
            self._orig_cache[path] = img
            return img
        except Exception:
            return None

    def get(self, path: str, size: Optional[tuple[int,int]] = None) -> Optional[ImageTk.PhotoImage]:
        """Return a Tk image resized to `size` (w,h) using contain behavior."""
        orig = self._load_orig(path)
        if orig is None:
            return None
        key = f"{path}|{size}" if size else f"{path}|orig"
        if key in self._thumb_cache:
            return self._thumb_cache[key]
        img = orig.copy()
        if size:
            img.thumbnail(size, Image.LANCZOS)  # 等比縮放：長邊貼齊，短邊留白
        tk_img = ImageTk.PhotoImage(img)
        self._thumb_cache[key] = tk_img
        return tk_img

class NineGridApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)

        self.image_cache = ImageCache()

        self.options: List[Option] = []
        self.option_names: List[str] = []
        self.name_to_option: Dict[str, Option] = {}

        self._build_ui()
        self._ensure_sample_options()
        self.load_options_file(OPTIONS_JSON)

        # 啟動後依元件需求尺寸自動設定視窗大小，確保一開啟就能完整看到九宮格
        self.after(0, self._autosize_to_content)

    def _autosize_to_content(self):
        """根據目前元件的需求尺寸自動設定視窗大小，確保一開啟就能完整看到九宮格。"""
        try:
            self.update_idletasks()
            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            # 加上些許邊距，並避免超出螢幕
            w = min(req_w + 20, max(640, screen_w - 80))
            h = min(req_h + 20, max(480, screen_h - 120))
            self.geometry(f"{w}x{h}")
            # 設最小尺寸避免縮到看不到格子
            self.minsize(req_w, req_h)
        except Exception:
            pass

    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(top, text="清空欄位", command=self.on_clear_all).pack(side=tk.LEFT, padx=(8,0))

        self.status_var = tk.StringVar(value="就緒。")
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT)

        grid_frame = ttk.Frame(self, padding=10)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        self.cells: List[Dict[str, object]] = []
        position_names = [["左上", "中上", "右上"],
                          ["左中", "中",   "右中"],
                          ["左下", "中下", "右下"]]
        for r in range(3):
            for c in range(3):
                cell = self._create_cell(grid_frame, r, c, position_names[r][c])
                self.cells.append(cell)

    def _create_cell(self, parent, r, c, title):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

        # 固定尺寸的圖片容器
        img_container = tk.Frame(frame, width=CELL_WIDTH, height=CELL_HEIGHT)
        img_container.pack()
        img_container.pack_propagate(False)  # 內部元件不影響容器大小

        img_label = ttk.Label(img_container)
        img_label.place(relx=0.5, rely=0.5, anchor="center")  # 置中顯示

        name_var = tk.StringVar()
        combo = ttk.Combobox(frame, textvariable=name_var, state="readonly")
        combo.pack(fill=tk.X, pady=(8,0))
        combo.bind("<<ComboboxSelected>>", lambda e, iv=name_var, il=img_label: self._on_cell_change(iv, il))

        return {"frame": frame, "img_label": img_label, "name_var": name_var, "combo": combo}

    def _ensure_sample_options(self):
        if os.path.exists(OPTIONS_JSON):
            return
        os.makedirs("images", exist_ok=True)
        sample = [
            {"id": i+1, "name": f"Option {i+1}", "image": f"images/sample_{i+1}.png"} for i in range(9)
        ]
        from PIL import ImageDraw, ImageFont
        for i in range(9):
            path = f"images/sample_{i+1}.png"
            if not os.path.exists(path):
                img = Image.new("RGBA", (256, 256), (240, 240, 240, 255))
                try:
                    draw = ImageDraw.Draw(img)
                    font = ImageFont.load_default()
                    text = str(i+1)
                    tw, th = draw.textsize(text, font=font)
                    draw.text(((256-tw)//2, (256-th)//2), text, fill=(0,0,0,255), font=font)
                except Exception:
                    pass
                img.save(path)
        with open(OPTIONS_JSON, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)

    def load_options_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Options Failed", f"Could not read {path}:\n{e}")
            return
        try:
            options: List[Option] = []
            for item in raw:
                options.append(Option(id=int(item.get("id")), name=str(item.get("name")), image_path=str(item.get("image"))))
        except Exception as e:
            messagebox.showerror("Invalid Options Format", f"{path} is not valid.\n{e}")
            return

        self.options = options
        self.option_names = [o.name for o in self.options]
        self.name_to_option = {o.name: o for o in self.options}

        for cell in self.cells:
            combo: ttk.Combobox = cell["combo"]
            combo["values"] = self.option_names
            name_var: tk.StringVar = cell["name_var"]
            if name_var.get() not in self.option_names:
                name_var.set("")
            self._refresh_cell_image(cell)
        self.status_var.set(f"已載入選項：{os.path.basename(path)}")

    def _on_cell_change(self, name_var: tk.StringVar, img_label: ttk.Label):
        name = name_var.get()
        opt = self.name_to_option.get(name)
        if not opt:
            img_label.configure(image="")
            img_label.image = None
            return
        # 固定用 CELL_WIDTH/HEIGHT 做等比縮放，長邊貼齊容器
        target_size = (CELL_WIDTH, CELL_HEIGHT)
        tk_img = self.image_cache.get(opt.image_path, target_size)
        img_label.configure(image=tk_img)
        img_label.image = tk_img

    def _refresh_cell_image(self, cell: Dict[str, object]):
        name_var: tk.StringVar = cell["name_var"]
        img_label: ttk.Label = cell["img_label"]
        name = name_var.get()
        opt = self.name_to_option.get(name)
        tk_img = self.image_cache.get(opt.image_path, (CELL_WIDTH, CELL_HEIGHT)) if opt else None
        img_label.configure(image=tk_img if tk_img else "")
        img_label.image = tk_img

    def on_clear_all(self):
        for i in range(9):
            combo: ttk.Combobox = self.cells[i]["combo"]
            combo.set("")
            img_label: ttk.Label = self.cells[i]["img_label"]
            img_label.configure(image="")
            img_label.image = None
        self.status_var.set("已清空所有欄位。")

if __name__ == "__main__":
    app = NineGridApp()
    app.mainloop()
