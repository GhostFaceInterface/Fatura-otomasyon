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
