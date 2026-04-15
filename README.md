# e-Arsiv Fatura Otomasyonu

Lokal bilgisayarda calisan, e-Arsiv taslak fatura olusturma surecini yari otomatik hale getirmek icin gelistirilen Python uygulamasi.

Faz 1-6 ve Faz 7 oncesi kritik tamamlamalar kapsaminda uygulama veri import eder, her importu ayri fatura donemi olarak SQLite'a kaydeder, Excel sheet ve kolon mapping secimi sunar, kayitlari aktif donem bazinda listeler, PENDING kayitlari secilebilir hale getirir, Playwright ile portal login + manuel veya 2FA'siz session akisini yonetir, tek kayit icin e-Arsiv taslak POC olusturur ve aktif donemdeki secili uygun kayitlari sirali batch olarak isleyip sonuc raporu uretir.

## Ozellikler

- CSV ve Excel dosyasindan kayit importu
- Excel sheet secimi
- Kullanici kontrollu kolon mapping
- Her import icin ayri fatura donemi / import batch kaydi
- Minimum kolon validasyonu
- TCKN format kontrolu
- Pozitif USD tutar kontrolu
- Hatalı satirlari atlayip gecerli satirlari kaydetme
- SQLite ile lokal veri saklama
- FastAPI + Jinja2 ile sade lokal web panel
- JSON API saglik kontrolu ve kayit listesi
- Kalici kayit secimi
- Aktif fatura donemi bazli kayit listeleme ve batch isleme
- Tumunu sec checkbox'i
- Batch hazirlik, sirali batch isleme ve sonuc raporu
- Headful Playwright browser session yonetimi
- Portal login formunu .env credential'lari ile otomatik doldurma
- Manuel 2FA veya dogrudan `/Home/Index` sonrasi session hazir kontrolu
- Tek kayit icin e-Arsiv taslak POC
- Secili PENDING/SELECTED kayitlari toplu taslak isleme
- Draft sonucunu SQLite status/hata alanlarina yazma
- Gercek portal hata dialoglarini status/exception'a map etme
- Kayit bazli hatalarda batch'e devam etme
- Turmob sonrasi ad/soyad dogrulama ve `FAILED_NAME_MISMATCH` statusu
- Kritik session/navigation hatasinda batch'i guvenli durdurma
- Hata aninda screenshot alma
- Uygulama loglari

## Klasor Yapisi

```text
invoice_automation/
├── app/
│   ├── config.py
│   ├── constants.py
│   ├── db/
│   ├── routes/
│   ├── schemas/
│   ├── services/
│   ├── templates/
│   ├── static/
│   └── utils/
├── data/
│   ├── imports/
│   ├── processed/
│   └── logs/
├── memory-bank/
├── tests/
├── .env.example
├── requirements.txt
└── run.py
```

## Kurulum

Python 3.11 veya daha yeni bir surum kullanin.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Faz 3 icin Playwright tarayici kurulumu gerekir:

```bash
playwright install chromium
```

## .env Ayari

```bash
cp .env.example .env
```

Faz 3/Faz 4 icin portal login ve taslak POC alanlarini `.env` icinde doldurun:

```text
PORTAL_LOGIN_URL=https://portal.hizliteknoloji.com.tr/
PORTAL_2FA_URL=https://portal.hizliteknoloji.com.tr/User/VerificationUser?verificationType=Mail
PORTAL_USERNAME=...
PORTAL_PASSWORD=...
PLAYWRIGHT_HEADLESS=false
PLAYWRIGHT_TIMEOUT_MS=30000
NAVIGATION_RETRY_COUNT=2
MAL_HIZMET_ADI=YURT DIŞI KONAKLAMA BEDELİ
PARA_BIRIMI=USD
KDV_ORANI=0
ISTISNA_TARGET_TEXT=302-11/1-a Hizmet ihracatı
ISTISNA_OPTION_VALUE=
DEFAULT_IL=**
DEFAULT_ILCE=**
```

2FA kodu `.env` icinde tutulmaz. Kod kullanici tarafindan acik browser uzerinden manuel girilir.

## Calistirma

```bash
python run.py
```

Ardindan tarayicida acin:

```text
http://127.0.0.1:8000
```

## Veri Formati

Import mapping ekraninda minimum su alanlar eslestirilir:

```text
ad,soyad,tc_kimlik_no,tutar_usd
```

`aciklama` opsiyoneldir. Otomatik alias mapping fallback olarak korunur.

Ornek CSV:

```csv
ad,soyad,tc_kimlik_no,tutar_usd,aciklama
Ali,Yilmaz,12345678901,1500,Yurt disi konaklama
Ayse,Demir,10987654321,2200,Umre hizmeti
```

Desteklenen dosya tipleri:

- `.csv`
- `.xlsx`
- `.xls`

## Ekranlar

- `/` dosya yukleme ekrani
- `/import/inspect` sheet kolonlarini yeniden yukleme
- `/import/confirm` mapping + fatura donemi ile import
- `/records?batch_id=1` aktif fatura donemi kayit listesi
- `/records?batch_id=1&status=PENDING` durum filtresi
- `/batch?batch_id=1` aktif fatura doneminde secili kayitlar icin batch hazirlik ekrani
- `/batch/run` secili uygun kayitlari batch olarak isleme
- `/session` browser login ve 2FA session ekrani
- `/draft` tek kayit e-Arsiv taslak POC ekrani
- `/api/health` saglik kontrolu
- `/api/records` JSON kayit listesi
- `/api/batch/preview` JSON batch preview
- `/api/batch/run` JSON batch run raporu
- `/api/session/status` JSON session durumu
- `/api/session/start` browser login baslatma
- `/api/session/verify` manuel 2FA sonrasi session kontrolu
- `/api/session/close` browser session kapatma
- `/api/draft/create?record_id=1` tek kayit draft POC

## Bilinen Limitler

- Kolon mapping ekrani vardir; otomatik alias mapping fallback olarak korunur.
- TCKN kontrolu format seviyesindedir; resmi checksum validasyonu yoktur.
- Batch run sadece aktif fatura donemi icindeki secili ve durumu PENDING/SELECTED olan kayitlari isler.
- Basari/hata/skip durumundaki kayitlar bu fazda otomatik yeniden denenmez.
- Batch calismasi siralidir; dagitik job queue veya websocket yoktur.
- Invalid TCKN, Turmob servis hatasi ve e-Fatura mukellefi dialoglari yakalanir.

## Guvenlik Notlari

- Portal kullanici adi ve sifresi `.env` icinde tutulmalidir.
- `.env` dosyasi repoya commit edilmemelidir.
- Uygulama lokal calisma hedefiyle tasarlanmistir.
- Faz 1'de GIB'e gonderim veya taslak fatura olusturma yoktur.

## Test

```bash
pytest
```

## Manuel Test Checklist

1. Sanal ortam olusturun ve bagimliliklari yukleyin.
2. `.env.example` dosyasini `.env` olarak kopyalayin.
3. `python run.py` komutunu calistirin.
4. `http://127.0.0.1:8000` adresini acin.
5. Gecerli CSV veya Excel dosyasi yukleyin.
6. Excel icin sheet secin, kolon mapping yapin ve fatura donemi adi verin.
7. Import sonrasi kayitlarin `/records?batch_id=...` ekraninda sadece ilgili donemde gorundugunu kontrol edin.
8. PENDING kayitlardan bir veya daha fazlasini secip `Secimi Kaydet` butonuna basin.
9. Header'daki `Tumunu Sec` checkbox'i ile uygun kayitlarin topluca secilebildigini kontrol edin.
10. Secilen kayitlarin SELECTED durumuna gectigini kontrol edin.
11. `/batch?batch_id=...` ekraninda secili kayit sayisini ve toplam USD tutarini kontrol edin.
12. `/session` ekraninda `Tarayiciyi Ac / Login Baslat` butonuna basin.
13. Browser'in acildigini, login alanlarinin doldugunu ve 2FA varsa 2FA ekranina geldigini kontrol edin.
14. 2FA yoksa `/Home/Index` sonrasi durumun dogrudan `READY` oldugunu kontrol edin.
15. 2FA varsa kodu acik browser'da manuel girip dogrulayin ve panelde `2FA Tamam, Session Kontrol Et` butonuna basin.
16. Durumun `READY` oldugunu kontrol edin.
17. `/draft` ekranina gidin.
18. Tek bir kayit icin `Taslak POC Olustur` butonuna basin.
19. Portalda e-Arsiv olustur sayfasinin acildigini, USD secildigini, kur getir aksiyonunun tetiklendigini, TCKN ve kalem bilgilerinin doldugunu kontrol edin.
20. Turmob sonrasi portal ad/soyadinin SQLite ad/soyadiyla eslestigini kontrol edin.
21. `Taslak Kaydet` butonuna basildigini ve kaydin `SUCCESS_DRAFT_CREATED` veya anlamli hata statusune gectigini kontrol edin.
22. Gecersiz TCKN formatinda `geçerli bir VKN/TCKN değeri değildir` dialogunun `FAILED_INVALID_TCKN` yazdigini kontrol edin.
23. Turmob servis hatasinda `Servis hatası oluştu` dialogunun `FAILED_TURMOB_SERVICE_ERROR` yazdigini kontrol edin.
24. e-Fatura mukellefi kiside `e-Fatura Mükellefine e-Arşiv Fatura Kesilemez` dialogunun `SKIPPED_EFATURA_MUKELLEFI` yazdigini kontrol edin.
25. Turmob ad/soyad uyusmazliginda `FAILED_NAME_MISMATCH` yazildigini kontrol edin.
26. Hata aninda dialogun OK ile kapandigini ve `data/logs/screenshots/` altina screenshot yazildigini kontrol edin.
27. `/batch?batch_id=...` ekraninda `Secilileri Taslak Olustur` butonuna basin.
28. Birden fazla secili kaydin sirayla islenip sonuc raporunda success/failed/skipped sayilarinin gorundugunu kontrol edin.
29. Bir kayit hata verdiginde sonraki kayda gecildigini kontrol edin.
30. Session kapanirsa batch'in kritik abort raporuyla guvenli durdugunu kontrol edin.
31. Eksik kolon mapping ile import deneyip anlasilir hata mesajini kontrol edin.
32. `data/invoice_automation.sqlite3` dosyasinin olustugunu kontrol edin.
33. `data/logs/app.log` dosyasina log yazildigini kontrol edin.

## Portal Hata Patternleri

Kodda merkezi tutulan dialog basliklari ve mesaj patternleri:

- Dialog basliklari: `Hata Oluştu`, `Bilgi`
- Turmob servis hatasi: `Servis hatası oluştu`
- Gecersiz VKN/TCKN: `geçerli bir VKN/TCKN değeri değildir`
- e-Fatura mukellefi: `e-Fatura Mükellefine e-Arşiv Fatura Kesilemez`
- Basari redirect: `/EArchive/Drafts`

## Gelecek Fazlar

- Faz 2: kayit secimi, durum yonetimi ve batch hazirligi tamamlandi
- Faz 3: Playwright browser session ve login + 2FA akisi tamamlandi
- Faz 4: tek kayit icin taslak olusturma POC tamamlandi
- Faz 5: hata senaryolari ve screenshot/log iyilestirmeleri tamamlandi
- Faz 6: coklu batch isleme ve sonuc raporu tamamlandi
- Faz 7 oncesi kritik operasyonel eksikler: fatura donemi izolasyonu, sheet/mapping import, 2FA'siz login, tumunu sec ve Turmob ad/soyad kontrolu tamamlandi
- Faz 7: sertlestirme, refactor ve UI iyilestirmeleri
