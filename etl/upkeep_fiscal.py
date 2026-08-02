"""INF-16 `upkeep`: нормализация исполнения местных бюджетов (майлстоун 2).

Вход: `data/raw/fiscal_pilot_2026-08-01/r-*.json` (10 пилотных районов,
майлстоун 1) + `data/raw/fiscal_full_2026-08-02/r-*.json` (оставшиеся 108
районов, майлстоун 2, если каталог существует). Каждый файл - результат
research-агента (+ verify-агента, если район попал в случайную выборку
скептика) с полем `figures[]`: свободнотекстовые метрики, суммы, статус
план/исполнение, статус консолидации.

Свободный текст метрик у разных районов сформулирован по-разному
(«доходы всего», «доходы районного бюджета всего», «ВСЕГО ДОХОДОВ» и т.д.) -
`classify_metric()` ниже сопоставляет их с фиксированным набором
канонических полей по ключевым словам. Это единственный содержательный
классификатор этого модуля; он не идеален (см. `docs/decisions/INF-16.md`
для найденных им особых случаев) и разбирается в открытую, а не скрыт
внутри одной непрозрачной функции.

Правило отбора: только ИСПОЛНЕНИЕ (`is_execution_not_plan=True`), никогда
план/прогноз/утверждено - `upkeep_burden` требует реальных денег (гейт G-7).
Приоритет уровня консолидации - консолидированный (район+сельсоветы), по
решению владельца (поручение M2, вопрос 2); при отсутствии консолидированной
цифры используется районная с явным флагом `consolidation_level=district_only`.

Запуск: python -m etl.upkeep_fiscal -> data/curated/upkeep_fiscal.csv
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .common import ROOT

CURATED = ROOT / "data" / "curated"
PILOT_DIR = ROOT / "data" / "raw" / "fiscal_pilot_2026-08-01"
FULL_DIR = ROOT / "data" / "raw" / "fiscal_full_2026-08-02"
OUT_CSV = CURATED / "upkeep_fiscal.csv"

# Канонические поля и ключевые слова классификации (порядок важен - более
# специфичные категории проверяются раньше общих "всего").
FIELD_KEYWORDS = [
    ("own_revenue", ("собственные доходы",)),
    ("transfers", ("безвозмездн", "трансферт")),
    ("exp_housing", ("жкх", "жилищно-коммунальн")),
    ("exp_education", ("образован",)),
    ("exp_health", ("здравоохранен",)),
    ("exp_governance", ("госуправлен", "общегосударствен")),
    ("exp_transport", ("транспорт",)),
    ("revenue_total", ("доход", "всего")),
    ("expenditure_total", ("расход", "всего")),
]

# Метрики, которые НИКОГДА не классифицируются как абсолютный уровень, даже
# если совпали по ключевым словам (доли/дельты/проценты - см. пилот M1,
# запись "прирост собственных доходов" и "доля от расходов всего").
EXCLUDE_MARKERS = ("доля", "%", "дельта", "прирост", "процент")


def classify_metric(metric: str) -> str | None:
    low = metric.lower()
    if any(m in low for m in EXCLUDE_MARKERS):
        return None
    for field, keywords in FIELD_KEYWORDS:
        if field in ("revenue_total", "expenditure_total"):
            if all(k in low for k in keywords):
                return field
        else:
            if any(k in low for k in keywords):
                return field
    return None


def infer_consolidation(figure: dict) -> bool | None:
    """True=консолидированный, False=только районный, None=не определено.
    Приоритет - явное поле is_consolidated (данные майлстоуна 2); для
    пилотных файлов майлстоуна 1 (поля нет) - разбор текста метрики."""
    if "is_consolidated" in figure:
        return figure["is_consolidated"]
    low = figure.get("metric", "").lower()
    if "консолидир" in low:
        return True
    if "только районный" in low or "без бюджетов сельсовет" in low or \
       ("районный бюджет" in low and "консолид" not in low):
        return False
    return None


def load_district_files() -> list[Path]:
    files = []
    if PILOT_DIR.exists():
        files += sorted(PILOT_DIR.glob("r-*.json"))
    if FULL_DIR.exists():
        files += sorted(FULL_DIR.glob("r-*.json"))
    return files


def normalize_district(path: Path) -> list[dict]:
    """Возвращает строки (district_id, year, field, value, is_consolidated,
    source_url) - одна строка на (год, поле, уровень консолидации), с
    приоритетом консолидированного при дублировании (год, поле)."""
    d = json.loads(path.read_text())
    rid = path.stem
    research = d.get("research", d)  # пилотные файлы вложены в research/verify
    figures = research.get("figures", [])

    by_key: dict[tuple[str, str], dict] = {}
    for fig in figures:
        if not fig.get("is_execution_not_plan"):
            continue
        amount = fig.get("amount_byn_new_rubles")
        if amount is None:
            continue
        field = classify_metric(fig.get("metric", ""))
        if field is None:
            continue
        is_cons = infer_consolidation(fig)
        key = (fig["year"], field)
        existing = by_key.get(key)
        # приоритет: консолидированный > неизвестно > районный (решение M2 вопрос 2)
        rank = {True: 2, None: 1, False: 0}
        if existing is None or rank.get(is_cons, 1) > rank.get(existing["is_consolidated"], 1):
            by_key[key] = {
                "district_id": rid, "year": fig["year"], "field": field,
                "value_byn": amount, "is_consolidated": is_cons,
                "source_url": fig.get("source_url", ""),
            }
    return list(by_key.values())


def build() -> list[dict]:
    rows = []
    for path in load_district_files():
        rows += normalize_district(path)
    return rows


def main() -> None:
    rows = build()
    CURATED.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["district_id", "year", "field", "value_byn", "is_consolidated", "source_url"])
        for r in rows:
            w.writerow([r["district_id"], r["year"], r["field"], r["value_byn"],
                       r["is_consolidated"], r["source_url"]])
    districts = {r["district_id"] for r in rows}
    print(f"upkeep_fiscal: {len(rows)} строк, {len(districts)} районов с хотя бы "
          f"одним нормализованным полем -> {OUT_CSV}")


if __name__ == "__main__":
    main()
