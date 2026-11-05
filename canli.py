"""Herkese açık demo: sunucu.py'nin arayüzü ve API'si, kötüye kullanıma karşı sınırlarla.
Caddy önde HTTPS'i yapar ve isteği 127.0.0.1:8790'a iletir.

Sınırlar (ortam değişkeniyle değiştirilebilir):
  CANLI_IP_GUN     bir IP'nin günde işleyebileceği yorum sayısı      (varsayılan 15)
  CANLI_GUN        tüm ziyaretçiler için günlük yorum sayısı         (varsayılan 400)
  CANLI_ISTEK_YORUM tek istekte en fazla yorum                       (varsayılan 3)
  YORUM_TAVAN      bu sunucudaki toplam Meta harcaması, $ (api.py)   (varsayılan burada 5)
Yorumlar ve işletme bilgileri kaydedilmez; yalnızca IP'nin kısaltılmış özeti gün içinde sayılır.
    python canli.py"""
import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

os.environ.setdefault("YORUM_TAVAN", "5")

import sunucu  # noqa: E402  (YORUM_TAVAN api.py yüklenmeden önce ayarlanmalı)
from api import harcanan, TAVAN  # noqa: E402

IP_GUN = int(os.environ.get("CANLI_IP_GUN", "15"))
GUN = int(os.environ.get("CANLI_GUN", "400"))
ISTEK_YORUM = int(os.environ.get("CANLI_ISTEK_YORUM", "3"))
TR = timezone(timedelta(hours=3))
_kilit = threading.Lock()
_sayac = {"gun": None, "toplam": 0, "ip": {}}

sunucu.YORUM_UST = min(getattr(sunucu, "YORUM_UST", ISTEK_YORUM), ISTEK_YORUM)


def _ip_ozet(isleyici):
    ip = (isleyici.headers.get("X-Forwarded-For") or isleyici.client_address[0]).split(",")[0].strip()
    return hashlib.sha256(("yorum-demo:" + ip).encode()).hexdigest()[:16]


def _hak_al(ozet, adet):
    """adet kadar yorum hakkı ayırır; yetmezse kalan hakkı ve nedeni döndürür."""
    with _kilit:
        bugun = datetime.now(TR).date().isoformat()
        if _sayac["gun"] != bugun:
            _sayac.update({"gun": bugun, "toplam": 0, "ip": {}})
        kisi = _sayac["ip"].get(ozet, 0)
        if kisi + adet > IP_GUN:
            return False, f"Bugünlük deneme hakkınız doldu ({IP_GUN} yorum). Yarın yeniden deneyebilirsiniz."
        if _sayac["toplam"] + adet > GUN:
            return False, "Demo bugün için günlük sınırına ulaştı. Yarın yeniden deneyebilirsiniz."
        _sayac["ip"][ozet] = kisi + adet
        _sayac["toplam"] += adet
        return True, None


class CanliIsleyici(sunucu.Isleyici):
    def do_GET(self):
        if self.path == "/durum":
            with _kilit:
                kisi = _sayac["ip"].get(_ip_ozet(self), 0) if _sayac["gun"] == datetime.now(TR).date().isoformat() else 0
            return self._gonder(200, {"kalan": max(0, IP_GUN - kisi), "istek_basina": ISTEK_YORUM,
                                      "butce_dolu": harcanan() >= TAVAN})
        if self.path in ("/", "/index.html"):
            html = (sunucu.KOK / "index.html").read_text(encoding="utf-8")
            not_ = (f'<p class="demo-not" style="font-size:.9rem;opacity:.8;margin:6px 0 0">Herkese açık demo: tek seferde en fazla '
                    f'{ISTEK_YORUM} yorum, günde {IP_GUN} yorum. Yazdıklarınız kaydedilmez. '
                    f'<a href="https://github.com/birtohum/yorum-yanitlayici">Kaynak kod</a></p>')
            html = html.replace('<div id="hata"', not_ + '\n    <div id="hata"', 1)
            html = html.replace("(en fazla 30)", f"(demoda ilk {ISTEK_YORUM} yorum işlenir)")
            return self._gonder(200, html.encode("utf-8"), "text/html; charset=utf-8")
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/yanitla":
            return self._gonder(404, {"hata": "bulunamadı"})
        uzunluk = int(self.headers.get("Content-Length", 0) or 0)
        if uzunluk > 20000:
            return self._gonder(413, {"hata": "istek çok büyük"})
        govde = self.rfile.read(uzunluk)
        try:
            yorumlar = [y for y in json.loads(govde).get("yorumlar", []) if str(y).strip()][:ISTEK_YORUM]
        except (ValueError, AttributeError):
            return self._gonder(400, {"hata": "istek okunamadı"})
        if harcanan() >= TAVAN:
            return self._gonder(503, {"hata": "Demo bütçesi doldu; kod GitHub'da, kendi anahtarınızla çalıştırabilirsiniz."})
        tamam, neden = _hak_al(_ip_ozet(self), max(1, len(yorumlar)))
        if not tamam:
            return self._gonder(429, {"hata": neden})
        # Gövde zaten okundu: üst sınıfın okuyabilmesi için yeniden besle
        import io
        self.rfile = io.BytesIO(govde)
        return super().do_POST()


if __name__ == "__main__":
    print(f"canlı demo: http://127.0.0.1:{sunucu.PORT}  (IP/gün {IP_GUN}, gün {GUN}, istek {ISTEK_YORUM}, tavan {TAVAN} $)")
    ThreadingHTTPServer(("127.0.0.1", sunucu.PORT), CanliIsleyici).serve_forever()
