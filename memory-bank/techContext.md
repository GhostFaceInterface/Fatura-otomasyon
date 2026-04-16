# Tech Context

- Python 3.11+
- FastAPI
- Jinja2
- Pandas
- openpyxl
- SQLite
- python-dotenv
- Playwright, Faz 3 ve sonrasi icin hazir bagimlilik
- pytest

Uygulama `python run.py` ile `127.0.0.1:8000` adresinde calisir. Runtime verileri `data/` altinda tutulur.

Playwright Python paketi `requirements.txt` ile kurulur, ancak browser binary'leri ayrica indirilmelidir. Ilk kurulumda veya cache temizlendiyse `venv/bin/python -m playwright install chromium` calistirilmelidir.

Faz 6 ve son faz icin ek runtime ayarlari:

- `NAVIGATION_RETRY_COUNT`: Basari/hata sonrasi sonraki kayit icin temiz e-Arsiv olustur sayfasina donus retry sayisi. Varsayilan `2`.
- `FIELD_WAIT_TIMEOUT_MS`: Kritik form alanlarini bekleme suresi. Varsayilan `30000`.
- `REDIRECT_WAIT_TIMEOUT_MS`: Taslak kaydetme sonrasi `/EArchive/Drafts` redirect bekleme suresi. Varsayilan `30000`.
- `TURMOB_LOOKUP_RETRY_COUNT`: Turmob sonrasi ad/soyad alanlarini okuma retry sayisi. Varsayilan `2`.
- `RETRY_BACKOFF_BASE_MS`: Kisa artan bekleme icin baz sure. Varsayilan `500`.
- `TAX_SCHEME_PREFILL_WAIT_MS`: TCKN girildikten sonra vergi dairesi alaninin otomatik dolmasini bekleme suresi. Varsayilan `2000`.
- `DRAFT_SAVE_WAIT_MS`: Taslak Kaydet tiklandiktan sonra portal yuklenmesini bekleme suresi. Varsayilan `2000`.

Faz 7 oncesi kritik tamamlamalar:

- SQLite schema additive migration kullanir; `import_batches` ve `invoice_records.batch_id` eski lokal DB'lere eklenir.
- Excel import icin `pandas.ExcelFile` sheet listesi ve `read_excel(sheet_name=...)` kullanilir.
- Login basari sinyali olarak `/Home/Index` kullanilir; 2FA sayfasi cikmazsa session READY kabul edilir.

Son faz:

- `invoice_automation/app/utils/retry.py` merkezi kisa retry/backoff helper saglar.
- Operasyon dokumantasyonu `README.md`, `docs/USAGE_GUIDE.md` ve `docs/OPERATIONS_CHECKLIST.md` icinde tutulur.
