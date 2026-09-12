# -*- coding: utf-8 -*-
"""
vektorizuj.py — kombinovani tok PNG/JPEG → SVG (sve open-source, bez pretplate)

    Pillow (priprema)  →  VTracer (boje)  ili  Potrace (crno-bijelo)  →  Scour (čišćenje SVG-a)

Primjeri:
    py vektorizuj.py grb.png
    py vektorizuj.py grb.jpg --preset logo --bg white
    py vektorizuj.py pecat.jpg --preset bw --bg clear
    py vektorizuj.py "slicice ikonice" --preset ikona --out izlaz
    py vektorizuj.py *.png --colors 8 --scale 2

Biblioteke (pip install -r requirements.txt):
    pillow    obavezno   – učitavanje, uvećanje, čišćenje šuma, pozadina
    vtracer   obavezno   – vektorizacija u boji (Rust motor, MIT)
    potracer  opciono    – pravi Potrace algoritam za crno-bijelo (čist Python port)
    numpy     opciono    – treba potraceru
    scour     opciono    – skraćivanje SVG-a (manji fajl, isti izgled)
Ako potracer/numpy nema, crno-bijelo ide kroz VTracer u binarnom režimu.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile
import time

# ---------------------------------------------------------------- opcione zavisnosti
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    print("Nedostaje Pillow. Pokreni:  py -m pip install pillow")
    sys.exit(1)

try:
    import vtracer
except ImportError:  # pragma: no cover
    vtracer = None

try:
    import numpy as np
    import potrace  # paket 'potracer' se uvozi kao 'potrace'
except ImportError:  # pragma: no cover
    np = None
    potrace = None

try:
    from scour import scour as _scour
except ImportError:  # pragma: no cover
    _scour = None


# ---------------------------------------------------------------- preseti
PRESETS = {
    # colors = broj boja (VTracer color_precision se izvodi iz toga), speckle = mrlje u px²,
    # corner = prag ugla (manje = više oštrih uglova), denoise = medijan filter (0/3/5)
    "logo":  dict(mode="color", colors=16, speckle=8,  corner=60, denoise=0, length=3.5, precision=3),
    "ikona": dict(mode="color", colors=24, speckle=12, corner=70, denoise=3, length=4.0, precision=3),
    "foto":  dict(mode="color", colors=48, speckle=32, corner=80, denoise=3, length=6.0, precision=2),
    "bw":    dict(mode="bw",    colors=2,  speckle=6,  corner=60, denoise=0, length=3.5, precision=3),
    "auto":  dict(mode="auto",  colors=16, speckle=8,  corner=60, denoise=0, length=3.5, precision=3),
}
FORMATI = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")


def log(msg: str) -> None:
    print("  " + msg, flush=True)


# ---------------------------------------------------------------- 1. priprema (Pillow)
def pripremi(img: Image.Image, scale: float | None, denoise: int, bg: str, bg_thresh: int) -> Image.Image:
    """Uvećanje, čišćenje šuma i obrada svijetle pozadine koja dodiruje rub."""
    img = ImageOps.exif_transpose(img).convert("RGBA")
    w, h = img.size

    # uvećanje: tracer daje glađe krive na većoj slici; auto = do ~1500 px po dužoj strani
    if scale is None:
        dulja = max(w, h)
        scale = 1.0 if dulja >= 1400 else min(4.0, 1500 / dulja)
    if abs(scale - 1.0) > 0.01:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        log(f"uvećano ×{scale:.2f} → {img.size[0]}×{img.size[1]} px")

    # šum (JPEG artefakti): medijan filter čuva ivice bolje od običnog zamućenja
    if denoise and denoise >= 3:
        rgb = img.convert("RGB").filter(ImageFilter.MedianFilter(size=denoise if denoise % 2 else denoise + 1))
        img = Image.merge("RGBA", (*rgb.split(), img.split()[3]))
        log(f"medijan filter {denoise}")

    # pozadina: flood-fill iz sva četiri ugla sa tolerancijom (samo ono što je spojeno s rubom)
    if bg in ("white", "clear"):
        fill = (255, 255, 255, 255) if bg == "white" else (0, 0, 0, 0)
        tol = (255 - bg_thresh) * 3    # Pillow sabira razlike po kanalima; prag 225 → 30 po kanalu
        W, H = img.size
        for xy in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1), (W // 2, 0), (W // 2, H - 1), (0, H // 2), (W - 1, H // 2)):
            px = img.getpixel(xy)
            if min(px[:3]) >= bg_thresh and px[3] > 0:
                ImageDraw.floodfill(img, xy, fill, thresh=tol)
        log("pozadina: " + ("izbijeljena" if bg == "white" else "uklonjena (providna)"))
    return img


def je_crno_bijela(img: Image.Image) -> bool:
    """Heuristika: ako je ≥ 96 % piksela vrlo tamno ili vrlo svijetlo, slika je praktično dvobojna."""
    g = img.convert("L").resize((200, 200))
    hist = g.histogram()
    ukupno = sum(hist)
    tamno = sum(hist[:60]); svijetlo = sum(hist[196:])
    zasic = img.convert("RGB").convert("HSV").resize((200, 200)).split()[1].histogram()
    sivo = sum(zasic[:40]) / ukupno
    return (tamno + svijetlo) / ukupno >= 0.96 and sivo >= 0.9


# ---------------------------------------------------------------- 2a. boje (VTracer)
def vtracer_svg(img: Image.Image, p: dict, mode: str) -> str:
    if vtracer is None:
        raise RuntimeError("Nedostaje vtracer. Pokreni:  py -m pip install vtracer")
    # color_precision: broj značajnih bitova po kanalu (1–8). 16 boja ≈ 4–5 bita, 48 ≈ 6.
    colors = max(2, int(p["colors"]))
    cp = 3 if colors <= 4 else 4 if colors <= 8 else 5 if colors <= 24 else 6 if colors <= 64 else 7
    layer_diff = 48 if colors <= 4 else 32 if colors <= 8 else 20 if colors <= 24 else 12
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.png"); dst = os.path.join(td, "out.svg")
        img.save(src, "PNG")
        vtracer.convert_image_to_svg_py(
            src, dst,
            colormode="binary" if mode == "bw" else "color",
            hierarchical="stacked",          # slojevi jedan preko drugog → nema šavova
            mode="spline",                   # Bezier krive
            filter_speckle=int(p["speckle"]),
            color_precision=cp,
            layer_difference=layer_diff,
            corner_threshold=int(p["corner"]),
            length_threshold=float(p["length"]),
            max_iterations=10,
            splice_threshold=45,
            path_precision=int(p["precision"]),
        )
        with open(dst, "r", encoding="utf-8") as f:
            return f.read()


# ---------------------------------------------------------------- 2b. crno-bijelo (Potrace)
def otsu_prag(hist: list[int]) -> int:
    ukupno = sum(hist); suma = sum(i * h for i, h in enumerate(hist))
    sb, wb, best, lo, hi = 0.0, 0, -1.0, 128, 128
    for t in range(256):
        wb += hist[t]
        if wb == 0:
            continue
        wf = ukupno - wb
        if wf == 0:
            break
        sb += t * hist[t]
        mb = sb / wb; mf = (suma - sb) / wf
        v = wb * wf * (mb - mf) ** 2
        if v > best + 1e-9:
            best, lo, hi = v, t, t
        elif abs(v - best) <= 1e-9:
            hi = t                      # plato jednakih vrijednosti → uzmi sredinu
    return (lo + hi) // 2 + 1


def potrace_svg(img: Image.Image, p: dict, boja: str = "#000000") -> str:
    """Pravi Potrace (kroz 'potracer'): najbolji rezultat za pečate, potpise, skenirane crteže."""
    if potrace is None or np is None:
        raise RuntimeError("Nedostaje potracer/numpy — koristi se VTracer binarni režim.")
    # providno → bijelo, pa u sivo i Otsu prag
    podloga = Image.new("RGBA", img.size, (255, 255, 255, 255))
    podloga.alpha_composite(img)
    g = podloga.convert("L")
    prag = otsu_prag(g.histogram())
    bitmap = np.array(g) < prag                          # True = crno
    bm = potrace.Bitmap(bitmap)
    path = bm.trace(turdsize=int(p["speckle"]), turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
                    alphamax=1.0, opticurve=True, opttolerance=0.2)
    w, h = img.size
    d = []
    for curve in path:
        s = curve.start_point
        d.append(f"M{s.x:.{p['precision']}f} {s.y:.{p['precision']}f}")
        for seg in curve:
            e = seg.end_point
            if seg.is_corner:
                c = seg.c
                d.append(f"L{c.x:.2f} {c.y:.2f} L{e.x:.2f} {e.y:.2f}")
            else:
                c1, c2 = seg.c1, seg.c2
                d.append(f"C{c1.x:.2f} {c1.y:.2f} {c2.x:.2f} {c2.y:.2f} {e.x:.2f} {e.y:.2f}")
        d.append("Z")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'
            f'<path fill="{boja}" fill-rule="evenodd" d="{" ".join(d)}"/>\n</svg>')


# ---------------------------------------------------------------- 3. čišćenje (Scour)
def ocisti(svg: str) -> str:
    if _scour is None:
        return svg
    opts = _scour.sanitizeOptions()
    opts.remove_metadata = True
    opts.strip_comments = True
    opts.strip_xml_prolog = False
    opts.shorten_ids = True
    opts.digits = 3
    opts.indent_type = "none"
    try:
        return _scour.scourString(svg, opts)
    except Exception as e:  # pragma: no cover
        log(f"scour preskočen ({e})")
        return svg


# ---------------------------------------------------------------- glavni tok
def vektorizuj(putanja: str, out_dir: str | None, preset: str, **kw) -> str:
    p = dict(PRESETS[preset])
    for k in ("colors", "speckle", "corner"):
        if kw.get(k) is not None:
            p[k] = kw[k]
    t0 = time.time()
    print(f"\n▶ {os.path.basename(putanja)}")
    img = Image.open(putanja)
    img = pripremi(img, kw.get("scale"), kw.get("denoise") if kw.get("denoise") is not None else p["denoise"],
                   kw.get("bg", "none"), kw.get("bg_thresh", 225))

    mode = p["mode"]
    if mode == "auto":
        mode = "bw" if je_crno_bijela(img) else "color"
        log(f"auto → {'crno-bijelo' if mode == 'bw' else 'boje'}")

    engine = kw.get("engine", "auto")
    if mode == "bw" and engine in ("auto", "potrace") and potrace is not None and np is not None:
        svg = potrace_svg(img, p); motor = "Potrace"
    else:
        svg = vtracer_svg(img, p, mode); motor = "VTracer" + (" (binarno)" if mode == "bw" else "")

    prije = len(svg)
    if not kw.get("no_optimize"):
        svg = ocisti(svg)
    izlaz_dir = out_dir or os.path.dirname(os.path.abspath(putanja))
    os.makedirs(izlaz_dir, exist_ok=True)
    izlaz = os.path.join(izlaz_dir, os.path.splitext(os.path.basename(putanja))[0] + ".svg")
    with open(izlaz, "w", encoding="utf-8") as f:
        f.write(svg)
    log(f"{motor} · {prije/1024:.1f} KB → {len(svg)/1024:.1f} KB · {time.time()-t0:.1f} s · {izlaz}")
    return izlaz


def skupi_ulaze(args: list[str]) -> list[str]:
    fajlovi: list[str] = []
    for a in args:
        if os.path.isdir(a):
            for f in sorted(os.listdir(a)):
                if f.lower().endswith(FORMATI):
                    fajlovi.append(os.path.join(a, f))
        else:
            m = glob.glob(a)
            fajlovi.extend(x for x in (m or [a]) if os.path.isfile(x) and x.lower().endswith(FORMATI))
    return fajlovi


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PNG/JPEG → SVG: Pillow + VTracer + Potrace + Scour")
    ap.add_argument("ulaz", nargs="+", help="slika, više slika, folder ili šablon (*.png)")
    ap.add_argument("--out", help="izlazni folder (podrazumijevano: pored slike)")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="auto")
    ap.add_argument("--engine", choices=["auto", "vtracer", "potrace"], default="auto")
    ap.add_argument("--colors", type=int, help="broj boja (npr. 8, 16, 32)")
    ap.add_argument("--speckle", type=int, help="ukloni mrlje manje od N px²")
    ap.add_argument("--corner", type=int, help="prag ugla 0–180 (manje = oštrije)")
    ap.add_argument("--scale", type=float, help="faktor uvećanja prije obrade (auto: do ~1500 px)")
    ap.add_argument("--denoise", type=int, help="medijan filter 0, 3 ili 5 (JPEG šum)")
    ap.add_argument("--bg", choices=["none", "white", "clear"], default="none", help="svijetla pozadina uz rub: izbijeli / ukloni")
    ap.add_argument("--bg-thresh", type=int, default=225, help="prag svjetline pozadine (160–250)")
    ap.add_argument("--no-optimize", action="store_true", help="preskoči scour")
    a = ap.parse_args(argv)

    fajlovi = skupi_ulaze(a.ulaz)
    if not fajlovi:
        print("Nema slika za obradu."); return 1
    print(f"Motori: Pillow ✔  VTracer {'✔' if vtracer else '✘ (pip install vtracer)'}  "
          f"Potrace {'✔' if potrace and np else '✘ (pip install potracer numpy)'}  Scour {'✔' if _scour else '✘'}")
    greske = 0
    for f in fajlovi:
        try:
            vektorizuj(f, a.out, a.preset, engine=a.engine, colors=a.colors, speckle=a.speckle, corner=a.corner,
                       scale=a.scale, denoise=a.denoise, bg=a.bg, bg_thresh=a.bg_thresh, no_optimize=a.no_optimize)
        except Exception as e:
            greske += 1; log(f"GREŠKA: {e}")
    print(f"\nGotovo: {len(fajlovi)-greske} od {len(fajlovi)}.")
    return 0 if greske == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
