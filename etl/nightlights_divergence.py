"""INF-08: исследовательские кандидаты-расхождения H1-H3 (stdlib).

Центральная идея релиза рилса v3: главная ценность спутниковых
наблюдений - там, где свет расходится со статистикой. Модуль
пересчитывает на production-данных три кандидата и полную
декомпозицию расхождения по всем районам.

Резидуал (ТЗ §10.3):
    D_r = dlog(L_r) - beta_class(r) * dlog(P_r)
где L - светимость зоны (аналитический ряд VNL), P - население,
beta - межрайонная эластичность из params/assumptions.json (класс
зоны). Локальные выводы - ТОЛЬКО по VIIRS 2012-2024 (ретро-сегмент
для страны/крупных зон, не для районной причинной диагностики).

Причинные формулировки запрещены: каждый кейс - «кандидат» с
конкурирующими гипотезами и списком данных для проверки; числа в
production-рилсе разрешены только при releaseApproved=true (гейт:
пересчёт на production-данных выполнен этим модулем).

Запуск: python -m etl.nightlights_divergence
  -> web/public/data/nightlights/research_candidates.json
  -> web/public/data/nightlights/divergence_decomposition.json
  -> docs/notes/nightlights_divergence_cases.md
"""
from __future__ import annotations

import json
import math

from .common import ROOT, OUT
from . import nightlights_model as M

NL = OUT / "nightlights"

# кейсы: агломерация НЕ смешивается с административным Минском -
# явный состав территорий; периоды сопоставимые (VIIRS)
CASES = [
    {
        "id": "minsk-agglomeration",
        "title_ru": "Минская агломерация",
        "title_be": "Мінская агламерацыя",
        "zones": ["BY-HM", "r-minski"],
        "zones_note": ("агломерация = Минск (BY-HM) + Минский район "
                       "(r-minski); административный Минск отдельно не "
                       "интерпретируется"),
        "period": [2012, 2024],
        "metric": "level",
        "metric_note": ("уровни: свет агломерации в абсолюте растёт "
                        "быстрее населения; ДОЛЯ агломерации в нац. "
                        "свете при этом снижается (сельский свет рос "
                        "быстрее) - метрикозависимое расхождение, само "
                        "по себе исследовательский вопрос"),
        "direction": "light_above_statistics",
        "hypotheses": ["commuting_mobility", "services_logistics",
                       "suburbanization_undercount",
                       "higher_lighting_per_capita",
                       "built_area_expansion"],
        "check_ru": ("маятниковая мобильность, ввод жилья, занятость по "
                     "месту работы, дороги и развязки, площадь застройки, "
                     "энергопотребление, услуги и логистика; свет и "
                     "площадь следа раздельно"),
    },
    {
        "id": "smolevichi-zhodino",
        "title_ru": "Смолевичи–Жодино",
        "title_be": "Смалявічы–Жодзіна",
        "zones": ["r-smalavicki"],
        "zones_note": ("Смолевичский район включает Жодино (город "
                       "областного подчинения) и БелАЗ - подписывать "
                       "географически как зону Смолевичи-Жодино"),
        "period": [2019, 2024],
        "metric": "share",
        "metric_note": ("доли в национальном свете (гасят продуктовый "
                        "скачок VNL-2021, который в уровнях перекрывает "
                        "сигнал); согласуется с v1-индексом к тренду"),
        "direction": "light_below_statistics",
        "hypotheses": ["industrial_load_change", "lighting_efficiency",
                       "population_measurement_lag",
                       "industrial_site_lighting_change",
                       "commuting_without_residence"],
        "check_ru": ("физические индексы производства, выпуск/экспорт "
                     "БелАЗ, занятость и смены, энергопотребление, "
                     "грузоперевозки, вакансии/зарплата, миграция, "
                     "программы замены освещения; свет отдельно для "
                     "жилой зоны, завода, дорог"),
    },
    {
        "id": "astravets",
        "title_ru": "Островец",
        "title_be": "Астравец",
        "zones": ["r-astraviecki"],
        "zones_note": "Островецкий район (строительство и ввод БелАЭС)",
        "period": [2012, 2024],
        "metric": "share",
        "metric_note": ("доли с 2012 года - охватывает строительную "
                        "фазу БелАЭС (рост доли света с 0,39% до 0,67%)"),
        "direction": "light_above_statistics",
        "hypotheses": ["large_infrastructure", "construction_lighting",
                       "roads_engineering", "services_housing_growth",
                       "lit_area_expansion_without_population"],
        "check_ru": ("хронология строительства/ввода БелАЭС, свет "
                     "площадки отдельно от населённых пунктов, персонал "
                     "(включая временный), ввод жилья, занятость, "
                     "энергопотребление, дороги; устойчивость света "
                     "после строительной фазы"),
    },
]

STATUS = "candidate"    # кандидат | исследуется | подтверждено частично
                        # | объяснение не установлено


def _pop(data, zid, year):
    v = data.get(zid)
    p = v["pop"].get(str(year)) if v else None
    return float(p[0]) if p else None


def _light(night_rows, zid, year):
    r = night_rows[zid]
    return r["light"].get(str(year))


def _nat_pop(data, rows, year):
    return sum(_pop(data, z, year) or 0 for z in rows)


def decomposition(night: dict, data: dict, assump: dict) -> list[dict]:
    """Декомпозиция расхождения по всем 119 зонам, 2012->2024.

    Обе метрики: уровни (несут продуктовый скачок VNL-2021 - флаг) и
    доли в национальном свете/населении (скачок сокращается)."""
    cls = M.zone_class(assump)
    betas = assump["model"]["beta"]
    rows = {r["id"]: r for r in night["rows"]}
    np0, np1 = _nat_pop(data, rows, 2012), _nat_pop(data, rows, 2024)
    out = []
    for zid in sorted(rows):
        l0, l1 = _light(rows, zid, 2012), _light(rows, zid, 2024)
        p0, p1 = _pop(data, zid, 2012), _pop(data, zid, 2024)
        if not (l0 and l1 and p0 and p1):
            continue
        ls0 = rows[zid]["lshare"]["2012"]
        ls1 = rows[zid]["lshare"]["2024"]
        zcls = cls.get(zid, "rural")
        beta = betas[zcls]
        dl = math.log(l1 / l0)
        dp = math.log(p1 / p0)
        dls = math.log(ls1 / ls0)
        dps = math.log((p1 / np1) / (p0 / np0))
        out.append({
            "id": zid,
            "class": zcls,
            "period": [2012, 2024],
            "observedLightChange": round(dl, 4),
            "populationChange": round(dp, 4),
            "beta": beta,
            "expectedLightChange": round(beta * dp, 4),
            "residualLevel": round(dl - beta * dp, 4),
            "residualShare": round(dls - beta * dps, 4),
            "qualityFlags": ["vnl_2021_step_in_level_metric",
                             "vnl_2012_partial_first_year"],
            "confidence": "high" if l0 > 2000 else "medium",
        })
    return out


def case_metrics(case: dict, night: dict, data: dict,
                 assump: dict) -> dict:
    """Резидуал кейса по выбранной метрике (level|share, ТЗ §10.3
    допускает обе: «L — светимость или доля в национальном свете»);
    вторая метрика считается для прозрачности."""
    cls = M.zone_class(assump)
    betas = assump["model"]["beta"]
    rows = {r["id"]: r for r in night["rows"]}
    y0, y1 = case["period"]

    def both(metric):
        if metric == "share":
            L0 = sum(rows[z]["lshare"][str(y0)] for z in case["zones"])
            L1 = sum(rows[z]["lshare"][str(y1)] for z in case["zones"])
            np0, np1 = _nat_pop(data, rows, y0), _nat_pop(data, rows, y1)
            P0 = sum(_pop(data, z, y0) or 0 for z in case["zones"]) / np0
            P1 = sum(_pop(data, z, y1) or 0 for z in case["zones"]) / np1
        else:
            L0 = sum(_light(rows, z, y0) or 0 for z in case["zones"])
            L1 = sum(_light(rows, z, y1) or 0 for z in case["zones"])
            P0 = sum(_pop(data, z, y0) or 0 for z in case["zones"])
            P1 = sum(_pop(data, z, y1) or 0 for z in case["zones"])
        wL0 = sum(_light(rows, z, y0) or 0 for z in case["zones"])
        beta = sum(betas[cls.get(z, "rural")]
                   * (_light(rows, z, y0) or 0)
                   for z in case["zones"]) / wL0
        dl, dp = math.log(L1 / L0), math.log(P1 / P0)
        return {"dl": dl, "dp": dp, "beta": beta,
                "residual": dl - beta * dp}

    main = both(case["metric"])
    alt_name = "share" if case["metric"] == "level" else "level"
    alt = both(alt_name)
    return {
        "metric": case["metric"],
        "lightChangeLog": round(main["dl"], 4),
        "populationChangeLog": round(main["dp"], 4),
        "betaUsed": round(main["beta"], 3),
        "expectedLightChangeLog": round(main["beta"] * main["dp"], 4),
        "lightResidual": round(main["residual"], 4),
        "lightResidualPct": round(math.expm1(main["residual"]) * 100, 1),
        "populationChange": round(math.expm1(main["dp"]) * 100, 1),
        "lightChange": round(math.expm1(main["dl"]) * 100, 1),
        "altMetric": alt_name,
        "altResidual": round(alt["residual"], 4),
        "altResidualPct": round(math.expm1(alt["residual"]) * 100, 1),
        "industrialChange": None,   # внешняя статистика - в проверку
    }


def build() -> tuple[list[dict], list[dict]]:
    night = json.loads((OUT / "nightlights_v2.json").read_text())
    data = json.loads((OUT / "data.json").read_text())["territories"]
    assump = M.load_assumptions()
    decomp = decomposition(night, data, assump)
    cands = []
    for c in CASES:
        m = case_metrics(c, night, data, assump)
        flags = []
        if c["period"][0] <= 2012:
            flags.append("vnl_2012_partial_first_year")
        if c["period"][0] <= 2021 <= c["period"][1]:
            flags.append("vnl_2021_step_in_period")
        # направление подтверждается пересчётом
        ok_dir = (m["lightResidual"] > 0) == \
            (c["direction"] == "light_above_statistics")
        cands.append({
            "id": c["id"],
            "titleRu": c["title_ru"], "titleBe": c["title_be"],
            "status": STATUS,
            "direction": c["direction"],
            "directionConfirmedByRecompute": ok_dir,
            "period": c["period"],
            "zones": c["zones"],
            "zonesNote": c["zones_note"],
            "metrics": m,
            "hypotheses": c["hypotheses"],
            "checkRu": c["check_ru"],
            "qualityFlags": flags,
            "evidenceLevel": ("данные совместимы с гипотезой; причина "
                              "не установлена"),
            "releaseApproved": ok_dir,
        })
    return cands, decomp


def main() -> None:
    cands, decomp = build()
    NL.mkdir(parents=True, exist_ok=True)
    (NL / "research_candidates.json").write_text(json.dumps({
        "note": ("Кандидаты-расхождения: сигналы для дополнительного "
                 "исследования, НЕ причинные выводы. Числа в "
                 "production-рилсе - только при releaseApproved=true "
                 "(гейт: пересчёт на production-данных). Локальная "
                 "диагностика - только VIIRS 2012-2024."),
        "recomputed": "production data, etl.nightlights_divergence",
        "candidates": cands}, ensure_ascii=False, indent=1))
    (NL / "divergence_decomposition.json").write_text(json.dumps({
        "note": ("D = dlogL - beta*dlogP по 119 зонам, 2012-2024; beta - "
                 "межрайонная эластичность класса (assumptions). "
                 "Резидуал - маркер расхождения, не причина."),
        "rows": decomp}, ensure_ascii=False, indent=1))

    ranked = sorted(decomp, key=lambda r: r["residualShare"])
    lines = [
        "# INF-08: кейсы расхождения свет/статистика (пересчёт на "
        "production-данных)", "",
        "Резидуал D = dlogL − β·dlogP (β — межрайонная эластичность "
        "класса). Расхождение — сигнал для проверки, не причинный вывод.",
        "", "## Кандидаты H1–H3", ""]
    for c in cands:
        m = c["metrics"]
        lines += [
            f"### {c['titleRu']} (`{c['id']}`) — {c['status']}",
            f"- направление: {c['direction']} "
            f"(подтверждено пересчётом: {c['directionConfirmedByRecompute']})",
            f"- период {c['period'][0]}–{c['period'][1]}; зоны: "
            f"{', '.join(c['zones'])} ({c['zonesNote']})",
            f"- свет {m['lightChange']:+.1f}%, население "
            f"{m['populationChange']:+.1f}%, ожидание по β={m['betaUsed']}"
            f": {math.expm1(m['expectedLightChangeLog']) * 100:+.1f}%, "
            f"**резидуал {m['lightResidualPct']:+.1f}%**",
            f"- качество: {', '.join(c['qualityFlags']) or 'clean'}",
            f"- проверить: {c['checkRu']}", ""]
    lines += ["## Топ-5 отрицательных резидуалов по долям "
              "(все районы, 2012–2024)", ""]
    for r in ranked[:5]:
        lines.append(f"- {r['id']}: D_share={r['residualShare']:+.3f} "
                     f"(свет {math.expm1(r['observedLightChange'])*100:+.0f}%, "
                     f"население {math.expm1(r['populationChange'])*100:+.0f}%)")
    lines += ["", "## Топ-5 положительных резидуалов", ""]
    for r in ranked[-5:][::-1]:
        lines.append(f"- {r['id']}: D_share={r['residualShare']:+.3f} "
                     f"(свет {math.expm1(r['observedLightChange'])*100:+.0f}%, "
                     f"население {math.expm1(r['populationChange'])*100:+.0f}%)")
    dst = ROOT / "docs" / "notes" / "nightlights_divergence_cases.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK: {len(cands)} кандидатов, {len(decomp)} зон декомпозиции")
    for c in cands:
        print(f"  {c['id']}: резидуал {c['metrics']['lightResidualPct']:+.1f}% "
              f"({c['direction']}, подтверждено={c['directionConfirmedByRecompute']})")


if __name__ == "__main__":
    main()
