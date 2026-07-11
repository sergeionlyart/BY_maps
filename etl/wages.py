"""INF-03 `wages`: зарплата x динамика населения.

Вопрос: следует ли население за деньгами - какова эластичность
десятилетней динамики населения района по зарплатному дифференциалу
к Минску; где аномалии (моногорода, пригороды)?

Данные: номинальная среднемесячная зарплата по районам и городам
областного подчинения, 2010-2025 (дата-портал Белстата, индикатор
10218000003; сырые ответы завендорены в data/raw/wages/). Дифференциал -
отношение зарплаты района к зарплате г. Минска того же года: относительная
величина самонормируется, деноминация-2016 и дефлятор не нужны (старые
рубли 2010-2015 делятся на 10 000 только для абсолютных рядов).

Периметр зарплатных районов = переписной: без городов областного
подчинения (Орша/Полоцк внутри районов, Новополоцк отдельно) - для
сопоставления население района берётся как data.json минус город-хост
(карта HOSTED, копия из etl.forecast.sub - синхронизация тестируется).

Методика (спека INF-03):
- биваритная классификация 3x3: терцили среднего дифференциала за окно
  x терцили десятилетней динамики населения (2015-2025);
- срезовая регрессия OLS: popChange10 ~ ln(mean wage_rel) + ln(pop центра);
  устойчивость: без контроля, окно 2009-2019 (перепись-к-переписи),
  без пригородов Минска, WLS;
- выбросы: топ |остатка| регрессии (моногорода, агрогородки, пригороды).

Запуск: python -m etl.wages -> web/public/data/wages.json
                               data/curated/wages.csv
"""
from __future__ import annotations

import csv
import json
import math

from .common import ROOT, OUT
from .census_age import RAION_RU2ID, _e

# Периметры: районы-хосты в data.json включают города обл. подчинения,
# зарплатная статистика - нет. Локальная копия карты из etl.forecast.sub
# (пакет wages не тянет модули прогноза); синхронизация закреплена тестом.
HOSTED = {
    "r-babrujski": "c-babrujsk", "r-baranavicki": "c-baranavichy",
    "r-brescki": "c-brest", "r-homielski": "c-homiel",
    "r-hrodzienski": "c-hrodna", "r-mahilouski": "c-mahilou",
    "r-pinski": "c-pinsk", "r-polacki": "c-navapolack",
    "r-smalavicki": "c-zhodzina", "r-viciebski": "c-viciebsk",
}

RAW = ROOT / "data" / "raw" / "wages"
CURATED = ROOT / "data" / "curated"
VERSION = "1.0.0"

WINDOW = (2015, 2025)        # десятилетнее окно динамики
WAGE_YEARS = range(2015, 2025)  # окно среднего дифференциала (полные годы)
ALT_WINDOW = (2009, 2019)   # окно устойчивости: перепись-к-переписи
ALT_WAGE_YEARS = range(2010, 2020)  # зарплаты доступны с 2010
DENOM_CUT = 2016             # до этого года - старые рубли (/10 000)

CITY_RU2ID = {
    "г. Брест": "c-brest", "г. Барановичи": "c-baranavichy",
    "г. Пинск": "c-pinsk", "г. Витебск": "c-viciebsk",
    "г. Новополоцк": "c-navapolack", "г. Гомель": "c-homiel",
    "г. Гродно": "c-hrodna", "г. Жодино": "c-zhodzina",
    "г. Могилев": "c-mahilou", "г. Бобруйск": "c-babrujsk",
}
OBL_RU2ID = {
    "Брестская область": "BY-BR", "Витебская область": "BY-VI",
    "Гомельская область": "BY-HO", "Гродненская область": "BY-HR",
    "Минская область": "BY-MI", "Могилевская область": "BY-MA",
    "г. Минск": "BY-HM", "Республика Беларусь": "BY",
}
# пригороды Минска для варианта устойчивости (агломерационный эффект)
MINSK_SUBURBS = {"r-minski", "r-dziarzhynski", "r-smalavicki", "r-lahojski"}


def _num(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load_wages() -> dict[str, dict[int, float]]:
    """{terr_id: {год: зарплата, BYN деноминированные}}."""
    out: dict[str, dict[int, float]] = {}
    skipped: set[str] = set()
    for fn in ("wage_10218000003_2010-2019.json",
               "wage_10218000003_2020-2026.json"):
        d = json.loads((RAW / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            name, level = row[0]["value"], row[0]["level"]
            tid = None
            if name in OBL_RU2ID:
                tid = OBL_RU2ID[name]
            elif name in CITY_RU2ID:
                tid = CITY_RU2ID[name]
            elif level == 2:
                tid = RAION_RU2ID.get(_e(name))
            if tid is None:
                skipped.add(name)
                continue
            for i, y in enumerate(years):
                v = _num(row[i + 1]["value"] if i + 1 < len(row) else None)
                if v is None:
                    continue
                if y < DENOM_CUT:
                    v /= 10_000.0  # деноминация-2016
                out.setdefault(tid, {})[y] = v
    # «Не распределено по районам Минской области» и т.п. - вне анализа
    expected_skips = {"Не распределено по районам Минской области"}
    unexpected = skipped - expected_skips
    assert not unexpected, f"несматченные территории: {sorted(unexpected)}"
    return out


def raion_pop(data: dict, t: str, year: int) -> float | None:
    """Население района в зарплатном периметре (минус город-хост)."""
    def val(tid: str) -> float | None:
        p = data[tid]["pop"].get(str(year))
        return float(p[0]) if p else None

    v = val(t)
    if v is None:
        return None
    if t in HOSTED:
        h = val(HOSTED[t])
        if h is None:
            return None
        v -= h
    return v


def ols(y: list[float], xs: list[list[float]],
        w: list[float] | None = None) -> dict:
    """OLS/WLS с константой (нормальные уравнения, чистый Python).

    xs - список регрессоров (каждый - список длины n).
    Возвращает {'beta': [b0, b1, ...], 'se': [...], 'r2': float, 'n': int}."""
    n = len(y)
    k = len(xs) + 1
    W = w if w is not None else [1.0] * n
    X = [[1.0] + [x[i] for x in xs] for i in range(n)]
    # X'WX и X'Wy
    xtx = [[sum(W[i] * X[i][a] * X[i][b] for i in range(n)) for b in range(k)]
           for a in range(k)]
    xty = [sum(W[i] * X[i][a] * y[i] for i in range(n)) for a in range(k)]
    # решение через исключение Гаусса
    m = [row[:] + [xty[a]] for a, row in enumerate(xtx)]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        d = m[col][col]
        m[col] = [v / d for v in m[col]]
        for r in range(k):
            if r != col and m[r][col]:
                f = m[r][col]
                m[r] = [v - f * u for v, u in zip(m[r], m[col])]
    beta = [m[a][k] for a in range(k)]
    yhat = [sum(b * X[i][j] for j, b in enumerate(beta)) for i in range(n)]
    resid = [y[i] - yhat[i] for i in range(n)]
    ybar = sum(W[i] * y[i] for i in range(n)) / sum(W)
    ss_res = sum(W[i] * resid[i] ** 2 for i in range(n))
    ss_tot = sum(W[i] * (y[i] - ybar) ** 2 for i in range(n))
    sigma2 = ss_res / (n - k)
    # обратная (X'WX): повторное исключение
    inv = [[1.0 if a == b else 0.0 for b in range(k)] for a in range(k)]
    m2 = [row[:] for row in xtx]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(m2[r][col]))
        m2[col], m2[piv] = m2[piv], m2[col]
        inv[col], inv[piv] = inv[piv], inv[col]
        d = m2[col][col]
        m2[col] = [v / d for v in m2[col]]
        inv[col] = [v / d for v in inv[col]]
        for r in range(k):
            if r != col and m2[r][col]:
                f = m2[r][col]
                m2[r] = [v - f * u for v, u in zip(m2[r], m2[col])]
                inv[r] = [v - f * u for v, u in zip(inv[r], inv[col])]
    se = [math.sqrt(sigma2 * inv[a][a]) for a in range(k)]
    # робастные к гетероскедастичности SE (HC1): (X'WX)^-1 X'W e^2 WX (X'WX)^-1
    meat = [[sum(W[i] ** 2 * resid[i] ** 2 * X[i][a] * X[i][b]
                 for i in range(n)) for b in range(k)] for a in range(k)]
    hc = [[sum(inv[a][c] * meat[c][d] * inv[d][b]
               for c in range(k) for d in range(k))
           for b in range(k)] for a in range(k)]
    corr = n / (n - k)
    se_hc1 = [math.sqrt(corr * hc[a][a]) for a in range(k)]
    return {"beta": beta, "se": se, "se_hc1": se_hc1,
            "r2": 1 - ss_res / ss_tot, "n": n, "resid": resid}


def build() -> dict:
    wages = load_wages()
    data = json.loads((OUT / "data.json").read_text())["territories"]
    raions = sorted(t for t in wages if t.startswith("r-"))
    assert len(raions) == 118, len(raions)

    y0, y1 = WINDOW
    minsk = wages["BY-HM"]

    rows = []
    for t in raions:
        w = wages[t]
        rel = [w[y] / minsk[y] for y in WAGE_YEARS if y in w and y in minsk]
        p0, p1 = raion_pop(data, t, y0), raion_pop(data, t, y1)
        if not rel or p0 is None or p1 is None:
            continue
        center = data[t].get("center") or []
        cpop = sum(float(data[c]["pop"].get(str(y0), [0])[0]) for c in center
                   if str(y0) in data[c]["pop"])
        rows.append({
            "id": t,
            "wage_rel": sum(rel) / len(rel),
            "pop_change": p1 / p0 - 1,
            "center_pop": max(cpop, 1.0),
            "wage_2025": w.get(2025),
        })
    assert len(rows) == 118, len(rows)

    # терцили -> классы 3x3 (w0..w2 x p0..p2)
    def terciles(vals: list[float]) -> tuple[float, float]:
        s = sorted(vals)
        return s[len(s) // 3], s[2 * len(s) // 3]

    wt = terciles([r["wage_rel"] for r in rows])
    pt = terciles([r["pop_change"] for r in rows])
    for r in rows:
        wi = 0 if r["wage_rel"] < wt[0] else 1 if r["wage_rel"] < wt[1] else 2
        pi = 0 if r["pop_change"] < pt[0] else 1 if r["pop_change"] < pt[1] else 2
        r["cls"] = f"w{wi}p{pi}"

    # регрессии: основная + варианты устойчивости
    def run_reg(rs: list[dict], weights: bool = False) -> dict:
        y = [r["pop_change"] * 100 for r in rs]              # п.п. за десятилетие
        x1 = [math.log(r["wage_rel"]) for r in rs]
        x2 = [math.log(r["center_pop"]) for r in rs]
        w = [r["center_pop"] for r in rs] if weights else None
        res = ols(y, [x1, x2], w)
        return res

    main = run_reg(rows)
    for r, resid in zip(rows, main["resid"]):
        r["resid"] = resid

    variants = {
        "main": main,
        "no_control": ols([r["pop_change"] * 100 for r in rows],
                          [[math.log(r["wage_rel"]) for r in rows]]),
        "no_suburbs": run_reg([r for r in rows if r["id"] not in MINSK_SUBURBS]),
        "weighted": run_reg(rows, weights=True),
    }

    # окно устойчивости: динамика по переписям 2009-2019,
    # дифференциал 2010-2019 (зарплаты доступны с 2010)
    a0, a1 = ALT_WINDOW
    alt_rows = []
    for t in raions:
        w = wages[t]
        rel = [w[y] / minsk[y] for y in ALT_WAGE_YEARS if y in w and y in minsk]
        p0, p1 = raion_pop(data, t, a0), raion_pop(data, t, a1)
        if not rel or p0 is None or p1 is None:
            continue
        r0 = next(r for r in rows if r["id"] == t)
        alt_rows.append({"pop_change": p1 / p0 - 1,
                         "wage_rel": sum(rel) / len(rel),
                         "center_pop": r0["center_pop"]})
    variants["window_2009_2019"] = run_reg(alt_rows)

    # выбросы: топ-8 |остатка|
    outliers = sorted(rows, key=lambda r: -abs(r["resid"]))[:8]

    grp = {}
    for fn in ("grp_pc_10202100055_2010-2019.json",
               "grp_pc_10202100055_2020-2026.json"):
        d = json.loads((RAW / fn).read_text())
        years = [int(y) for y in d["tableHeader"][0]]
        for row in d["tableRows"]:
            tid = OBL_RU2ID.get(row[0]["value"])
            if not tid:
                continue
            for i, y in enumerate(years):
                v = _num(row[i + 1]["value"] if i + 1 < len(row) else None)
                if v is not None and y >= DENOM_CUT:
                    grp.setdefault(tid, {})[y] = v
    return {
        "rows": rows, "terciles": {"wage": wt, "pop": pt},
        "variants": variants, "outliers": [r["id"] for r in outliers],
        "wages": wages, "grp_pc": grp,
    }


def main() -> None:
    b = build()
    rows, variants = b["rows"], b["variants"]

    terrs = {}
    for r in rows:
        terrs[r["id"]] = {
            "wageRel": round(r["wage_rel"], 4),
            "popChange": round(r["pop_change"] * 100, 2),
            "cls": r["cls"],
            "resid": round(r["resid"], 2),
            "wage2025": r["wage_2025"],
        }

    def reg_out(v: dict) -> dict:
        return {"beta": [round(x, 3) for x in v["beta"]],
                "se": [round(x, 3) for x in v["se"]],
                "seHc1": [round(x, 3) for x in v["se_hc1"]],
                "r2": round(v["r2"], 3), "n": v["n"]}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wages.json").write_text(json.dumps({
        "version": VERSION,
        "window": list(WINDOW),
        "wageYears": [WAGE_YEARS.start, WAGE_YEARS.stop - 1],
        "terciles": {k: [round(x, 4) for x in v] for k, v in b["terciles"].items()},
        "territories": terrs,
        "regressions": {k: reg_out(v) for k, v in variants.items()},
        "outliers": b["outliers"],
        "minskWage": {y: b["wages"]["BY-HM"][y] for y in sorted(b["wages"]["BY-HM"])},
        "grpPc": b["grp_pc"],
    }, ensure_ascii=False))

    with open(CURATED / "wages.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["territory_id", "year", "wage_byn"])
        for t, ys in sorted(b["wages"].items()):
            for y, v in sorted(ys.items()):
                w.writerow([t, y, v])

    m = variants["main"]
    print(f"OK: wages.json ({len(rows)} районов)")
    print(f"  регрессия: ΔP(10 лет, п.п.) ~ ln(wage_rel): "
          f"beta={m['beta'][1]:.2f} (SE {m['se'][1]:.2f}, HC1 {m['se_hc1'][1]:.2f}), "
          f"контроль ln(центр): {m['beta'][2]:.2f}, R²={m['r2']:.3f}")
    for k in ("no_control", "no_suburbs", "weighted", "window_2009_2019"):
        v = variants[k]
        print(f"  {k:18s}: beta={v['beta'][1]:6.2f} (SE {v['se'][1]:.2f}) "
              f"R²={v['r2']:.3f} n={v['n']}")


if __name__ == "__main__":
    main()
