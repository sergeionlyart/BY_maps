"""Тесты INF-16 `upkeep_fiscal`. Классификация метрик и приоритет уровня
консолидации - на синтетических данных; сверка с лично перепроверенными
цифрами пилота (docs/preregistration/upkeep-v0.1.md, поправка 2026-08-01)
- на реальных файлах."""
import json

from etl.upkeep_fiscal import (build, classify_metric, infer_consolidation,
                               normalize_district, PILOT_DIR)


def test_classify_revenue_total():
    assert classify_metric("доходы всего") == "revenue_total"
    assert classify_metric("доходы всего (исполнено)") == "revenue_total"
    assert classify_metric("ВСЕГО ДОХОДОВ") == "revenue_total"  # порядок слов не важен (substring-проверка)


def test_classify_expenditure_total():
    assert classify_metric("расходы всего") == "expenditure_total"
    assert classify_metric("расходы всего (районный бюджет)") == "expenditure_total"


def test_classify_sections():
    assert classify_metric("расходы на ЖКХ") == "exp_housing"
    assert classify_metric("расходы на образование") == "exp_education"
    assert classify_metric("расходы на здравоохранение") == "exp_health"
    assert classify_metric("расходы на госуправление") == "exp_governance"
    assert classify_metric("расходы на общегосударственную деятельность (госуправление)") == "exp_governance"


def test_classify_own_revenue_and_transfers():
    assert classify_metric("собственные доходы (налоговые + неналоговые)") == "own_revenue"
    assert classify_metric("безвозмездные поступления/трансферты") == "transfers"


def test_classify_excludes_shares_and_deltas():
    assert classify_metric("расходы на ЖКХ (доля от расходов всего, консолидировано)") is None
    assert classify_metric("прирост собственных доходов к предыдущему году") is None
    assert classify_metric("исполнение доходов консолидированного бюджета за 1-е полугодие (%)") is None


def test_classify_no_match():
    assert classify_metric("нечто не относящееся к бюджету") is None


def test_infer_consolidation_explicit_field():
    assert infer_consolidation({"is_consolidated": True}) is True
    assert infer_consolidation({"is_consolidated": False}) is False


def test_infer_consolidation_from_text_m1_pilot():
    assert infer_consolidation({"metric": "доходы всего (консолидированный бюджет района)"}) is True
    assert infer_consolidation({"metric": "доходы всего (только районный бюджет)"}) is False
    assert infer_consolidation({"metric": "доходы всего"}) is None


def test_normalize_district_skips_plan_and_shares():
    figures = [
        {"year": "2025", "metric": "доходы всего", "amount_byn_new_rubles": 100.0,
         "is_execution_not_plan": True, "source_url": "http://x"},
        {"year": "2025", "metric": "доходы всего (план)", "amount_byn_new_rubles": 999.0,
         "is_execution_not_plan": False, "source_url": "http://x"},
        {"year": "2025", "metric": "доходы всего (доля от чего-то, %)", "amount_byn_new_rubles": 50.0,
         "is_execution_not_plan": True, "source_url": "http://x"},
    ]
    import tempfile, pathlib
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"research": {"figures": figures}}, f)
        path = pathlib.Path(f.name)
    rows = normalize_district(path)
    path.unlink()
    assert len(rows) == 1
    assert rows[0]["field"] == "revenue_total"
    assert rows[0]["value_byn"] == 100.0


def test_normalize_district_prefers_consolidated():
    figures = [
        {"year": "2024", "metric": "доходы всего (только районный бюджет)",
         "amount_byn_new_rubles": 100.0, "is_execution_not_plan": True, "source_url": "http://a"},
        {"year": "2024", "metric": "доходы всего (консолидированный бюджет района)",
         "amount_byn_new_rubles": 120.0, "is_execution_not_plan": True, "source_url": "http://b"},
    ]
    import tempfile, pathlib
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"research": {"figures": figures}}, f)
        path = pathlib.Path(f.name)
    rows = normalize_district(path)
    path.unlink()
    assert len(rows) == 1
    assert rows[0]["value_byn"] == 120.0
    assert rows[0]["is_consolidated"] is True


def test_real_pilot_ushacki_matches_personally_verified_figures():
    """Сверка с решением Ушачского райсовета №112 от 30.03.2026, лично
    перепроверенным (pdftotext) в майлстоуне 1."""
    path = PILOT_DIR / "r-ushacki.json"
    if not path.exists():
        return  # файл пилота может отсутствовать в некоторых окружениях CI
    rows = normalize_district(path)
    by_field_year = {(r["field"], r["year"]): r["value_byn"] for r in rows}
    assert abs(by_field_year[("revenue_total", "2025")] - 57206576.19) < 0.01
    assert abs(by_field_year[("expenditure_total", "2025")] - 54634283.31) < 0.01


def test_build_runs_on_real_pilot_data():
    if not PILOT_DIR.exists():
        return
    rows = build()
    assert len(rows) > 0
    districts = {r["district_id"] for r in rows}
    assert "r-ushacki" in districts
