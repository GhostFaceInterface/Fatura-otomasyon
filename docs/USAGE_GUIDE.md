# Kullanim Kilavuzu

Panelde uc ekran vardir: **Donemler** (ana sayfa), **Tum kayitlar** ve **Dosya yukle**. Sag ustteki **Portal** rozeti oturum durumunu gosterir ve portal sayfasini acar.

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

## 2. Dosya Yukleme (Yeni Donem)

1. `Dosya yukle` > Excel veya CSV sec > `Devam`.
2. Excel'de birden fazla sayfa varsa `Sayfa` listesinden dogru sayfayi sec.
3. Ad, Soyad, TC kimlik no ve Tutar (USD) kolonlarini sec; Aciklama istege baglidir. `Onizle`.
4. Onizleme ekraninda dosyadaki kisiler duzenlenebilir bir tabloda gelir. Bu noktada veritabanina hicbir sey yazilmamistir.
   - Hucreye tiklayip ad, soyad, TCKN, tutar veya aciklamayi duzelt. Degisen hucre sari olur; uzerine gelince dosyadaki eski deger gorunur.
   - Tutar `1450`, `1.450`, `1450,50` veya `1.450,50` gibi yazilabilir; hucreden cikinca `1450.00` bicimine doner. Boylece kaydedilecek deger ekranda gorunur.
   - `Sil` satiri cikarir (ustu cizili kalir), `Geri al` geri getirir.
   - `+ Kisi ekle` tablonun sonuna bos bir satir ekler. Bos birakilan yeni satir yok sayilir.
   - Hatali hucreler kirmizi ve altinda sebebi yazar. Hata varken ice aktarma butonu kapalidir; duzelt ya da `Hatalilarin hepsini sil`.
   - Ayni TCKN listede birden fazla varsa sari uyari cikar ama engellemez.
   - Ustteki arama ve `Tumu / Hatali / Degistirilen / Yeni eklenen / Silinen` secimi uzun listede bulmayi kolaylastirir.
5. En alttaki `Donem adi` kutusuna yaz (ornek: `Ekim 2026 umre`) ve `N kisiyi ice aktar`a tikla; onay sorusu kac kisinin hangi doneme aktarilacagini soyler. Enter tusu hicbir kutuda ice aktarma yapmaz; listede aramak icin en ustteki `Listede ara` kutusu kullanilir ve yazdikca suzer.

Tabloda ne gorunuyorsa o aktarilir. Sunucu tum satirlari ayni kurallarla tekrar kontrol eder; tek bir hata bile varsa hicbir kayit yazilmaz. Hata yoksa donem ve tum kisiler tek seferde (tek transaction) yazilir ve donem sayfasi acilir. Yanlis dosya yuklendiyse donem sayfasindaki `Donemi sil` donemi ve eklenen kisileri siler.

## 3. Donemler

Ana sayfa tum donemleri listeler: kisi sayisi, bekleyen, taslak olusan, hatali ve kontrol gereken sayilari. Donem adina tiklayinca donem sayfasi acilir. `Sil` donemi ve icindeki tum kisileri siler.

Hicbir donemle iliskisi olmayan eski kayitlar varsa ustte tek satirlik uyari ve `Sil` cikar.

## 4. Donem Sayfasi

- Arama kutusu ad, soyad veya TCKN ile listeyi aninda daraltir; durum listesi Bekliyor / Taslak olustu / Hatali / Kontrol gerekli filtrelerini verir.
- Satir aksiyonlari:
  - `Tekrar dene`: hatali kisi tekrar `Bekliyor` olur.
  - `Taslak var` / `Taslak yok`: `Kontrol gerekli` kisiyi portalda kontrol ettikten sonra sonuclandirir.
  - `Sil`: kisiyi siler.
- Tutar degistirme (ice aktarimdan sonra):
  - Taslagi henuz olusmamis kisilerin (`Bekliyor`, `Secildi` ve tekrar denenebilir hatalar) tutari satirda bir kutu olarak gorunur. Yeni tutari yazip Enter'a bas veya kutudan cik; aninda kaydedilir, kutu yesil yanar ve basliktaki toplam guncellenir. `Esc` degisikligi geri alir.
  - Tutar ice aktarimdaki kurallarla okunur: `1450`, `1.450`, `1450,50`, `1.450,50`.
  - `Taslak olustu`, `Kontrol gerekli` ve `Isleniyor` kisilerin tutari kilitlidir (duz yazi). Portalda taslak zaten eski tutarla olustugu icin burada degistirmek yaniltici olurdu; bu kural veritabani guncellemesinde de uygulanir.
  - Donemde taslak islemi calisirken tutarlar degistirilemez.
  - Her degisiklik eski ve yeni tutarla `app.log` dosyasina yazilir.
- Alt cubuk:
  - `Secilileri sil`: isaretli kisileri siler.
  - `Yeni tutar` + `N kisinin tutarini degistir`: isaretli kisilere tek seferde ayni tutari verir. Kilitli kisiler secime dahil olsa bile degismez; onay mesaji ve sonuc mesaji kac kisinin atlandigini soyler.
  - `N kisi icin taslak olustur`: isaretli ve `Bekliyor` durumundaki kisiler icin toplu taslak islemini baslatir. Portal hazir degilse buton pasiftir.

Islem arka planda calisir; sayfa ilerlemeyi kendisi gunceller. `Durdur` portalda islenen kisi bittikten sonra durdurur. Bitince ustte ozet satiri ve `Ayrintilar` (hata mesaji, ekran goruntusu yolu) gorunur.

Toplu islem sirasinda bilgisayarin uyumasi engellenir (`SLEEP_PREVENTION_*` ayarlari); islem bitince otomatik kapanir.

## 5. Tum Kayitlar

Butun donemlerdeki kisileri tek listede gosterir. Ad/soyad/TCKN, donem ve durum ile aranir; satir aksiyonlari donem sayfasiyla aynidir.

## 6. Portal Oturumu

1. `Portal` rozetine tikla > `Giris yap`. Tarayici acilir, `.env` icindeki kullanici bilgileri doldurulur.
2. Kod istenirse acilan tarayiciya gir, sonra `2FA kodunu girdim`.
3. Durum `Hazir` olunca donem sayfasindan taslak olusturulabilir.

## 7. Durumlar

- `Bekliyor`: islenmeyi bekliyor.
- `Taslak olustu`: portalda taslak olusturuldu.
- `Hata: TCKN gecersiz`: TCKN/VKN portal validasyonundan gecmedi.
- `Hata: isim uyusmuyor`: Turmob ad/soyad yerel kayitla eslesmedi. Buyuk/kucuk harf, bosluk ve sadece `ı/i/İ/I`, `u/ü`, `o/ö` farki tolere edilir; toleransla gecen kayit `data/logs/app.log` icine `harf toleransiyla eslesti` uyarisi yazar. `ş/s`, `ç/c`, `ğ/g` veya farkli isim yine uyusmazliktir.
- `Hata: Turmob servisi`: Turmob sorgusunda servis hatasi.
- `Atlandi: e-Fatura mukellefi`: kisi e-Fatura mukellefi.
- `Hata: portal zaman asimi`: portal Taslak Kaydet oncesi zamaninda yanit vermedi.
- `Yarida kaldi: oturum dustu`: portal oturumu islem sirasinda kapandi.
- `Kontrol gerekli`: Taslak Kaydet tiklandi ama sonuc dogrulanamadi. Portaldaki Taslaklar listesini kontrol edip `Taslak var` / `Taslak yok` ile sonuclandirin; otomatik yeniden denenmez.

Hata ayrintisi icin ekran goruntuleri `data/logs/screenshots/`, log `data/logs/app.log` altindadir.

## 8. Silme Hakkinda

- Silme yalnizca bu paneldeki kayitlari siler; portalda olusmus taslaklar silinmez.
- Taslak olusmus bir donemi silip ayni kisileri tekrar yuklerseniz portalda mukerrer taslak olusabilir.
- Islenmekte olan kisi ve islem suren donem silinemez.

## 9. Guvenli Kullanim Notlari

- Ilk canli kullanimda kucuk bir kisi grubuyla deneyin.
- Taslak olusturmadan once donem adini ve secili kisi sayisini kontrol edin.
- `Kontrol gerekli` kisileri portalda bakmadan `Taslak yok` ile kapatmayin.
