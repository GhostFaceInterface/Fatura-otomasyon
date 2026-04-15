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

Henuz tamamlanmayan sonraki isler:

- Faz 4: tek kayit icin taslak fatura POC
- Faz 5: portal hata senaryolari
- Faz 6: coklu batch
- Faz 7: sertlestirme ve dokumantasyon iyilestirme
