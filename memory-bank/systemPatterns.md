# System Patterns

- FastAPI uygulamasi server-rendered Jinja2 ekranlari ve hafif JSON API sunar.
- SQLite erisimi repository katmaninda toplanir.
- Import ve validasyon servisleri UI route'larindan ayridir.
- Secim kurallari `SelectionService` icinde tutulur; repository sadece kontrollu PENDING/SELECTED gecislerini uygular.
- Batch hazirligi `BatchService` uzerinden preview kontratiyla baslatilir.
- Durum degerleri `InvoiceStatus` enum'u ile merkezi tutulur.
- Portal otomasyonu sonraki fazlarda `automation/` katmaninda Playwright ile ayrilacak.
- Kayit bazli hatalar batch'i durdurmayacak; session-level kritik hatalar batch'i guvenli durduracak.
