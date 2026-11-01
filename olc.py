"""Test setinde ölçüm: sınıflama doğruluğu, denetimden geçme oranı; elle inceleme için yanıtları yazar.

Kullanım: python olc.py [çıktı_adı]   -> test/sonuc_<ad>.json
         SET=ayrik.json python olc.py ayrik   (ayrık set; bu sete bakıp istem değiştirilmez)
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from api import harcanan
from cekirdek import yanitla

KOK = Path(__file__).parent / "test"
ad = sys.argv[1] if len(sys.argv) > 1 else "son"
veri = json.loads((KOK / os.environ.get("SET", "set.json")).read_text(encoding="utf-8"))
basla = harcanan()

with ThreadPoolExecutor(6) as h:
    sonuclar = list(h.map(lambda y: yanitla(veri["isletmeler"][y["isletme"]], y["metin"]), veri["yorumlar"]))

kayit = []
duygu = aciliyet = hazir = ilk = 0
for y, s in zip(veri["yorumlar"], sonuclar):
    duygu += s.get("duygu") == y["duygu"]
    aciliyet += s.get("aciliyet") == y["aciliyet"]
    hazir += s["durum"] == "hazir"
    ilk += s["durum"] == "hazir" and s["deneme"] == 1
    kayit.append({"id": y["id"], "yorum": y["metin"], "tuzak": y.get("tuzak", ""), "beklenen": [y["duygu"], y["aciliyet"]],
                  "bulunan": [s.get("duygu"), s.get("aciliyet")], "durum": s["durum"], "deneme": s["deneme"],
                  "yanit": s.get("yanit"), "gecmis": s["gecmis"]})
n = len(kayit)
ozet = {"n": n, "duygu": duygu, "aciliyet": aciliyet, "hazir": hazir, "ilk_denemede": ilk,
        "maliyet_usd": round(harcanan() - basla, 4)}
(KOK / f"sonuc_{ad}.json").write_text(json.dumps({"ozet": ozet, "kayit": kayit}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
print(json.dumps(ozet, ensure_ascii=False))
for k in kayit:
    isaret = "✓" if k["durum"] == "hazir" else "!"
    print(f"\n#{k['id']} {isaret} d{k['deneme']} beklenen {k['beklenen']} bulunan {k['bulunan']}")
    print(f"  YORUM: {k['yorum'][:120]}")
    if k["tuzak"]:
        print(f"  TUZAK: {k['tuzak']}")
    print(f"  YANIT: {k['yanit']}")
    for g in k["gecmis"]:
        if g["sorunlar"]:
            print(f"  [deneme {g['deneme']} sorunları] {'; '.join(g['sorunlar'])}")
