# -*- coding: utf-8 -*-
"""
vektor_web.py — lokalni web prozor za tok Pillow + VTracer + Potrace + Scour.

Pokreni:  py vektor_web.py        (ili dupli klik na POKRENI-WEB.bat)
Otvara se http://127.0.0.1:8765 u pregledniku. Sve ostaje na računaru.

Stranica je ista kao ../Alati-PNG-u-SVG.html (jedan dizajn za sajt, artifact i lokalni prozor);
ovdje se servira bez prijave i sa oznakom da obradu radi Python, ne motor u pregledniku.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OVDJE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, OVDJE)
import vektorizuj as V  # noqa: E402

PORT = int(os.environ.get("VEKTOR_PORT", "8765"))
IZLAZ = os.path.join(OVDJE, "izlaz")
UI_PUTANJE = [os.path.join(OVDJE, "ui.html"), os.path.join(os.path.dirname(OVDJE), "Alati-PNG-u-SVG.html")]


def ucitaj_ui() -> str:
    for p in UI_PUTANJE:
        if os.path.isfile(p):
            s = open(p, encoding="utf-8").read()
            # bez prijave sajta i bez linkova ka sajtu
            s = re.sub(r"<script>try\{if\(localStorage\.getItem\('ipp-auth'\).*?</script>", "", s, count=1, flags=re.S)
            s = s.replace('<a class="btn sm" href="index.html">← Početna</a>', "")
            s = re.sub(r'<button type="button" class="btn sm danger"[^>]*>Odjava</button>', "", s)
            s = s.replace('<link rel="icon" href="grb.jpg">', "")
            # oznaka lokalnog režima prije svih skripti
            s = s.replace("<title>", "<script>window.__LOCAL__=true;</script><title>", 1)
            return s
    return ("<h1>Nedostaje stranica</h1><p>Očekujem <code>vektor/ui.html</code> ili "
            "<code>Alati-PNG-u-SVG.html</code> u nadfolderu (kloniraj cijeli repozitorij).</p>")


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):  # tiši ispis
        if "/api/" in (a[0] if a else ""):
            sys.stdout.write("  " + (fmt % a) + "\n")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            self._send(200, ucitaj_ui().encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            self._send(200, json.dumps(dict(
                vtracer=V.vtracer is not None, potrace=V.potrace is not None and V.np is not None,
                scour=V._scour is not None, izlaz=IZLAZ)).encode(), "application/json")
        else:
            self._send(404, b"404", "text/plain")

    def do_POST(self):
        if self.path != "/api/convert":
            self._send(404, b"404", "text/plain"); return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            raw = base64.b64decode(req["data"])
            img = V.Image.open(io.BytesIO(raw))
            preset = req.get("preset") or "auto"
            if preset not in V.PRESETS:
                preset = "auto"

            def cijeli(k):
                v = req.get(k)
                return int(v) if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()) else None

            svg, info = V.vektorizuj_sliku(
                img, preset, colors=cijeli("colors"), speckle=cijeli("speckle"), denoise=cijeli("denoise"),
                bg=req.get("bg", "none"), bg_thresh=cijeli("bg_thresh") or 225, engine=req.get("engine", "auto"))
            info["paths"] = svg.count("<path")
            info["segments"] = len(re.findall(r"[LQCZ]", svg))
            info["colors"] = len(set(re.findall(r'fill="(#[0-9a-fA-F]{3,8})"', svg))) or None
            # sačuvaj i u izlazni folder, da se ne mora klikati "Preuzmi"
            os.makedirs(IZLAZ, exist_ok=True)
            ime = os.path.splitext(os.path.basename(req.get("name") or "slika"))[0] + ".svg"
            with open(os.path.join(IZLAZ, ime), "w", encoding="utf-8") as f:
                f.write(svg)
            info["saved"] = os.path.join(IZLAZ, ime)
            self._send(200, json.dumps(dict(svg=svg, info=info)).encode("utf-8"), "application/json")
        except Exception as e:  # noqa: BLE001
            self._send(200, json.dumps(dict(error=f"{type(e).__name__}: {e}")).encode("utf-8"), "application/json")


def main() -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Vektor · lokalni prozor na {url}")
    print(f"Motori: VTracer {'✔' if V.vtracer else '✘'}  Potrace {'✔' if V.potrace and V.np else '✘'}  Scour {'✔' if V._scour else '✘'}")
    print(f"SVG fajlovi se snimaju u: {IZLAZ}\nZatvori ovaj prozor (Ctrl+C) kad završiš.")
    if os.environ.get("VEKTOR_NO_BROWSER") != "1":
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
