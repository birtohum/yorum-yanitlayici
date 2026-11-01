"""Müşteri yorumunu sınıflar ve işletme adına yanıt taslağı yazar; taslağı denetler.

Temel kural: yanıt yalnızca işletmenin kendi girdiği bilgilere dayanır. İşletmenin vermediği bir söz
(indirim, iade, ikram, tazminat...) ya da uydurma bir bilgi (saat, telefon, ürün) içeren taslak
yeniden yazdırılır; yine geçemezse "elle düzenleyin" diye işaretlenir.
"""
import json
import re
from difflib import SequenceMatcher

from api import sor

KONULAR = ["urun-kalite", "fiyat", "hizmet-personel", "bekleme-gecikme", "hijyen-saglik", "rezervasyon-randevu",
           "ortam", "fatura-odeme", "hasar", "diger"]

# Söz kalıpları: yanıtta geçip işletme bilgisinde geçmiyorsa işletmenin vermediği bir söz sayılır.
SOZLER = {
    "indirim": r"indirim|kupon|discount|%\s?\d+",
    "iade": r"iade|geri öde|refund|money back",
    "bedava": r"bedava|ücretsiz|ikram|hediye|free|on the house|complimentary",
    "telafi": r"telafi|tazmin|karşılayacağız|karşılarız|ödeyeceğiz|öderiz|compensat",
    "ikame": r"ikame",
}
TELEFON = r"(?:\+?90\s?)?0?\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}"
EPOSTA = r"[\w.+-]+@[\w-]+\.[\w.]+"

YANIT_ISTEM = """Bir işletmenin internetteki müşteri yorumlarına işletme adına yanıt taslağı yazıyorsun.

İŞLETME: {ad} ({tur})
İŞLETMENİN KENDİ VERDİĞİ BİLGİLER (yalnızca bunlara dayanabilirsin):
\"\"\"{bilgiler}\"\"\"
ÜSLUP: {uslup}

MÜŞTERİ YORUMU:
\"\"\"{yorum}\"\"\"
{duzelt}
Kurallar:
1. İşletme bilgilerinde yazmayan hiçbir söz verme: indirim, iade, ücretsiz ürün/ikram, hediye, telafi, tazminat,
   ikame hizmet YOK. Bilgilerde olmayan saat, telefon, fiyat, ürün, kampanya uydurma.
2. Müşteri yanlış bir şey söylüyorsa (ör. olmayan bir eksiklik) bilgilere dayanarak kibarca düzelt.
3. Sağlık, güvenlik, hukuki tehdit ya da ayrımcılık iddiası varsa: aciliyet "yuksek". Bu durumda kusuru kabul etme,
   reddetme de; üzüldüğünü ve konunun ciddiye alındığını söyle, bilgilerdeki iletişim kanalından özelden ulaşmasını iste.
   Yüksek aciliyette olayın kendisiyle ilgili HİÇBİR bilgi verme (ürün içeriği, kural, garanti, prosedür):
   bu tür bir cümle müşteriyi suçlamak ya da kusuru kabul etmek gibi okunabilir.
4. Yorumdaki telefon, e-posta, tam ad gibi kişisel bilgileri yanıtta tekrar etme.
5. Hakarete karşılık verme, rakip işletmeden söz etme, alaycı yorumu övgü sanma.
6. Yorum hangi dilde yazıldıysa o dilde yanıt ver. En fazla 70 kelime. İmza atma.
7. Bilgileri kendi cümlelerinle, doğal ve akıcı biçimde aktar; bilgi metnini cümleye olduğu gibi yapıştırma
   (yanlış: "Dilerseniz Şikayet ve öneriler için: x@y adresinden yazın", doğru: "Dilerseniz x@y adresine yazın").
   Yalnızca yorumla ilgili bilgileri kullan; ilgisiz bilgi (saatler, politikalar) sıralama.
   Saat, telefon, e-posta ve tutarları bilgilerdeki yazımıyla aynen yaz.

Yalnızca şu JSON'u döndür:
{{"dil": "tr|en|...", "duygu": "olumlu|olumsuz|karisik|notr", "aciliyet": "normal|yuksek",
  "aciliyet_nedeni": "yuksekse kısa neden, değilse boş", "konular": [{konular}'den],
  "ozet": "yorumun 10 kelimelik özeti", "yanit": "yanıt metni",
  "dayanilan_bilgiler": ["yanıtta kullandığın her işletme bilgisi için bilgilerden BİREBİR alıntı"]}}"""

DENETIM_ISTEM = """Bir işletme adına yazılmış yorum yanıtını denetliyorsun.

İŞLETMENİN VERDİĞİ BİLGİLER: \"\"\"{bilgiler}\"\"\"
MÜŞTERİ YORUMU: \"\"\"{yorum}\"\"\"
YANIT: \"\"\"{yanit}\"\"\"

Soruları yalnızca yanıta bakarak cevapla:
- yeni_soz: Yanıt, bilgilerde olmayan bir söz ya da taahhüt veriyor mu (indirim, iade, ikram, telafi, tazminat,
  "bir dahakine şunu yapacağız" gibi somut vaat)? Özür dilemek ya da "ilgileneceğiz" demek söz sayılmaz.
- uydurma_bilgi: Yanıtta bilgilerde ya da yorumda olmayan somut bir olgu (saat, ürün, kural, kişi, olay) var mı?
- kusur_tutumu: Yanıt hukuki sonuç doğurabilecek biçimde kusuru kabul ediyor ("bizim hatamızdan zehirlendiniz"),
  müşteriyi yalanlıyor ya da sağlık/güvenlik/hukuk/ayrımcılık şikayetinde olayla ilgili bir bilgi vererek
  (ör. "ürünlerimizde alerjen var", "garanti şartlarımız şöyle") dolaylı olarak sorumluluğu birine yüklüyor mu?
- dil_uyumu: Yanıt yorumla aynı dilde mi?
Yalnızca şu JSON'u döndür:
{{"yeni_soz": true|false, "uydurma_bilgi": true|false, "kusur_tutumu": true|false, "dil_uyumu": true|false,
  "aciklama": "sorun varsa tek cümle"}}"""


def maskele(metin):
    """Modele gitmeden önce yorumdaki telefon ve e-postaları gizler (ücretsiz kredide içerik Meta'ya açık)."""
    return re.sub(EPOSTA, "[e-posta]", re.sub(TELEFON, "[telefon]", metin))


def _json(s):
    s = re.sub(r"^```(json)?|```$", "", s.strip(), flags=re.M).strip()
    return json.loads(s[s.find("{"): s.rfind("}") + 1])


def _norm(s):
    return re.sub(r"\s+", " ", s.replace("İ", "i").replace("I", "ı").lower()).strip()


def _bilgide(alinti, bilgiler):
    a, b = _norm(alinti), _norm(bilgiler)
    if not a or a in b:
        return bool(a)
    n = len(a)
    return max((SequenceMatcher(None, a, b[i:i + n]).ratio() for i in range(0, max(1, len(b) - n + 1), 3)),
               default=0) >= 0.85


def kod_denetimi(isletme, yorum, sonuc):
    """Modelden bağımsız, kuralla yakalanabilen sorunlar."""
    yanit, bilgiler = sonuc.get("yanit", ""), isletme["bilgiler"]
    sorunlar = []
    for ad, kalip in SOZLER.items():
        if re.search(kalip, yanit, flags=re.I) and not re.search(kalip, bilgiler, flags=re.I):
            sorunlar.append(f"işletmenin vermediği bir söz olabilir ({ad})")
    for tel in re.findall(TELEFON, yanit) + re.findall(EPOSTA, yanit):
        if _norm(tel) not in _norm(bilgiler):
            sorunlar.append(f"işletme bilgisinde olmayan iletişim bilgisi: {tel}")
    # yanıttaki sayılar (saat, fiyat, süre) bilgilerde ya da yorumda geçmeli
    for sayi in re.findall(r"\d+(?:[.:,]\d+)*", re.sub(TELEFON + "|" + EPOSTA, " ", yanit)):
        if sayi not in bilgiler and sayi not in yorum:
            sorunlar.append(f"kaynağı olmayan sayı: {sayi}")
    for d in sonuc.get("dayanilan_bilgiler", []):
        if not _bilgide(d, bilgiler):
            sorunlar.append(f"işletme bilgisinde bulunmayan dayanak: {d[:60]}")
    if len(yanit.split()) > 90:
        sorunlar.append("yanıt çok uzun")
    if not yanit.strip():
        sorunlar.append("yanıt boş")
    return sorunlar


def model_denetimi(isletme, yorum, yanit):
    try:
        d = _json(sor(DENETIM_ISTEM.format(bilgiler=isletme["bilgiler"], yorum=yorum, yanit=yanit),
                      json_mod=True, etiket="denetim"))
    except Exception:
        return ["denetim yapılamadı"]
    sorunlar = []
    if d.get("yeni_soz"):
        sorunlar.append("denetçi: işletmenin vermediği bir söz")
    if d.get("uydurma_bilgi"):
        sorunlar.append("denetçi: bilgilerde olmayan bir olgu")
    if d.get("kusur_tutumu"):
        sorunlar.append("denetçi: kusuru kabul ediyor ya da müşteriyi yalanlıyor")
    if d.get("dil_uyumu") is False:
        sorunlar.append("denetçi: yanıt dili yorumla aynı değil")
    if sorunlar and d.get("aciklama"):
        sorunlar.append(f"açıklama: {d['aciklama']}")
    return sorunlar


def yanitla(isletme, yorum, deneme_ust=2):
    """Sonuç sözlüğü döndürür: sınıflar, yanıt, denetim sonucu ve kaç denemede geçtiği."""
    yorum = maskele(yorum)
    duzelt, gecmis, s = "", [], {}
    for deneme in range(1, deneme_ust + 1):
        try:
            s = _json(sor(YANIT_ISTEM.format(ad=isletme["ad"], tur=isletme["tur"], bilgiler=isletme["bilgiler"],
                                             uslup=isletme.get("uslup", "saygılı"), yorum=yorum, duzelt=duzelt,
                                             konular=", ".join(KONULAR)), json_mod=True, etiket="yanit"))
        except (json.JSONDecodeError, ValueError):
            gecmis.append({"deneme": deneme, "sorunlar": ["JSON okunamadı"]})
            continue
        s["konular"] = [k for k in s.get("konular", []) if k in KONULAR] or ["diger"]
        sorunlar = kod_denetimi(isletme, yorum, s)
        if not any(x.startswith(("yanıt boş",)) for x in sorunlar):
            sorunlar += model_denetimi(isletme, yorum, s["yanit"])
        gecmis.append({"deneme": deneme, "yanit": s.get("yanit"), "sorunlar": sorunlar})
        if not sorunlar:
            return s | {"durum": "hazir", "deneme": deneme, "gecmis": gecmis}
        duzelt = ("\nÖNCEKİ TASLAĞIN SORUNLARI (bunları düzelterek yeniden yaz):\n- " + "\n- ".join(sorunlar)
                  + f"\nÖnceki taslak: \"{s.get('yanit', '')}\"\n")
    son = next((g for g in reversed(gecmis) if g.get("yanit")), {})
    return s | {"yanit": son.get("yanit", ""), "durum": "elle_duzenleyin",
                                          "sorunlar": son.get("sorunlar", []), "deneme": deneme_ust, "gecmis": gecmis}
