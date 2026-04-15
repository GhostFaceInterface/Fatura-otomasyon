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

Henuz tamamlanmayan sonraki isler:

- Faz 6: coklu batch
- Faz 7: sertlestirme ve dokumantasyon iyilestirme
