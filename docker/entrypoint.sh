#!/usr/bin/env bash
# Container entrypoint — minimum dogrulama + state dizini hazirlik + main.py.
#
# Coklu instance pratikleri:
#   - Her container kendi GATEWAY_CODE/.env dosyasiyla calisir
#   - GATEWAY_STATE_DIR (varsayilan /app/.gateway_state) volume olarak mount
#     edilmeli. Aksi halde restart sonrasi instance_id ve outbox kuyrugu kaybolur.
#   - WORKER_HEALTH_PORT container icinde sabit (8020); host tarafinda farkli
#     -p mappingleri ile coklu instance erisilebilir kilinir.
#
set -euo pipefail

if [[ -z "${GATEWAY_CODE:-}" || -z "${GATEWAY_TOKEN:-}" ]]; then
    echo "[entrypoint] HATA: GATEWAY_CODE ve GATEWAY_TOKEN env zorunludur." >&2
    echo "             docker run --env-file <gateway>.env ... seklinde gecirin." >&2
    exit 64
fi

# State dir mevcut degilse olustur. Volume mount edilmis olmali; degilse
# warning. (Persist olmazsa instance_id her restart'ta degisir.)
state_dir="${GATEWAY_STATE_DIR:-/app/.gateway_state}"
mkdir -p "${state_dir}"
if ! mountpoint -q "${state_dir}" 2>/dev/null; then
    if [[ "${GATEWAY_STATE_PERSIST_WARN:-1}" = "1" ]]; then
        echo "[entrypoint] UYARI: ${state_dir} bir volume degil; restart'ta veri kaybolur." >&2
        echo "             docker run -v <vol>:${state_dir} veya compose volumes ile baglanmali." >&2
    fi
fi

echo "[entrypoint] starting code=${GATEWAY_CODE} mode=${GATEWAY_MODE:-mock} library=${DNP3_LIBRARY:-dnp3py}"

exec "$@"
