# Yorum Yanıtlayıcı

Küçük işletmeler için: müşteri yorumlarını yapıştırırsınız; her birine işletme adına bir yanıt taslağı,
duygu/konu sınıflaması ve acil olanların işaretlendiği bir özet çıkar.

Bu tür araçların asıl riski, işletme adına **verilmemiş söz vermesi** ("size %20 indirim tanımlayalım")
ya da bilgi uydurmasıdır. Bu araç yanıtı yalnızca işletmenin kendi yazdığı bilgilere dayandırır ve bunu denetler.

> Durum: prototip, yerel çalışır. Gerçek bir işletmeyle henüz denenmedi.

## Nasıl çalışır

```
yorum ──maskele (telefon, e-posta)──▶ Muse Spark: sınıflama + yanıt + "dayandığım bilgiler" (JSON)
                                         │
             kod denetimi ◀──────────────┘  söz kalıpları (indirim, iade, ikram, telafi…) bilgilerde yoksa,
                │                            kaynağı olmayan sayı / telefon / e-posta, bilgide bulunmayan dayanak
                ▼
        model denetimi (ayrı çağrı)          yeni söz? uydurma olgu? kusur kabulü/yalanlama? dil uyumu?
                │
   sorun varsa sorunları söyleyerek bir kez yeniden yazdır; yine geçmezse "Elle düzenleyin"
```

Sağlık, güvenlik, hukuki tehdit ya da ayrımcılık içeren yorumlar "acil" olarak en üste çıkar.
Bu yorumlarda yanıt olayla ilgili hiçbir bilgi vermez; yalnızca üzüntü bildirir ve özel iletişime yönlendirir.

## Çalıştırma

```bash
python -m venv .venv
.venv/Scripts/python sunucu.py              # http://127.0.0.1:8790
.venv/Scripts/python olc.py v3              # geliştirme setinde ölçüm
SET=ayrik.json .venv/Scripts/python olc.py ayrik
```

Anahtar: `META_MODEL_API_KEY`. Harcama `kayitlar/butce.jsonl`'e yazılır; `YORUM_TAVAN` (varsayılan 20 $) aşılınca durur.

## Ölçümler

Test yorumlarını ben yazdım (uydurma işletmeler; her yorumda yanıtın düşmemesi gereken bir "tuzak" var:
indirim isteyen müşteri, gıda zehirlenmesi, alaycı övgü, yanlış bilgi veren müşteri, telefon numarası bırakan müşteri…).
Yanıtları tuzaklara karşı elle okudum.

| Set | Yanıt | Elle: kabul edilebilir | Duygu | Aciliyet |
|---|---|---|---|---|
| Geliştirme v1 (30 yorum, kafe + oto servis) | 30 | 30 güvenli, ama ~8'i işletme metnini yapıştırdığı için bozuk cümleli | 30/30 | 29/30 |
| Geliştirme v2 (üslup kuralı eklendi) | 30 | 28; **1 ciddi hata**: alerji şikayetine "tatlılarımızın çoğunda fındık var" eklemiş (iki denetim de kaçırdı), 1 yazım hatası | 30/30 | 29/30 |
| Geliştirme v3 (acil durum kuralı), 2 tekrar | 60 | 60 | 60/60 | 58/60 |
| **Ayrık set** (yeni işletme: kuaför, 15 yorum; istem bu set görülmeden sabitlendi) | 15 | 15 (1 küçük büyük harf hatası) | 15/15 | 15/15 |

Aciliyetteki tek fark: "menüdeki fiyat kasada farklı, bu yasal mı?" yorumunu model acil saydı, ben saymamıştım (tartışmalı).

Maliyet: yorum başına ~0,001 $ (yanıt + denetim). 1.000 yorum ≈ 1 $.

**Bu sayılar ne söylemez:** Test seti küçük ve tek kişinin (benim) yazdığı uydurma yorumlardan oluşuyor; elle
değerlendirmeyi de ben yaptım. Gerçek yorumlar daha dağınık olabilir. Kod denetimi tüm turlarda yalnızca bir kez
gerçek bir söz yakaladı (v1'de "bedava"); modelin kendisi kurallara çoğunlukla uyuyor. Model denetçisi özeti
yazan modelle aynı ve v2'deki ciddi hatayı kaçırdı; ona güvenmek yerine kural ve kapsam (acil durumda bilgi verme) ile
önlem alındı.

## Bilinen sınırlar

- Yorumlar elle yapıştırılır; Google/Trendyol'dan otomatik çekme yok (sitelerin kurallarına aykırı olabilir).
  Doğru yol işletme sahibinin yetkisiyle Google Business Profile API'si; henüz yapılmadı.
- Yorumlardaki ad/soyad maskelenmiyor (yalnızca telefon ve e-posta). Ücretsiz Meta kredisiyle gönderilen içerik
  Meta'nın ürün geliştirmesinde kullanılabilir.
- Yanıtlar taslaktır; acil işaretli olanlar yayımlanmadan önce bir insan (gerekirse avukat) tarafından okunmalı.
- Sunucu yalnızca 127.0.0.1'de dinler; çok kullanıcılı yayın için kimlik doğrulama ve hız sınırı gerekir.

## Herkese açık demo

**Canlı:** https://51-20-66-93.sslip.io/

Demo, `canli.py` ile çalışır. Arayüz ve API, `sunucu.py`'nin aynısıdır; üstüne kötüye kullanıma karşı sınırlar eklenmiştir:
- Tek istekte en fazla 3 yorum işlenir.
- Bir IP günde en fazla 15 yorum işletebilir; tüm ziyaretçiler için günlük sınır 400 yorumdur.
- Sunucudaki toplam Meta harcaması 5 $'ı geçince demo durur.

Yorumlar ve işletme bilgileri kaydedilmez. Günlük sayım için IP'nin yalnızca kısaltılmış özeti bellekte tutulur.

Sunucu: AWS'de systemd servisi (`yorum-demo.service`, bellek 250 MB, CPU %60 ile sınırlı). Önde Caddy çalışır ve HTTPS sertifikasını kendisi alır.
