#!/usr/bin/env bash
# yadnp3 (OpenDNP3 + Python binding, f0rw4rd fork) Linux derleme yardimcisi.
#
# Default Dockerfile build'i (DNP3_LIBRARY=dnp3py) bu scripti calistirmaz; sadece
# --build-arg DNP3_LIBRARY=yadnp3 verildiginde devreye girer. Cikti: $1 dizinine
# yadnp3-*.whl yazar.
#
# Linux'ta yadnp3 PyPI'de yok (sadece win_amd64 wheel'i yayinlanmis). Bu yuzden
# fork repo'yu klonluyor, cmake + pybind11 ile derliyoruz. ~5-10 dakika surer.
# Prod bir CI'da bu adim ayri bir base image olarak cache'lenmeli.
#
# Kullanim (containerda):
#   apt-get install -y build-essential cmake git libssl-dev pkg-config
#   ./build-yadnp3.sh /tmp/wheels

set -euo pipefail

OUTPUT_DIR="${1:-/tmp/wheels}"
REPO_URL="${YADNP3_REPO_URL:-https://github.com/f0rw4rd/opendnp3.git}"
REPO_REF="${YADNP3_REPO_REF:-3.2.1.1}"  # tag/branch
WORKDIR="${WORKDIR:-/tmp/yadnp3-src}"

mkdir -p "${OUTPUT_DIR}"

echo "[yadnp3-build] cloning ${REPO_URL}@${REPO_REF}"
rm -rf "${WORKDIR}"
git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" "${WORKDIR}" \
    || git clone --depth 1 "${REPO_URL}" "${WORKDIR}"

cd "${WORKDIR}"

echo "[yadnp3-build] installing build-time python deps"
pip install --upgrade pip
pip install pybind11 build setuptools wheel

# Repo yapisi: python binding pyproject.toml veya setup.py ile build edilebilir.
# f0rw4rd fork'unda `python/` alt klasoru var; tipik yapi.
if [[ -f "pyproject.toml" ]]; then
    echo "[yadnp3-build] building wheel (root pyproject)"
    python -m build --wheel --outdir "${OUTPUT_DIR}"
elif [[ -f "python/pyproject.toml" ]]; then
    echo "[yadnp3-build] building wheel (python/ subdir)"
    cd python
    python -m build --wheel --outdir "${OUTPUT_DIR}"
elif [[ -f "setup.py" ]]; then
    echo "[yadnp3-build] building wheel (legacy setup.py)"
    python setup.py bdist_wheel --dist-dir "${OUTPUT_DIR}"
else
    echo "[yadnp3-build] HATA: pyproject.toml veya setup.py bulunamadi. Repo yapisi degismis olabilir." >&2
    echo "             Manuel olarak yadnp3 wheel'i uretip ${OUTPUT_DIR} icine koyun." >&2
    exit 1
fi

echo "[yadnp3-build] success — produced wheels:"
ls -la "${OUTPUT_DIR}"/yadnp3*.whl 2>&1 || true
