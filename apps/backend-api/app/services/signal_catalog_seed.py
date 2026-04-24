"""Horstmann Smart Navigator 2.0 standart sinyal kataloğu seed'i.

Sinyal tanımları `app/data/horstmann_sn2_signals.json` içinde saklanır.
Cihazın DNP3 listesi master + 2 satellite üzerinden toplam 3 faz bilgisini
getirdiği için her sinyal kaynağa (`master`, `sat01`, `sat02`) göre ayrı
`key` ile tutulur. Bu sayede alarmın hangi fazdan/uniteden geldiği karışmaz.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.signal_catalog import SignalCatalog


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "horstmann_sn2_signals.json"


def load_default_signals() -> list[dict]:
    """Horstmann SN2 varsayılan sinyal listesini JSON'dan yükler."""
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as fh:
        items = json.load(fh)
    if not isinstance(items, list):
        return []
    return items


# Geriye uyumluluk için eski import yolları (app.main tarafında log/diagnostik kullanabilir).
DEFAULT_SIGNALS: list[dict] = load_default_signals()


_MUTABLE_FIELDS = (
    "label",
    "unit",
    "description",
    "source",
    "dnp3_class",
    "data_type",
    "dnp3_object_group",
    "dnp3_index",
    "scale",
    "offset",
    "supports_alarm",
    "display_order",
)


def seed_default_signals(db: Session) -> dict:
    """Upsert: Horstmann SN2 standart sinyallerini ekler veya günceller.

    Dönüş: {"inserted": N, "updated": M, "total": T}
    - Aynı `key` varsa alanları günceller (scale/dnp3_index vb. değişmişse).
    - Yeni `key`'ler eklenir.
    - Mevcut kayıtlardan seed listesinde olmayanlar **silinmez**
      (kurulumcunun eklediği özel sinyaller korunur).
    """
    items = load_default_signals()
    if not items:
        return {"inserted": 0, "updated": 0, "total": 0, "skipped": True}

    existing = {row.key: row for row in db.scalars(select(SignalCatalog)).all()}
    inserted = 0
    updated = 0

    for data in items:
        key = data.get("key")
        if not key:
            continue
        current = existing.get(key)
        if current is None:
            db.add(SignalCatalog(**data))
            inserted += 1
            continue
        changed = False
        for field in _MUTABLE_FIELDS:
            new_value = data.get(field, getattr(current, field))
            if getattr(current, field) != new_value:
                setattr(current, field, new_value)
                changed = True
        if changed:
            updated += 1

    db.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "total": inserted + updated,
        "skipped": False,
    }
