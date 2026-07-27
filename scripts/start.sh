#!/usr/bin/env bash
# Start the local operator panel. This script never starts a portal session or a batch.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
ENV_FILE="$PROJECT_DIR/.env"

cd "$PROJECT_DIR"

configured_port="${APP_PORT:-}"
if [[ -z "$configured_port" && -f "$ENV_FILE" ]]; then
  configured_port="$(awk -F= '$1 == "APP_PORT" { print substr($0, index($0, "=") + 1); exit }' "$ENV_FILE" | tr -d '\r')"
fi
APP_PORT="${configured_port:-8010}"

if [[ ! "$APP_PORT" =~ ^[1-9][0-9]{0,4}$ ]] || (( APP_PORT > 65535 )); then
  printf '%s\n' "APP_PORT 1 ile 65535 arasında sayısal bir değer olmalıdır."
  exit 1
fi
if [[ "$APP_PORT" == "8000" ]]; then
  printf '%s\n' "Güvenlik kısıtı: 8000 portu kullanılamaz. APP_PORT değerini örneğin 8010 yapın."
  exit 1
fi
export APP_PORT

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  PYTHON_BIN=""
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)'; then
      PYTHON_BIN="$candidate"
      break
    fi
  done

  if [[ -z "$PYTHON_BIN" ]]; then
    printf '%s\n' "Python 3.11, 3.12 veya 3.13 gerekli; uygun bir Python bulunamadı."
    exit 1
  fi

  printf '%s\n' "İzole Python ortamı hazırlanıyor ($PYTHON_BIN)..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r requirements.txt
fi

PYTHON_BIN="$VENV_DIR/bin/python"

if ! "$PYTHON_BIN" -c 'import fastapi, jinja2, pandas, playwright, uvicorn' >/dev/null 2>&1; then
  printf '%s\n' "Eksik Python bağımlılıkları kuruluyor..."
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

printf '%s\n' "Playwright Chromium hazır olup olmadığı denetleniyor..."
"$PYTHON_BIN" -m playwright install chromium

if [[ ! -f "$ENV_FILE" ]]; then
  printf '%s\n' "Bilgi: .env bulunamadı; panel güvenli varsayılanlarla açılacak."
  printf '%s\n' "Portal oturumu gerektiğinde PORTAL_USERNAME ve PORTAL_PASSWORD değerlerini .env veya kabuk ortamında sağlayın."
elif ! grep -Eq '^PORTAL_USERNAME=.+$' "$ENV_FILE" || ! grep -Eq '^PORTAL_PASSWORD=.+$' "$ENV_FILE"; then
  printf '%s\n' "Uyarı: PORTAL_USERNAME veya PORTAL_PASSWORD boş. Panel açılır; portal oturumu başlatıldığında bu alanlar istenir."
fi

printf '%s\n' "Lokal panel başlatılıyor: http://127.0.0.1:$APP_PORT"
printf '%s\n' "Bu komut portal oturumu açmaz ve fatura/taslak oluşturmaz; durdurmak için Ctrl+C kullanın."
exec "$PYTHON_BIN" run.py
