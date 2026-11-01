"""Meta Model API istemcisi (OpenAI uyumlu) ve harcama sayacı.

Ücretsiz kredide gönderilen içerik Meta'nın ürün geliştirmesinde kullanılabilir:
yorumlardaki kişi adları gönderilmeden önce maskelenir (cekirdek.maskele).
"""
import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://api.meta.ai/v1/chat/completions"
MODEL = "muse-spark-1.3-contributor"
FIYAT = {"muse-spark-1.3-contributor": (0.10, 0.20), "muse-spark-1.3": (1.25, 4.25)}  # $ / 1M token
TAVAN = float(os.environ.get("YORUM_TAVAN", "20"))  # bu projenin toplam harcama sınırı, $
SAYAC = Path(__file__).parent / "kayitlar" / "butce.jsonl"
_kilit = threading.Lock()


def _anahtar():
    if os.environ.get("META_MODEL_API_KEY"):
        return os.environ["META_MODEL_API_KEY"]
    for satir in open(Path.home() / ".pflow-anahtarlar.env", encoding="utf-8"):
        if satir.startswith("META_MODEL_API_KEY="):
            return satir.split("=", 1)[1].strip().strip('"')
    raise SystemExit("META_MODEL_API_KEY bulunamadı")


def harcanan():
    if not SAYAC.exists():
        return 0.0
    return sum(json.loads(s)["usd"] for s in SAYAC.read_text(encoding="utf-8").splitlines() if s)


def sor(icerik, model=MODEL, max_tokens=8000, json_mod=False, etiket=""):
    """icerik: str ya da OpenAI biçiminde içerik listesi. Cevap metnini döndürür."""
    if harcanan() >= TAVAN:
        raise SystemExit(f"harcama tavanı {TAVAN} $ doldu")
    govde = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": icerik}]}
    if json_mod:
        govde["response_format"] = {"type": "json_object"}
    istek = urllib.request.Request(URL, data=json.dumps(govde).encode(), headers={
        "Authorization": "Bearer " + _anahtar(), "Content-Type": "application/json"})
    for deneme in range(5):
        try:
            with urllib.request.urlopen(istek, timeout=600) as r:
                j = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and deneme < 4:
                time.sleep(10 * (deneme + 1))
                continue
            raise RuntimeError(f"{e.code} {e.read()[:300]!r}")
        except (urllib.error.URLError, TimeoutError):
            if deneme == 4:
                raise
            time.sleep(10 * (deneme + 1))
    u = j.get("usage", {})
    gir, cik = FIYAT[model]
    usd = (u.get("prompt_tokens", 0) * gir + u.get("completion_tokens", 0) * cik) / 1e6
    with _kilit:
        SAYAC.parent.mkdir(exist_ok=True)
        with open(SAYAC, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": int(time.time()), "model": model, "etiket": etiket,
                                "gir": u.get("prompt_tokens"), "cik": u.get("completion_tokens"),
                                "usd": round(usd, 6)}) + "\n")
    return j["choices"][0]["message"]["content"] or ""


def resim(veri, tur="png"):
    return {"type": "image_url", "image_url": {"url": f"data:image/{tur};base64," + base64.b64encode(veri).decode()}}
