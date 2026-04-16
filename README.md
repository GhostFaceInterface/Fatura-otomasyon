# e-Arsiv Fatura Otomasyonu

Lokal bilgisayarda calisan, Excel/CSV verilerinden e-Arsiv taslak fatura olusturma surecini yari otomatik hale getiren Python uygulamasi.

## 1. Proje Amaci

Bu proje, manuel olarak tekrar edilen e-Arsiv taslak fatura hazirlama adimlarini lokal bir web panel ve Playwright browser otomasyonu ile azaltmak icin gelistirildi. Sistem veriyi import eder, kayitlari fatura donemi altinda saklar, kullanicinin sectigi kisiler icin portala girerek taslak olusturur ve hata alan kayitlari anlamli statuslerle raporlar.

## 2. Sistem Ne Yapar / Ne Yapmaz

Yapar:

- Excel/CSV import eder.
- Excel sheet secimi ve kolon mapping sunar.
- Her importu ayri fatura donemi olarak saklar.
- Kayitlari aktif fatura donemine gore listeler.
- Kayit secimi ve tumunu sec davranisini destekler.
- Headful Playwright browser acip login formunu doldurur.
- 2FA varsa kullaniciyi manuel kod girisi icin bekletir.
- 2FA yoksa `/Home/Index` veya e-Arsiv menu sinyali ile session hazir kabul eder.
- Tek kayit ve secili coklu kayit icin taslak e-Arsiv fatura olusturma akisini calistirir.
- Invalid TCKN, Turmob servis hatasi, e-Fatura mukellefi ve ad/soyad uyusmazligi gibi durumlari statuslere map eder.
- Hata aninda log ve screenshot uretir.

Yapmaz:

- GIB'e otomatik gonderim yapmaz.
- Muhasebe sistemi veya uzak sunucu deployment saglamaz.
- Cok kullanicili rol/yetki sistemi kurmaz.
- Hata alan kayitlari otomatik yeniden deneme workflow'una sokmaz.

## 3. Kurulum

Python 3.11+ kullanin.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 4. .env Ayarlari

```bash
cp .env.example .env
```

Temel alanlar:

```text
PORTAL_LOGIN_URL=https://portal.hizliteknoloji.com.tr/
PORTAL_2FA_URL=https://portal.hizliteknoloji.com.tr/User/VerificationUser?verificationType=Mail
PORTAL_USERNAME=
PORTAL_PASSWORD=
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_TIMEOUT_MS=30000
NAVIGATION_RETRY_COUNT=2
FIELD_WAIT_TIMEOUT_MS=30000
REDIRECT_WAIT_TIMEOUT_MS=30000
TURMOB_LOOKUP_RETRY_COUNT=2
RETRY_BACKOFF_BASE_MS=500
TAX_SCHEME_PREFILL_WAIT_MS=2000
DRAFT_SAVE_WAIT_MS=2000
SLEEP_PREVENTION_ENABLED=true
SLEEP_PREVENTION_PLATFORM=auto
SLEEP_PREVENTION_KEEP_DISPLAY_AWAKE=true
MAL_HIZMET_ADI=YURT DIŞI KONAKLAMA BEDELİ
PARA_BIRIMI=USD
KDV_ORANI=0
ISTISNA_TARGET_TEXT=302-11/1-a Hizmet ihracatı
ISTISNA_OPTION_VALUE=
DEFAULT_IL=**
DEFAULT_ILCE=**
```

2FA kodu `.env` icinde tutulmaz. Kod acik browser uzerinden kullanici tarafindan girilir.

Sleep prevention ayarlari sadece batch/taslak olusturma sirasinda kullanilir. Import, kayit listeleme veya session ekraninda bilgisayarin uyku davranisi degistirilmez. `SLEEP_PREVENTION_PLATFORM=auto` macOS, Windows ve Linux'u otomatik algilar; gerekirse `macos`, `windows` veya `linux` olarak elle yazilabilir.

## 5. Uygulamayi Calistirma

```bash
python run.py
```

Panel:

```text
http://127.0.0.1:8000
```

## 6. Excel Import Akisi

1. `/` ekraninda Excel veya CSV dosyasini yukleyin.
2. Excel dosyasinda kullanilacak sheet'i secin.
3. Kolon mapping ekraninda zorunlu alanlari eslestirin.
4. Fatura donemi / batch adi verin.
5. Importu onaylayin.

## 7. Sheet Secimi

Excel dosyasi birden fazla sheet iceriyorsa sistem sheet listesini okur. Kullanici import edilecek sheet'i secer ve kolon listesi secilen sheet'e gore yenilenir.

## 8. Kolon Mapping

Zorunlu alanlar:

- `ad`
- `soyad`
- `tc_kimlik_no`
- `tutar_usd`

Opsiyonel alan:

- `aciklama`

Otomatik alias mapping fallback olarak korunur, ancak operasyonel kullanimda kullanici kontrollu mapping tercih edilir.

## 9. Fatura Donemi / Batch Mantigi

Her import `import_batches` tablosunda ayri bir fatura donemi olusturur. `invoice_records.batch_id` ile kayitlar ilgili doneme baglanir.

Records ve batch ekranlari aktif fatura donemi baglaminda calisir. Eski donemde secili kalmis kayitlar yeni donem batch islemini etkilemez.

## 10. Session Baslatma

`/session` ekraninda:

1. `Tarayiciyi Ac / Login Baslat` butonuna basin.
2. Sistem portali acar, kullanici adi ve sifreyi `.env` uzerinden doldurur.
3. Login sonrasi durum panelde guncellenir.

## 11. 2FA'li / 2FA'siz Login Davranisi

Login sonrasi uc sinyal izlenir:

- 2FA sayfasi: `/User/VerificationUser`
- Basarili dashboard: `/Home/Index`
- e-Arsiv menu linki

2FA sayfasi gelirse kullanici kodu manuel girer ve panelde session kontrolu calistirilir. `/Home/Index` veya e-Arsiv menu gorunurse session `READY` kabul edilir.

## 12. Kayit Secme

`/records?batch_id=...` ekraninda aktif fatura donemine ait kayitlar listelenir. Sadece `PENDING` ve `SELECTED` kayitlar secilebilir. Header'daki `Tumunu Sec` checkbox'i yalnizca gorunur ve uygun checkboxlari etkiler.

## 13. Toplu Taslak Olusturma

`/batch?batch_id=...` ekraninda:

1. Aktif fatura donemini kontrol edin.
2. Session durumunun `READY` oldugunu dogrulayin.
3. Secili uygun kayit sayisini kontrol edin.
4. `Secilileri Taslak Olustur` butonuna basin.

Batch siralidir. Kayit bazli hatalarda sonraki kayda gecilir. Session veya navigation kritik hatasinda batch guvenli sekilde durur.

Batch calisirken uygulama bilgisayarin uyumasini engellemeye calisir. macOS'ta `caffeinate`, Windows'ta native execution state, Linux'ta `systemd-inhibit` kullanilir. Batch tamamlaninca veya hata nedeniyle durunca bu engel otomatik kapatilir.

## 14. Hata Statusleri

- `PENDING`: import edildi, islem bekliyor.
- `SELECTED`: kullanici tarafindan batch icin secildi.
- `IN_PROGRESS`: kayit isleniyor.
- `SUCCESS_DRAFT_CREATED`: taslak basariyla olustu.
- `FAILED_INVALID_TCKN`: VKN/TCKN formati veya portal validasyonu gecersiz.
- `FAILED_NAME_MISMATCH`: Turmob ad/soyad ile lokal kayit eslesmedi.
- `FAILED_TURMOB_SERVICE_ERROR`: Turmob servis hatasi alindi.
- `SKIPPED_EFATURA_MUKELLEFI`: kisi e-Fatura mukellefi oldugu icin e-Arsiv kesilemedi.
- `FAILED_PORTAL_TIMEOUT`: portal elementi, redirect veya navigation timeout oldu.
- `FAILED_UNKNOWN`: siniflandirilmamis hata.
- `ABORTED_SESSION_LOST`: session/browser kritik nedenle kaybedildi.

## 15. Screenshot ve Loglar

- Uygulama logu: `data/logs/app.log`
- Hata screenshotlari: `data/logs/screenshots/`
- Veritabani: `data/invoice_automation.sqlite3`

Batch raporunda screenshot path gorunuyorsa ilgili kaydin hata anindaki ekran goruntusu incelenmelidir.

## 16. Bilinen Sinirlamalar

- Portal selectorlari gercek portala baglidir; portal UI degisirse guncelleme gerekir.
- TCKN dogrulamasi import sirasinda format seviyesindedir.
- Batch sirali calisir; websocket, queue veya paralel isleme yoktur.
- Basarili/hata/skip kayitlar otomatik yeniden denenmez.
- Bu uygulama sadece lokal kullanim icin tasarlanmistir.

## 17. Guvenlik Notlari

- `.env` repoya commit edilmemelidir.
- Portal sifresi sadece lokal `.env` dosyasinda tutulmalidir.
- Uygulama headful browser kullanir; 2FA kodu otomatik cozulmez.
- Canli kullanim oncesi kucuk test batch'i ile dogrulama yapin.

## 18. Canli Kullanim Oncesi Checklist

1. `.env` credential alanlari dogru mu?
2. Excel dosyasi dogru mu?
3. Sheet ve kolon mapping dogru mu?
4. Fatura donemi adi dogru mu?
5. Records ekraninda sadece aktif donem kayitlari mi gorunuyor?
6. Secili kayit sayisi beklenen sayi mi?
7. Session durumu `READY` mi?
8. `.env` icinde sleep prevention ayarlari dogru mu?
9. Ilk deneme kucuk kayit grubu ile yapildi mi?
10. Batch sonrasi success/fail/skip dagilimi kontrol edildi mi?
11. Hata screenshot ve loglari incelendi mi?

## Test

```bash
pytest
```

Detayli operasyon adimlari icin `docs/USAGE_GUIDE.md`, kontrol listeleri icin `docs/OPERATIONS_CHECKLIST.md` dosyasina bakin.
