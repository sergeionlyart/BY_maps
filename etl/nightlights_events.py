"""INF-08 v3: обнаружение событий и адаптивная скорость (stdlib).

События считаются ТОЛЬКО по аналитическому слою (гармонизированные
зональные доли nightlights_v2.json) - не по визуальной разнице кадров.

Для каждой сопоставимой пары лет (внутри сегмента):
  d_z    = ln(share_y / share_prev)          - нац. тренд исключён
           (доли), общенациональное движение оценивается отдельно;
  sigma_z = медиана |d_z| по сегменту зоны   - обычная волатильность
           района (min 0.02);
  z      = d_z / sigma_z; вес важности w = share/(share+s0) гасит
           крохотные шумные зоны; score = |z| * w.
Персистентность: одиночный выброс (знак меняется в следующем году при
сопоставимой силе) не считается событием. Методологические переходы
(2011->2012 смена источника, 2021 смена обработки VNL, 2024->2030
граница наблюдение/модель) исключены из обычного скоринга и оформлены
отдельными типами. Соседние районы с одним направлением объединяются в
кластер (смежность по границам adm2).

Причины событий НЕ генерируются: карточка сообщает только наблюдаемое
изменение; ручные объяснения с источниками - nightlights_annotations.json.

Скорость воспроизведения (мс на кадр) выводится из силы события:
  тихо 380-450 / умеренно 650 / событие 1000 / крупное 1350;
  методологический переход - остановка 1500 с пояснением.

Запуск: python -m etl.nightlights_events
  -> web/public/data/nightlights/nightlights_events.json
  -> web/public/data/nightlights/nightlights_annotations.json
"""
from __future__ import annotations

import json
import math
import statistics

from .common import ROOT, OUT
from . import nightlights_model as M

NL = OUT / "nightlights"

SIGMA_MIN = 0.02
S0 = 0.002                 # полувес важности доли
Z_REGION = {"reconstruction": 6.0, "observed": 4.0, "model": 4.0}
Z_NATIONAL = 2.5
MAX_SECONDARY = 2

DUR_QUIET_RECON = 380
DUR_QUIET_OBS = 450
DUR_MODERATE = 650
DUR_EVENT = 1000
DUR_MAJOR = 1350
DUR_BOUNDARY = 1500
PAUSE_AFTER_MAJOR = 450


def _adjacency() -> dict[str, set[str]]:
    """Смежность районов по общим границам (adm2 + Минск).

    Предпочитается вендоренный data/raw/nightlights/adjacency.json
    (пакет воспроизводится stdlib-only); при его отсутствии — пересчёт
    shapely (детерминирован, тем же результатом)."""
    vend = ROOT / "data" / "raw" / "nightlights" / "adjacency.json"
    if vend.exists():
        return {k: set(v)
                for k, v in json.loads(vend.read_text()).items()}
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    g2 = json.loads((OUT / "geo" / "adm2.geojson").read_text())
    g1 = json.loads((OUT / "geo" / "adm1.geojson").read_text())
    feats = [(f["properties"]["id"], shape(f["geometry"]))
             for f in g2["features"]
             if f["properties"]["id"].startswith("r-")]
    feats += [(f["properties"]["id"], shape(f["geometry"]))
              for f in g1["features"] if f["properties"]["id"] == "BY-HM"]
    ids = [i for i, _ in feats]
    geoms = [g for _, g in feats]
    tree = STRtree(geoms)
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for i, g in enumerate(geoms):
        for j in tree.query(g):
            j = int(j)
            if j != i and geoms[i].intersects(geoms[j]):
                adj[ids[i]].add(ids[j])
    return adj


def _segment(year: int) -> str:
    if year <= 2011:
        return "reconstruction"
    if year <= 2024:
        return "observed"
    return "model"


def _pairs(night: dict) -> list[dict]:
    """Сопоставимые пары лет таймлайна (наблюдения + узлы модели)."""
    out = []
    for y in range(1993, 2012):
        out.append({"year": y, "ref": y - 1, "seg": "reconstruction",
                    "span": 1})
    for y in range(2013, 2025):
        out.append({"year": y, "ref": y - 1, "seg": "observed", "span": 1})
    nodes = night["nodes"]
    for i in range(1, len(nodes)):
        out.append({"year": nodes[i], "ref": nodes[i - 1], "seg": "model",
                    "span": nodes[i] - nodes[i - 1]})
    return out


def _shares(night: dict, scn="base", jmp="official"):
    """share[zone][year] и natLight[year] для наблюдений + модель."""
    shares: dict[str, dict[int, float]] = {}
    nat: dict[int, float] = {}
    for k, v in night["natLight"].items():
        nat[int(k)] = v
    for k, v in night["natModel"][jmp][scn].items():
        nat[int(k)] = v
    for r in night["rows"]:
        z = r["id"]
        shares[z] = {}
        for k, s in r["lshare"].items():
            shares[z][int(k)] = s
        for k, m in r["model"][jmp][scn].items():
            shares[z][int(k)] = m["ls"]
    return shares, nat


def build(night: dict) -> dict:
    shares, nat = _shares(night)
    zones = sorted(shares)
    adj = _adjacency()
    pairs = _pairs(night)

    # волатильность зоны по сегментам
    seg_years = {
        "reconstruction": [(y, y - 1) for y in range(1993, 2012)],
        "observed": [(y, y - 1) for y in range(2013, 2025)],
    }
    nodes = night["nodes"]
    seg_years["model"] = [(nodes[i], nodes[i - 1])
                          for i in range(1, len(nodes))]
    sigma: dict[str, dict[str, float]] = {}
    dvals: dict[tuple, dict[str, float]] = {}
    for seg, ys in seg_years.items():
        sigma[seg] = {}
        for z in zones:
            ds = []
            for y, ref in ys:
                a, b = shares[z].get(y), shares[z].get(ref)
                if a and b:
                    d = math.log(a / b)
                    dvals[(z, y)] = d
                    ds.append(abs(d))
            sigma[seg][z] = max(statistics.median(ds) if ds else 1.0,
                                SIGMA_MIN)

    nat_d = {}
    for p in pairs:
        y, ref = p["year"], p["ref"]
        if nat.get(y) and nat.get(ref):
            nat_d[y] = math.log(nat[y] / nat[ref]) / p["span"]
    nat_sigma = {}
    for seg, ys in seg_years.items():
        vals = [abs(nat_d[y]) for y, _ in ys if y in nat_d]
        nat_sigma[seg] = max(statistics.median(vals) if vals else 1.0,
                             0.01)

    events = []

    # методологические границы - отдельные типы, вне скоринга
    events.append({
        "year": 2012, "kind": "source_transition",
        "durationMs": DUR_BOUNDARY, "quality": "methodological_boundary",
        "annotationKey": "source-transition-2012", "regions": []})
    events.append({
        "year": 2021, "kind": "quality_note",
        "durationMs": DUR_MODERATE, "quality": "vnl_processing_step",
        "annotationKey": "vnl-2021", "regions": []})
    events.append({
        "year": nodes[0], "kind": "forecast_boundary",
        "durationMs": DUR_BOUNDARY, "quality": "methodological_boundary",
        "annotationKey": "forecast-boundary", "regions": []})

    excluded = {2012, 2021, nodes[0]}
    for p in pairs:
        y, ref, seg = p["year"], p["ref"], p["seg"]
        if y in excluded:
            continue
        cand = []
        for z in zones:
            d = dvals.get((z, y))
            if d is None:
                continue
            zscore = (d / p["span"]) / sigma[seg][z]
            share = shares[z].get(y, 0.0)
            w = share / (share + S0)
            score = abs(zscore) * w
            if score < Z_REGION[seg]:
                continue
            # персистентность (наблюдения): одиночный выброс со сменой
            # знака в следующем году отбрасывается
            if seg == "observed" and y < 2024:
                dn = dvals.get((z, y + 1))
                if dn is not None and dn * d < 0 \
                        and abs(dn) > 0.5 * abs(d):
                    continue
            cand.append({"id": z, "d": d, "score": score})
        if not cand:
            continue
        # кластеризация соседей с одним направлением
        cand.sort(key=lambda c: -c["score"])
        used: set[str] = set()
        clusters = []
        by_id = {c["id"]: c for c in cand}
        for c in cand:
            if c["id"] in used:
                continue
            cl = [c]
            used.add(c["id"])
            stack = [c["id"]]
            while stack:
                cur = stack.pop()
                for nb in adj.get(cur, ()):
                    if nb in by_id and nb not in used \
                            and by_id[nb]["d"] * c["d"] > 0:
                        used.add(nb)
                        cl.append(by_id[nb])
                        stack.append(nb)
            clusters.append(cl)
        clusters.sort(key=lambda cl: -max(c["score"] for c in cl))
        top = clusters[0]
        top_score = max(c["score"] for c in top)
        regions = []
        for c in sorted(top, key=lambda c: -c["score"])[:1 + MAX_SECONDARY]:
            share_now = shares[c["id"]].get(y, 0.0)
            share_ref = shares[c["id"]].get(ref, 0.0)
            regions.append({
                "id": c["id"],
                "direction": "rise" if c["d"] > 0 else "fall",
                "annualizedChange":
                    round(math.expm1(c["d"] / p["span"]), 4),
                "nationalShareDelta": round(share_now - share_ref, 5),
                "confidence": ("reconstruction" if seg == "reconstruction"
                               else "model" if seg == "model" else "high"),
                "annotationKey": ("astravets-npp"
                                  if c["id"] == "r-astraviecki"
                                  and seg == "observed" else None)})
        # вторичный кластер (не более одного дополнительного акцента)
        if len(clusters) > 1 and len(regions) < 1 + MAX_SECONDARY:
            c2 = max(clusters[1], key=lambda c: c["score"])
            share_now = shares[c2["id"]].get(y, 0.0)
            share_ref = shares[c2["id"]].get(ref, 0.0)
            regions.append({
                "id": c2["id"],
                "direction": "rise" if c2["d"] > 0 else "fall",
                "annualizedChange":
                    round(math.expm1(c2["d"] / p["span"]), 4),
                "nationalShareDelta": round(share_now - share_ref, 5),
                "confidence": ("reconstruction" if seg == "reconstruction"
                               else "model" if seg == "model" else "high"),
                "annotationKey": None})
        dur = DUR_MAJOR if top_score >= 2 * Z_REGION[seg] else DUR_EVENT
        events.append({
            "year": y, "kind": "regional_change",
            "score": round(top_score, 2), "durationMs": dur,
            "pauseAfterMs": PAUSE_AFTER_MAJOR if dur == DUR_MAJOR else 0,
            "quality": ("reconstruction" if seg == "reconstruction"
                        else "model" if seg == "model" else "clean"),
            "scenarioScope": "base_official" if seg == "model" else None,
            "regions": regions})

    # общенациональные события (отдельно от локальных)
    for p in pairs:
        y, seg = p["year"], p["seg"]
        if y in excluded or y not in nat_d:
            continue
        zn = nat_d[y] / nat_sigma[seg]
        if abs(zn) >= Z_NATIONAL:
            events.append({
                "year": y, "kind": "national_change",
                "score": round(abs(zn), 2), "durationMs": DUR_EVENT,
                "quality": ("reconstruction" if seg == "reconstruction"
                            else "model" if seg == "model" else "clean"),
                "direction": "rise" if nat_d[y] > 0 else "fall",
                "annualizedChange": round(math.expm1(nat_d[y]), 4),
                "regions": []})

    # длительности «тихих» лет
    ev_years = {e["year"] for e in events}
    stops = list(range(1992, 2025)) + nodes
    durations = {}
    for y in stops:
        if y in ev_years:
            durations[str(y)] = max(e["durationMs"] for e in events
                                    if e["year"] == y)
        else:
            seg = _segment(y)
            durations[str(y)] = (DUR_QUIET_RECON
                                 if seg == "reconstruction"
                                 else DUR_QUIET_OBS)
    return {"events": sorted(events, key=lambda e: e["year"]),
            "durationsMs": durations,
            "params": {"sigmaMin": SIGMA_MIN, "shareHalfWeight": S0,
                       "zRegion": Z_REGION, "zNational": Z_NATIONAL,
                       "note": ("скоринг по аналитическим долям "
                                "(нац. тренд исключён); переходы "
                                "источников и аномалии продукта вне "
                                "обычного скоринга")}}


ANNOTATIONS = {
    "astravets-npp": {
        "ru": ("Возможное объяснение: строительство и ввод Белорусской "
               "АЭС (энергоблок 1 — ноябрь 2020, энергоблок 2 — 2023)."),
        "be": ("Магчымае тлумачэнне: будаўніцтва і ўвод Беларускай АЭС "
               "(энергаблок 1 — лістапад 2020, энергаблок 2 — 2023)."),
        "source": "https://ru.wikipedia.org/wiki/Белорусская_АЭС",
        "sourceTitle": "Белорусская АЭС — Википедия"},
    "source-transition-2012": {
        "ru": ("Смена происхождения данных: реконструкция VIIRS-like "
               "(по DMSP) заканчивается, начинаются реальные наблюдения "
               "VIIRS. Изменение картинки на этом стыке — свойство "
               "данных, а не событие на земле."),
        "be": ("Змена паходжання даных: рэканструкцыя VIIRS-like (па "
               "DMSP) заканчваецца, пачынаюцца рэальныя назіранні "
               "VIIRS. Змена карцінкі на гэтым стыку — уласцівасць "
               "даных, а не падзея на зямлі."),
        "source": "/methodology", "sourceTitle": "Методология проекта"},
    "vnl-2021": {
        "ru": ("Смена обработки продукта VNL в 2021 году даёт скачок "
               "уровня — это артефакт данных; доли районов устойчивее, "
               "но год исключён из автоматического поиска событий."),
        "be": ("Змена апрацоўкі прадукту VNL у 2021 годзе дае скачок "
               "узроўню — гэта артэфакт даных; долі раёнаў "
               "устойлівейшыя, але год выключаны з аўтаматычнага "
               "пошуку падзей."),
        "source": "/methodology", "sourceTitle": "Методология проекта"},
    "forecast-boundary": {
        "ru": ("Дальше — модельная визуализация на основе "
               "демографического сценария и пространственной структуры "
               "освещения базового года. Это не спутниковый снимок "
               "будущего."),
        "be": ("Далей — мадэльная візуалізацыя на аснове дэмаграфічнага "
               "сцэнарыя і прасторавай структуры асвятлення базавага "
               "года. Гэта не спадарожнікавы здымак будучыні."),
        "source": "/methodology", "sourceTitle": "Методология проекта"},
}


def main() -> None:
    night = json.loads((OUT / "nightlights_v2.json").read_text())
    ev = build(night)
    NL.mkdir(parents=True, exist_ok=True)
    (NL / "nightlights_events.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=1))
    (NL / "nightlights_annotations.json").write_text(
        json.dumps(ANNOTATIONS, ensure_ascii=False, indent=1))
    kinds = {}
    for e in ev["events"]:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"OK: {len(ev['events'])} событий: {kinds}")
    for e in ev["events"]:
        if e["kind"] == "regional_change":
            r0 = e["regions"][0]
            print(f"  {e['year']}: {r0['id']} {r0['direction']} "
                  f"score={e['score']} q={e['quality']}")


if __name__ == "__main__":
    main()
