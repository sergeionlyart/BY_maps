"""Координаты и русские названия городов из выгрузки Wikidata (SPARQL)."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _norm(s: str) -> str:
    return (s or "").lower().replace("’", "'").replace("ʼ", "'").strip()


def load_settlements(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    items: dict[str, dict] = {}
    for r in data["results"]["bindings"]:
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        it = items.setdefault(qid, {"qid": qid, "ru": None, "be": None,
                                    "lon": None, "lat": None, "admin": set()})
        if "ru" in r:
            it["ru"] = r["ru"]["value"]
        if "be" in r:
            it["be"] = r["be"]["value"]
        if "adminLabel" in r:
            it["admin"].add(r["adminLabel"]["value"])
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", r["coord"]["value"])
        if m:
            it["lon"], it["lat"] = float(m.group(1)), float(m.group(2))
    return list(items.values())


def match_city(be_name: str, oblast_admins: set[str], settlements: list[dict]) -> dict | None:
    """Ищет город по белорусскому названию; при неоднозначности предпочитает
    кандидата, чья административная привязка (adminLabel, например
    'Свислочский район') относится к той же области."""
    cand = [s for s in settlements if _norm(s["be"]) == _norm(be_name)]
    if not cand:
        return None
    if len(cand) > 1:
        pref = [s for s in cand if s["admin"] & oblast_admins]
        if pref:
            return pref[0]
    return cand[0]
