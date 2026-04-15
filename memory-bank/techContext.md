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

Faz 6 icin ek runtime ayari:

- `NAVIGATION_RETRY_COUNT`: Basari/hata sonrasi sonraki kayit icin temiz e-Arsiv olustur sayfasina donus retry sayisi. Varsayilan `2`.

Faz 7 oncesi kritik tamamlamalar:

- SQLite schema additive migration kullanir; `import_batches` ve `invoice_records.batch_id` eski lokal DB'lere eklenir.
- Excel import icin `pandas.ExcelFile` sheet listesi ve `read_excel(sheet_name=...)` kullanilir.
- Login basari sinyali olarak `/Home/Index` kullanilir; 2FA sayfasi cikmazsa session READY kabul edilir.
