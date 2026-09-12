# -*- coding: utf-8 -*-
"""Jednostavan prozor oko vektorizuj.py (Tkinter je dio Pythona, ništa dodatno)."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vektorizuj as V  # noqa: E402


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PNG / JPEG → SVG  (VTracer + Potrace)")
        self.geometry("720x560")
        self.fajlovi = []
        pad = dict(padx=8, pady=4)

        top = ttk.Frame(self); top.pack(fill="x", **pad)
        ttk.Button(top, text="📂 Izaberi slike…", command=self.izaberi).pack(side="left")
        ttk.Button(top, text="📁 Izaberi folder…", command=self.izaberi_folder).pack(side="left", padx=6)
        self.lbl = ttk.Label(top, text="nema izabranih slika"); self.lbl.pack(side="left", padx=8)

        opt = ttk.LabelFrame(self, text="Podešavanja"); opt.pack(fill="x", **pad)
        self.preset = tk.StringVar(value="auto"); self.bg = tk.StringVar(value="white")
        self.colors = tk.StringVar(value=""); self.speckle = tk.StringVar(value="")
        self.denoise = tk.StringVar(value=""); self.out = tk.StringVar(value="")
        r = 0
        ttk.Label(opt, text="Preset").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(opt, textvariable=self.preset, values=sorted(V.PRESETS), state="readonly", width=12).grid(row=r, column=1, sticky="w")
        ttk.Label(opt, text="auto = sam prepozna crno-bijelo · logo · ikona · foto · bw").grid(row=r, column=2, columnspan=3, sticky="w")
        r += 1
        ttk.Label(opt, text="Pozadina uz rub").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(opt, textvariable=self.bg, values=["none", "white", "clear"], state="readonly", width=12).grid(row=r, column=1, sticky="w")
        ttk.Label(opt, text="white = izbijeli JPEG oreol · clear = providno · none = ne diraj").grid(row=r, column=2, columnspan=3, sticky="w")
        r += 1
        ttk.Label(opt, text="Broj boja").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(opt, textvariable=self.colors, width=6).grid(row=r, column=1, sticky="w")
        ttk.Label(opt, text="Mrlje px²").grid(row=r, column=2, sticky="e")
        ttk.Entry(opt, textvariable=self.speckle, width=6).grid(row=r, column=3, sticky="w")
        ttk.Label(opt, text="Šum (0/3/5)").grid(row=r, column=4, sticky="e")
        ttk.Entry(opt, textvariable=self.denoise, width=6).grid(row=r, column=5, sticky="w", padx=(0, 8))
        r += 1
        ttk.Label(opt, text="Izlazni folder").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(opt, textvariable=self.out, width=48).grid(row=r, column=1, columnspan=4, sticky="we")
        ttk.Button(opt, text="…", width=3, command=self.izaberi_out).grid(row=r, column=5, sticky="w")

        self.btn = ttk.Button(self, text="⚡ Pretvori u SVG", command=self.pokreni); self.btn.pack(**pad)
        self.log = tk.Text(self, height=18, wrap="word"); self.log.pack(fill="both", expand=True, **pad)
        self.pisi(f"VTracer {'✔' if V.vtracer else '✘ (py -m pip install vtracer)'}   "
                  f"Potrace {'✔' if V.potrace and V.np else '✘ (py -m pip install potracer numpy)'}   "
                  f"Scour {'✔' if V._scour else '✘ (opciono)'}\n")

    def pisi(self, s):
        self.log.insert("end", s); self.log.see("end")

    def izaberi(self):
        f = filedialog.askopenfilenames(filetypes=[("Slike", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff"), ("Sve", "*.*")])
        if f:
            self.fajlovi = list(f); self.lbl.config(text=f"{len(f)} slika")

    def izaberi_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.fajlovi = V.skupi_ulaze([d]); self.lbl.config(text=f"{len(self.fajlovi)} slika iz foldera")

    def izaberi_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out.set(d)

    def pokreni(self):
        if not self.fajlovi:
            self.pisi("Prvo izaberi slike.\n"); return
        self.btn.config(state="disabled")
        threading.Thread(target=self._radi, daemon=True).start()

    def _radi(self):
        def broj(v):
            v = v.get().strip(); return int(v) if v.isdigit() else None
        import io, contextlib
        for f in self.fajlovi:
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    V.vektorizuj(f, self.out.get() or None, self.preset.get(), bg=self.bg.get(),
                                 colors=broj(self.colors), speckle=broj(self.speckle), denoise=broj(self.denoise))
            except Exception as e:
                buf.write(f"  GREŠKA: {e}\n")
            self.after(0, self.pisi, buf.getvalue() + "\n")
        self.after(0, lambda: (self.btn.config(state="normal"), self.pisi("Gotovo.\n\n")))


if __name__ == "__main__":
    App().mainloop()
