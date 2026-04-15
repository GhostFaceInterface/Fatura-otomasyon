# Progress

## Faz 1

Tamamlandi:

- Calisan FastAPI iskeleti
- SQLite veri katmani
- Import validasyonu
- CSV/Excel dosya okuma
- Kayit listeleme ekrani
- Temel testler

## Faz 2

Tamamlandi:

- Kayit secimi
- Durum yonetimi
- Batch servis iskeleti
- Temel progress modeli

Notlar:

- PENDING kayitlar SELECTED durumuna alinabilir.
- Secimi kaldirilan SELECTED kayitlar PENDING durumuna doner.
- Basarili veya hatali son durumdaki kayitlar secim guncellemesiyle degistirilmez.
- `/batch` ekrani secili kayitlari, toplam USD tutarini ve Faz 2 progress iskeletini gosterir.

## Faz 3

Tamamlandi:

- Playwright browser lifecycle icin `BrowserManager`
- Portal login ve manuel 2FA icin `PortalSessionManager`
- `/session` UI ekrani
- `/api/session/*` endpointleri
- `.env.example` portal ve Playwright alanlari
- Session state/log mesaji akisi

Notlar:

- Browser headful calisir; default `PLAYWRIGHT_HEADLESS=false`.
- 2FA kodu otomatik girilmez ve `.env` icinde tutulmaz.
- Session hazir kontrolunde oncelik e-Arsiv menu linkindedir.
- Faz 4'te ayni session/page uzerinden e-Arsiv olusturma akisi eklenecek.

## Faz 4

Tamamlandi:

- `EArchiveNavigation` ile e-Arsiv menu ve olustur sayfasi navigasyonu
- `InvoiceFormFiller` ile USD, kur getir, TCKN, Turmob, il/ilce, mal/hizmet, fiyat, KDV ve istisna doldurma
- `PortalErrorDetector` ile invalid TCKN/e-Fatura/genel hata detection hook'u
- `DraftCreator` ile tek kayit uctan uca taslak POC
- `SingleDraftService` ile repository status/hata guncellemesi
- `/draft` UI ve `/api/draft/create` endpointi

Notlar:

- Faz 4 coklu kayit islemez.
- GIB'e gonderim yoktur, sadece `Taslak Kaydet` butonu kullanilir.
- Basarili kayit `SUCCESS_DRAFT_CREATED`, hata alan kayit anlamli FAILED/SKIPPED/ABORTED statusune gecer.
- Invalid TCKN ve e-Fatura metinleri portalda netlestikce Faz 5'te sertlestirilecek.

## Faz 5

Tamamlandi:

- Gercek SweetAlert dialog algilama: `Hata Oluştu`, `Bilgi`
- Turmob servis hatasi mapping: `Servis hatası oluştu` -> `TurmobServiceError` -> `FAILED_TURMOB_SERVICE_ERROR`
- Gecersiz VKN/TCKN mapping: `geçerli bir VKN/TCKN değeri değildir` -> `InvalidTCKNError` -> `FAILED_INVALID_TCKN`
- e-Fatura mukellefi mapping: `e-Fatura Mükellefine e-Arşiv Fatura Kesilemez` -> `EFaturaMukellefiError` -> `SKIPPED_EFATURA_MUKELLEFI`
- Dialog OK ile kapatma
- Hata aninda screenshot alma
- Taslak basarisini `/EArchive/Drafts` redirect'i ile dogrulama

Notlar:

- Tek kayit akisi crash etmez; hata sonucunu repository'ye yazar.
- Screenshotlar `data/logs/screenshots/` altinda record id ve stage ile tutulur.
- Faz 6 bu kayit bazli dayanikli akisi coklu batch'e tasiyacaktir.

## Faz 6

Tamamlandi:

- Secili ve PENDING/SELECTED durumundaki kayitlari batch icin filtreleme
- Deterministic id sirasiyla coklu kayit isleme
- `BatchRunner` ile mevcut `SingleDraftService` tek kayit akisini orkestre etme
- Kayit bazli FAILED/SKIPPED durumlarda batch'e devam etme
- ABORTED_SESSION_LOST ve temiz yeni kayit sayfasina donus hatalarinda batch'i guvenli durdurma
- Basari veya hata sonrasi sonraki kayit icin e-Arsiv olustur sayfasina retry ile donme
- Batch raporu: total, processed, success, skipped, failed, aborted, status dagilimi ve kayit detaylari
- `/batch/run` UI aksiyonu ve `/api/batch/run` JSON endpointi
- `NAVIGATION_RETRY_COUNT` config alani

Notlar:

- Batch run daha once SUCCESS/FAILED/SKIPPED/ABORTED durumuna gecmis kayitlari yeniden denemez.
- Basari sonrasi `/EArchive/Drafts` sayfasindan e-Arsiv olustur linkiyle temiz forma donulur.
- Hata sonrasi dialog Faz 5 katmaninda kapandiktan sonra form state'i terk edilip yeni olustur ekranina donulur.
- Bu faz websocket/canli progress kurmaz; senkron post/response sonuc raporu verir.

## Faz 7 oncesi kritik tamamlamalar

Tamamlandi:

- `import_batches` tablosu ve `invoice_records.batch_id` alanlari eklendi.
- Var olan lokal SQLite dosyalari icin additive migration mantigi eklendi.
- Import servisi sheet inspection, sheet secimi ve kolon mapping destekler.
- CSV import geriye uyumlu kalir; Excel icin kullanici secilen sheet'i import eder.
- Import sirasinda batch/fatura donemi adi alinir ve kayitlar o doneme baglanir.
- Records ekrani aktif fatura donemiyle calisir, ad/soyad ayri kolonlarda gosterilir.
- Records ekraninda uygun kayitlar icin tumunu sec checkbox'i vardir.
- Batch preview/run aktif fatura donemi icindeki secili PENDING/SELECTED kayitlarla calisir.
- Login sonrasi 2FA sayfasi, `/Home/Index` veya e-Arsiv menu sinyali ayirt edilir.
- 2FA gerekmezse session dogrudan READY olur.
- Turmob sonrasi portal ad/soyad alanlari okunur ve SQLite kaydiyla normalize edilerek karsilastirilir.
- Ad/soyad uyusmazligi `NameMismatchError` -> `FAILED_NAME_MISMATCH` olarak status'a yazilir.

Notlar:

- Fatura donemi izolasyonu artik operasyonel batch secimini belirler.
- Otomatik kolon alias mapping kaldirilmadi; explicit UI mapping birinci sinif akisa eklendi.
- Name mismatch kayit bazli hata kabul edilir, batch'i durdurmaz.

## Faz 7 / Son Faz Hardening

Tamamlandi:

- Session state bilgisi UI'da daha okunabilir hale getirildi.
- Batch ekraninda session durumu gorunur hale geldi.
- Session READY degilken batch run butonu UI'da disable edilir.
- Login sonrasi hazirlik kontrolu `/Home/Index` veya e-Arsiv menu sinyaline dayandirildi.
- `FIELD_WAIT_TIMEOUT_MS`, `REDIRECT_WAIT_TIMEOUT_MS`, `TURMOB_LOOKUP_RETRY_COUNT`, `RETRY_BACKOFF_BASE_MS` config alanlari eklendi.
- Merkezi `retry_with_backoff` helper eklendi.
- e-Arsiv olustur formu hazir kontrolu birden fazla kritik alanla yapilir.
- Sonraki kayit icin yeni olustur sayfasina donus retry/backoff ile sertlestirildi.
- Kur getir/Turmob tiklama ve Turmob ad/soyad alanlarini okuma daha dayanikli hale getirildi.
- Draft success redirect bekleme suresi ayri config ile yonetilir.
- Records ekranina aktif batch icinde ad/soyad/TCKN aramasi eklendi.
- Batch rapor detaylarina failed/skip/screenshot filtreleri eklendi.
- README operasyon odakli yeniden yazildi.
- `docs/USAGE_GUIDE.md` kullanici kilavuzu eklendi.
- `docs/OPERATIONS_CHECKLIST.md` operasyon checklist dosyasi eklendi.
- Test paketi 52 test ile basarili calisti.

Notlar:

- Buyuk mimari refactor yapilmadi.
- GIB gonderimi, queue, websocket veya otomatik yeniden deneme workflow'u eklenmedi.
- Sonraki adim canli ortamda kucuk pilot batch ile portal selector ve timing davranisini dogrulamaktir.

Henuz tamamlanmayan sonraki isler:

- Canli pilot sonrasi portal UI'da degisen selector veya metinler varsa kucuk uyarlama.
