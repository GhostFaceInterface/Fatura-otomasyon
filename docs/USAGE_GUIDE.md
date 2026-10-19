# Kullanim Kilavuzu

Bu kilavuz operasyon kullanicisinin bir fatura donemini import edip secili kayitlar icin taslak olusturmasi icin hazirlandi.

## 1. Uygulamayi Baslatma

```bash
./scripts/start.sh
```

İlk çalıştırmada betik `.venv/` ortamını, sabitlenmiş bağımlılıkları ve Playwright Chromium'u kurar. `.env` isteğe bağlıdır; yoksa panel varsayılan ayarlarla açılır. Portal oturumu açılacaksa `PORTAL_USERNAME` ve `PORTAL_PASSWORD` değerlerini `.env` içine veya kabuk ortamına ekleyin. Başlatmak portal oturumu açmaz veya taslak fatura oluşturmaz.

Paneli acin:

```text
http://127.0.0.1:8010
```

`8000` ortamdan gelse bile betik otomatik olarak `8010` kullanir. Farkli bir port yalnizca istege baglidir; ornegin `APP_PORT=8123 ./scripts/start.sh` kullanabilirsiniz.

## 2. Yeni Fatura Donemi Import Etme

1. `Veri Yukle` ekranina gidin.
2. Excel veya CSV dosyasini secin.
3. Dosyayi yukleyin.
4. Excel ise sheet listesinden dogru sheet'i secin.
5. Kolon mapping alanlarini doldurun:
   - `ad`
   - `soyad`
   - `tc_kimlik_no`
   - `tutar_usd`
   - opsiyonel `aciklama`
6. Batch/fatura donemi adini yazin.
7. Importu onaylayin.

Import sonucu gecerli satirlar SQLite'a yazilir. Hatalı satirlar raporlanir, uygulama kapanmaz.

## 3. Kayitlari Kontrol Etme

1. `Kayitlar` ekranina gidin.
2. Fatura donemi seciciden dogru donemi secin.
3. Listede su alanlari kontrol edin:
   - Ad
   - Soyad
   - TCKN
   - Tutar USD
   - Durum
4. Gerekirse status filtresi veya arama alanini kullanin.

Kayitlar sadece aktif fatura donemi icinde listelenir. Yanlis donemde islem yapmamak icin aktif donem adini mutlaka kontrol edin.

## 4. Kayit Secme

1. Sadece islenecek kayitlari checkbox ile secin.
2. Tum uygun gorunen kayitlar islenecekse `Tumunu Sec` checkbox'ini kullanin.
3. `Secimi Kaydet` butonuna basin.
4. Secili kayit sayisinin beklenen sayi oldugunu kontrol edin.

Sadece `PENDING` ve `SELECTED` durumundaki kayitlar secilebilir.

## 5. Session Acma

1. `Session` ekranina gidin.
2. `Tarayiciyi Ac / Login Baslat` butonuna basin.
3. Portal login bilgileri `.env` uzerinden otomatik doldurulur.
4. Portal direkt `/Home/Index` sayfasina giderse session `READY` olur.
5. 2FA sayfasi gelirse kodu acik browser'da manuel girin.
6. 2FA dogrulamasi sonrasi panelde `2FA Tamam, Session Kontrol Et` butonuna basin.
7. Durum `READY` olana kadar batch baslatmayin.

## 6. Batch Calistirma

1. `Batch` ekranina gidin.
2. Aktif fatura doneminin dogru oldugunu kontrol edin.
3. Session durumunun `READY` oldugunu kontrol edin.
4. Secili uygun kayit sayisini kontrol edin.
5. `Secilileri Taslak Olustur` butonuna basin.

Batch kayitlari id/import sirasina gore sirali isler. Kayit bazli hatalar batch'i durdurmaz. Kritik session veya navigation problemi olursa batch guvenli sekilde durur.

Batch basladiginda uygulama bilgisayarin uyumasini engellemeye calisir. Bu davranis `.env` icindeki `SLEEP_PREVENTION_ENABLED`, `SLEEP_PREVENTION_PLATFORM` ve `SLEEP_PREVENTION_KEEP_DISPLAY_AWAKE` alanlariyla yonetilir. Bu engel sadece batch calisirken aktiftir; batch tamamlaninca otomatik kapanir.

## 7. Batch Sonucunu Inceleme

Batch sonucu ekranda su bilgiler gorunur:

- Toplam secili uygun kayit
- Islenen kayit
- Basarili taslak sayisi
- Skip sayisi
- Failed sayisi
- Kritik abort bilgisi
- Status dagilimi
- Kayit bazli hata mesaji ve screenshot path

Detay tablosunda filtreler:

- Tum Detaylar
- Failed
- Skip
- Screenshot Olanlar

## 8. Hata Olan Kayitlari Inceleme

1. Batch raporunda hata statusunu bulun.
2. Hata mesajini okuyun.
3. Screenshot path varsa `data/logs/screenshots/` altindan dosyayi acin.
4. Gerekiyorsa `data/logs/app.log` dosyasinda record id veya TCKN ile arama yapin.

Yaygin statusler:

- `FAILED_INVALID_TCKN`: TCKN/VKN verisi veya portal validasyonu gecersiz.
- `FAILED_TURMOB_SERVICE_ERROR`: Turmob sorgusunda servis hatasi.
- `SKIPPED_EFATURA_MUKELLEFI`: kisi e-Fatura mukellefi.
- `FAILED_NAME_MISMATCH`: Turmob ad/soyad lokal kayitla eslesmedi. Buyuk/kucuk harf ve bosluk farki ile sadece `ı/i/İ/I`, `u/ü`, `o/ö` farki tolere edilir (ornek: Excel'de `Ozturk`, portalda `Öztürk`). Toleransla gecen kayit fail olmaz; `data/logs/app.log` icine `harf toleransiyla eslesti` uyarisi iki degerle birlikte yazilir. `ş/s`, `ç/c`, `ğ/g`, eksik/fazla harf veya farkli isim yine uyusmazliktir.
- `FAILED_PORTAL_TIMEOUT`: portal beklenen yaniti zamaninda vermedi (Taslak Kaydet oncesi).
- `NEEDS_REVIEW`: Taslak Kaydet tiklandi ama sonuc dogrulanamadi ya da islem yarida kaldi. Portaldaki Taslaklar listesini kontrol edin; kayit ekranindaki "Kontrol ve yeniden deneme" kartinda "Taslak var" veya "Taslak yok" ile sonuclandirin. Bu kayitlar otomatik yeniden denenmez.

Hatali kayitlari tekrar denemek icin kayit ekranindaki "Kontrol ve yeniden deneme" kartindan "Yeniden denemeye al" kullanin; kayit `PENDING` olur ve tekrar secilebilir.

Toplu islem arka planda calisir: baslattiktan sonra sayfa ilerlemeyi otomatik gunceller, ayni anda tek islem calisabilir ve "Islemi durdur" ile portalda islenen kayit bittikten sonra durdurulabilir.

## 9. Tek Kayit POC

`Draft POC` ekrani tek kayit icin manuel dogrulama amaclidir. Canli batch oncesi yeni portal selector veya config degisikligi test etmek icin kullanilabilir.

## 10. Guvenli Kullanim Notlari

- Yanlis fatura donemi seciliyken batch baslatmayin.
- Import sonrasi kayitlari gozle kontrol etmeden batch baslatmayin.
- Session `READY` degilken batch calistirmayin.
- Ilk canli kullanimda kucuk kayit grubuyla deneyin.
- Hata statuslerini rapor bitmeden manuel olarak degistirmeyin.
