# System Patterns

- FastAPI uygulamasi server-rendered Jinja2 ekranlari ve hafif JSON API sunar.
- SQLite erisimi repository katmaninda toplanir.
- Import ve validasyon servisleri UI route'larindan ayridir.
- Secim kurallari `SelectionService` icinde tutulur; repository sadece kontrollu PENDING/SELECTED gecislerini uygular.
- Batch hazirligi `BatchService` uzerinden preview kontratiyla baslatilir.
- Playwright lifecycle `BrowserManager` icinde tutulur.
- Portal login ve manuel 2FA state akisi `PortalSessionManager` uzerinden yonetilir.
- e-Arsiv sayfa navigasyonu `EArchiveNavigation`, form doldurma `InvoiceFormFiller`, hata hook'lari `PortalErrorDetector`, tek kayit orchestration `DraftCreator` icinde tutulur.
- Tek kayit draft DB/status akisi `SingleDraftService` ile repository'ye yazilir.
- Durum degerleri `InvoiceStatus` enum'u ile merkezi tutulur.
- Portal otomasyonu `automation/` katmaninda Playwright ile ayrilir.
- Kayit bazli hatalar batch'i durdurmayacak; session-level kritik hatalar batch'i guvenli durduracak.
