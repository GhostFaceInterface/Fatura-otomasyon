# Active Context

Mevcut aktif is son faz sertlestirme ve operasyon hazirligini tamamlamak olarak guncellendi.

Hedefler:

- Faz 2 secim ve batch hazirlik akisi tamamlandi.
- Faz 3 browser session yonetimi tamamlandi.
- Playwright browser manager ve portal session manager eklendi.
- Login formu .env credential'lariyla doldurulur.
- 2FA ekrani beklenir, kullanici kodu manuel girer.
- 2FA sonrasi session hazirligi `/Home/Index` veya e-Arsiv menu linki ile dogrulanir.
- Faz 4 tek kayit taslak POC tamamlandi.
- Hazir session ile e-Arsiv olustur ekranina gidilir.
- Tek kayit verisi forma yazilir, Taslak Kaydet butonu kullanilir.
- Sonuc repository status/hata alanlarina yazilir.
- Faz 5 hata senaryolari tamamlandi.
- Turmob servis hatasi, gecersiz VKN/TCKN ve e-Fatura mukellefi dialoglari gercek portal mesajlariyla yakalanir.
- Hata dialoglari OK ile kapatilir, screenshot alinir, status/hata alanlari repository'ye yazilir.
- Basari `/EArchive/Drafts` redirect'i ile dogrulanir.
- Faz 6 coklu batch isleme tamamlandi.
- Secili ve PENDING/SELECTED durumundaki kayitlar deterministic id sirasiyla islenir.
- Batch runner mevcut `SingleDraftService` tek kayit akisini cagirir; tek kayit otomasyonu yeniden yazilmamistir.
- Kayit bazli FAILED/SKIPPED durumlar batch'i durdurmaz.
- ABORTED_SESSION_LOST veya yeni e-Arsiv olustur sayfasina guvenli donus hatasi batch'i kritik nedenle durdurur.
- Batch sonunda UI/API uzerinden toplam success/skip/fail/abort ve kayit bazli detay raporu doner.
- Faz 7 oncesi kritik eksikler tamamlandi.
- Her import `import_batches` fatura donemine baglanir; `invoice_records.batch_id` ile donem izolasyonu saglanir.
- Excel import akisi sheet secimi, kolon mapping ve batch adi ile calisir; otomatik alias mapping fallback olarak kalir.
- Records ve batch ekranlari aktif fatura donemi baglaminda calisir.
- Records ekraninda uygun kayitlar icin `Tumunu Sec` checkbox'i vardir.
- Login sonrasi `/Home/Index`, e-Arsiv menu veya 2FA sayfasi ayirt edilir; 2FA yoksa session dogrudan READY olur.
- Turmob sonrasi `#txtPerson_FirstName` ve `#txtPerson_FamilyName` okunur; SQLite ad/soyad ile normalize edilerek karsilastirilir.
- Ad/soyad uyusmazligi `FAILED_NAME_MISMATCH` statusu ile kayit bazli fail olur ve batch devam eder.

- Son faz hardening tamamlandi.
- Login/session UI'da state ve kullanici yonlendirmesi daha net hale getirildi.
- Session READY degilse batch run UI'da engellenir; backend yine session check ile guvenli abort uretir.
- Navigation/form hazir kontrolu birden fazla kritik alanla yapilir.
- Retry/backoff icin merkezi helper ve config alanlari eklendi.
- Turmob ad/soyad alanlarini okuma ve Getir/Turmob tiklamalari kontrollu retry/backoff ile sertlestirildi.
- Draft success redirect timeout'u ayri config ile yonetilir.
- Records ekranina aktif batch icinde arama eklendi.
- Batch raporuna detay filtreleri eklendi: tum, failed, skip, screenshot olanlar.
- README, `docs/USAGE_GUIDE.md` ve `docs/OPERATIONS_CHECKLIST.md` operasyon odakli guncellendi.

Sonraki ana is canli kullanim oncesi kucuk kayit grubu ile pilot test ve portal selector davranislarini gercek ortamda dogrulamaktir.

Son bug fix:

- Import tutar parsing'i `parse_currency` ile merkezi hale getirildi.
- `$1.450`, `1.450`, `$850`, `$1,450` gibi binlik ayracli degerler deterministik olarak float tutara normalize edilir.
- `$1450.75` gibi decimal nokta iceren degerler decimal olarak korunur.
- Parse edilemeyen veya bos tutarlar satir bazli import hatasi olarak raporlanir ve loglanir.

Canli pilot bulgusu:

- Portal KDV 0 secilince "Fatura Tipi ISTISNA olarak degistirilmistir" bilgi mesajini gosterir; bu normaldir ve fail sayilmamalidir.
- TCKN girildikten sonra `#txtTaxSchemeName` dolu gelirse kisi daha once sorgulanmis kabul edilir, kontor harcamamak icin Turmob butonuna tekrar basilmaz.
- Taslak kaydet butonu sonrasi portal yuklenmesi icin 2 saniyelik kontrollu bekleme eklendi.

Yeni operasyonel ihtiyac:

- Toplu taslak olusturma sirasinda bilgisayar uyumamali.
- Sleep prevention sadece batch run scope'unda aktiftir; import/session/kayit listeleme sirasinda sistem uyku ayari degistirilmez.
- `.env` ile `SLEEP_PREVENTION_ENABLED`, `SLEEP_PREVENTION_PLATFORM` ve `SLEEP_PREVENTION_KEEP_DISPLAY_AWAKE` yonetilir.

UI sadeleştirme odağı:

- Ana arayuz teknik faz/POC terminolojisinden temizlenir.
- Kullanici akisi 4 adima indirildi: veri yukle, kayit sec, oturum ac, taslak olustur.
- Ana navigasyonda `Draft POC` ve `Health` gibi operasyon disi linkler gosterilmez.
- Kayıt ve taslak ekranlari sadece operasyon icin gerekli kolon ve aksiyonlari one cikarir.
- Gorsel tasarim ust navbar, 4 adimli is akisi, kartlar, durum rozetleri ve daha okunabilir tablolarla yeniden kuruldu.

Guncel frontend redesign:

- Kullanici istegiyle arayuz Bootstrap 5 tabanli profesyonel operasyon paneline tasindi.
- FastAPI + Jinja server-side rendering ve mevcut backend route/form action yapisi korunur.
- Base layout ust navbar, marka alani ve 4 adimli is akisi karti icerir.
- Records ekrani aktif fatura donemi, secili/gorunen/uygun metrikleri, filtre karti, aksiyon grubu ve Bootstrap tabloyla yeniden tasarlandi.
- Import, kolon mapping, session, batch ve draft POC ekranlari ayni Bootstrap kart/form/alert/table diliyle tutarli hale getirildi.
- Bootstrap CDN kullanilir; proje offline zorunlu hale gelirse Bootstrap asset'leri lokal olarak vendor edilebilir.

Kayit listesi UX guncellemesi:

- Records ekraninda filtre butonu kaldirildi; arama input'u yazildikca otomatik GET yenilemesiyle ad, soyad veya TCKN filtresini uygular.
- Dönem, durum, siralama alani ve siralama yonu degisiklikleri listeyi otomatik yeniler.
- Kayit listesi ad, soyad, TC kimlik no, tutar veya kayit sirasina gore artan/azalan siralanabilir.
- Secimi kaydet aksiyonu mevcut filtre ve siralama query parametrelerini koruyarak kayit ekranina doner.
- Canli arama `/api/records` ile tabloyu yerinde gunceller; secili kayit ID'leri filtre/siralama degisikliklerinde client state olarak korunur.
- Ad/soyad aramasi Python `casefold()` ile yapilir, boylece Turkce buyuk/kucuk harf eslesmesi SQLite `LIKE` davranisina bagli kalmaz.

README final dokumantasyon guncellemesi:

- `README.md` bastan sona final urun dokumani olarak yeniden yazildi.
- Odak program amaci, toplu e-Arsiv taslak fatura otomasyonu, kurulum, yetenekler, veri formati, operasyon akisi, durumlar, raporlama, mimari ve guvenlik notlari olarak belirlendi.
- Portal icindeki tek tek buton adimlari anlatilmadi; yuksek seviye toplu taslak fatura otomasyonu dili kullanildi.
- README icine renkli Shields rozetleri ve renkli Mermaid akis/mimari diagramlari eklendi.
