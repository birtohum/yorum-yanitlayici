"""Yerel web arayüzü: python sunucu.py  ->  http://127.0.0.1:8790

POST /api/yanitla  {"isletme": {ad, tur, bilgiler, uslup}, "yorumlar": ["...", ...]}
"""
import json
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cekirdek import yanitla

KOK = Path(__file__).parent
PORT = 8790
YORUM_UST, YORUM_UZUNLUK, BILGI_UZUNLUK = 30, 2000, 4000


class Isleyici(BaseHTTPRequestHandler):
    def _gonder(self, kod, govde, tur="application/json; charset=utf-8"):
        veri = govde if isinstance(govde, bytes) else json.dumps(govde, ensure_ascii=False).encode()
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._gonder(200, (KOK / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/ornek.json":
            return self._gonder(200, (KOK / "test" / "set.json").read_bytes())
        self._gonder(404, {"hata": "bulunamadı"})

    def do_POST(self):
        if self.path != "/api/yanitla":
            return self._gonder(404, {"hata": "bulunamadı"})
        try:
            istek = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            isl = istek["isletme"]
            isletme = {"ad": str(isl.get("ad", ""))[:100], "tur": str(isl.get("tur", ""))[:100],
                       "bilgiler": str(isl.get("bilgiler", ""))[:BILGI_UZUNLUK],
                       "uslup": str(isl.get("uslup", "") or "saygılı")[:200]}
            yorumlar = [str(y)[:YORUM_UZUNLUK] for y in istek["yorumlar"] if str(y).strip()][:YORUM_UST]
        except (ValueError, KeyError, TypeError):
            return self._gonder(400, {"hata": "istek okunamadı"})
        if not isletme["ad"] or not isletme["bilgiler"].strip() or not yorumlar:
            return self._gonder(400, {"hata": "işletme adı, bilgiler ve en az bir yorum gerekli"})
        try:
            with ThreadPoolExecutor(6) as h:
                sonuclar = list(h.map(lambda y: yanitla(isletme, y), yorumlar))
        except SystemExit as e:  # harcama tavanı
            return self._gonder(503, {"hata": str(e)})
        except Exception as e:
            return self._gonder(502, {"hata": f"model hatası: {e}"[:300]})
        self._gonder(200, {"sonuclar": [{"yorum": y} | {k: s.get(k) for k in (
            "dil", "duygu", "aciliyet", "aciliyet_nedeni", "konular", "ozet", "yanit", "durum", "sorunlar", "deneme")}
            for y, s in zip(yorumlar, sonuclar)]})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici).serve_forever()
