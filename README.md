# e-Arsiv Fatura Otomasyonu

Lokal bilgisayarda calisan, e-Arsiv taslak fatura olusturma surecini yari otomatik hale getirmek icin gelistirilen Python uygulamasi.

Faz 1 ve Faz 2 kapsaminda uygulama veri import eder, SQLite'a kaydeder, kayitlari lokal web panelde listeler, PENDING kayitlari secilebilir hale getirir ve secili kayitlar icin batch hazirlik ekrani sunar. Portal otomasyonu, Playwright login akisi, 2FA sonrasi gercek batch isleme ve taslak fatura olusturma sonraki fazlarda eklenecektir.

## Ozellikler

- CSV ve Excel dosyasindan kayit importu
- Minimum kolon validasyonu
- TCKN format kontrolu
- Pozitif USD tutar kontrolu
- Hatalı satirlari atlayip gecerli satirlari kaydetme
- SQLite ile lokal veri saklama
- FastAPI + Jinja2 ile sade lokal web panel
- JSON API saglik kontrolu ve kayit listesi
- Kalici kayit secimi
- Batch hazirlik ve temel progress ekrani
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

Playwright tarayici kurulumlari Faz 3'te aktif kullanilacak. Simdiden hazirlamak isterseniz:

```bash
playwright install chromium
```

## .env Ayari

```bash
cp .env.example .env
```

Faz 1 icin portal bilgileri kullanilmaz, ancak sonraki fazlara hazirlik icin `.env.example` icinde tutulur.

## Calistirma

```bash
python run.py
```

Ardindan tarayicida acin:

```text
http://127.0.0.1:8000
```

## Veri Formati

Ilk surum minimum su kolonlari bekler:

```text
ad,soyad,tc_kimlik_no,tutar_usd,aciklama
```

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
- `/records` kayit listesi
- `/records?status=PENDING` durum filtresi
- `/batch` secili kayitlar icin batch hazirlik ekrani
- `/api/health` saglik kontrolu
- `/api/records` JSON kayit listesi
- `/api/batch/preview` JSON batch preview

## Bilinen Limitler

- Kolon mapping ekrani yoktur; sadece normalize edilen minimum kolonlar desteklenir.
- TCKN kontrolu format seviyesindedir; resmi checksum validasyonu yoktur.
- Portal otomasyonu bu fazda uygulanmamistir.
- Gercek browser tabanli batch isleme Faz 3 ve sonrasi icin ayrilmistir.
- Faz 2 batch hazirligi sadece secili kayitlari hazirlar; portala gitmez.

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
6. Import sonrasi kayitlarin `/records` ekraninda gorundugunu kontrol edin.
7. PENDING kayitlardan bir veya daha fazlasini secip `Secimi Kaydet` butonuna basin.
8. Secilen kayitlarin SELECTED durumuna gectigini kontrol edin.
9. `/batch` ekraninda secili kayit sayisini ve toplam USD tutarini kontrol edin.
10. Eksik kolonlu dosya yukleyip anlasilir hata mesajini kontrol edin.
11. Hatali TCKN iceren satirin atlandigini ve uygulamanin kapanmadigini kontrol edin.
12. `data/invoice_automation.sqlite3` dosyasinin olustugunu kontrol edin.
13. `data/logs/app.log` dosyasina log yazildigini kontrol edin.

## Gelecek Fazlar

- Faz 2: kayit secimi, durum yonetimi ve batch hazirligi tamamlandi
- Faz 3: Playwright browser session ve login akisi
- Faz 4: tek kayit icin taslak olusturma POC
- Faz 5: hata senaryolari ve screenshot/log iyilestirmeleri
- Faz 6: coklu batch isleme ve sonuc raporu
- Faz 7: sertlestirme, refactor ve UI iyilestirmeleri
