# Active Context

Mevcut aktif is Faz 6 coklu batch islemeyi tamamlamak ve Faz 7 sertlestirme/dokumantasyon fazina hazir hale gecmektir.

Hedefler:

- Faz 2 secim ve batch hazirlik akisi tamamlandi.
- Faz 3 browser session yonetimi tamamlandi.
- Playwright browser manager ve portal session manager eklendi.
- Login formu .env credential'lariyla doldurulur.
- 2FA ekrani beklenir, kullanici kodu manuel girer.
- 2FA sonrasi session hazirligi e-Arsiv menu linki veya URL fallback ile dogrulanir.
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

Sonraki ana is Faz 7 sertlestirme, selector iyilestirmeleri, retry/backoff ve genel temizliktir.
