"""ML-challenger (этап 8, ROADMAP §2): диагностика систематических ошибок
структурной модели районов, НЕ конкурирующий прогноз и НЕ 50-летний
прогнозист.

Мишень — ЗНАКОВАЯ ошибка инкумбента CCR/Гамильтона-Перри на его ЕДИНСТВЕННОМ
подлинно out-of-sample окне (база 2019 -> факт 2026, перепись-периметр A,
нормировка к фактическим областным итогам, БЕЗ калибровки старта):
    e_i = ln(факт_2026_i / CCR_2026_i)
Поскольку CCR нормирован к истинному областному итогу, e_i — это
ВНУТРИОБЛАСТНАЯ ошибка распределения: «какие районы и под действием каких
сигналов, которые CCR структурно не видит, модель систематически
недо-/пере-оценивает».

Мы регрессируем e_i градиентным бустингом (чистый stdlib, сеяный) на
признаках, которые CCR игнорирует (зарплаты, транспортная доступность,
доступ к границе ЕС, ночная светимость, миграционное сальдо) + структурные
контроли (возрастные доли, чернобыльский класс, host-флаг). ВСЕ признаки
датированы <= 2019 (никакой утечки из окна 2019->2026).

Честность встроена, а не задекларирована:
  - LOO-по-областям кросс-валидация (6 фолдов; Минск — не район);
  - ПЕРЕСТАНОВОЧНЫЙ НУЛЬ: тасуем e_i N раз, тот же CV -> нулевое
    распределение OOF R2 и важностей; каждое заявление гейтится p<0.05;
    если реальный OOF R2 внутри нуль-полосы — заголовок «CCR не оставляет
    ковариат-детектируемой систематической ошибки» (положительная
    валидация CCR);
  - повторная CV -> полоса 5/95 (не единичная удача);
  - гонка MAPE (CCR vs CCR+коррекция vs наивная) ПОНИЖЕНА под диагностику.

Запуск: python -m etl.challenger -> web/public/data/mlchallenger.json
"""
from __future__ import annotations

import csv
import json
import math
import random

from .common import ROOT, OUT
from .forecast import sub
from .forecast.backtest_sub import backtest_raions

SEED = 20260712
CURATED = ROOT / "data" / "curated"

# --- сетка гиперпараметров (жёсткая регуляризация под n=118) ---
GB = dict(n_estimators=300, learning_rate=0.05, max_depth=2, min_leaf=10,
          subsample=0.7, feat_sub=5, seed=SEED)
N_PERM = 200          # перестановочный нуль
N_REPEAT = 30         # повторная CV (варьируем сид субвыборки)
PATIENCE = 25         # ранняя остановка по OOF

EXO = ["wage_rel19", "wage_gr1519", "access_eff", "access_eu2019",
       "nl_pc19", "nl_trend1519", "mig_rate1519"]
CTRL = ["share014_19", "share65_19", "lnpop19", "cher_class", "host_flag"]
FEATURES = EXO + CTRL


# ====================================================================
# признаки
# ====================================================================
def _wages() -> dict:
    w: dict[str, dict[int, float]] = {}
    for r in csv.DictReader(open(CURATED / "wages.csv")):
        w.setdefault(r["territory_id"], {})[int(r["year"])] = float(r["wage_byn"])
    return w


def _age_shares(year: int) -> dict:
    """Из age{year}.csv (периметр A): доли 0-14 / 65+ и итог района."""
    young = {"0-4", "5-9", "10-14"}
    old = {"65-69", "70-74", "75-79", "80+"}
    agg: dict[str, dict] = {}
    for r in csv.DictReader(open(CURATED / f"age{year}.csv")):
        t = r["territory_id"]
        if not t.startswith("r-"):
            continue
        g, p = r["age_group"], float(r["pop"])
        a = agg.setdefault(t, {"tot": 0.0, "y": 0.0, "o": 0.0})
        a["tot"] += p
        if g in young:
            a["y"] += p
        elif g in old:
            a["o"] += p
    return agg


def _nightlights() -> tuple[dict, dict]:
    d = json.load(open(OUT / "nightlights.json"))
    rows = {r["id"]: r for r in d["rows"]}
    natlight = {int(y): v for y, v in d["natLight"].items()}
    return rows, natlight


def _slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    return num / den if den else 0.0


def build_panel() -> dict:
    """Собрать (ids, oblast, X, y=e_ccr, уровни CCR/наив/факт, host)."""
    bt = backtest_raions()
    rows = {r["territory_id"]: r for r in bt["rows"] if r["territory_id"].startswith("r-")}
    obl = sub.oblast_of()
    chern = sub._chernobyl_classes()
    hosted = set(sub.HOSTED) | set(sub.MERGED_2009.values())

    wages = _wages()
    sh19 = _age_shares(2019)
    nl_rows, natlight = _nightlights()
    mig = json.load(open(OUT / "migration.json"))["raions"]
    acc = json.load(open(OUT / "access.json"))["territories"]

    wage_by = wages["BY"]
    ids = sorted(rows)
    X, y = [], []
    ccr, naive, fact, host = {}, {}, {}, {}
    feat_rows = {}
    for t in ids:
        r = rows[t]
        fact[t] = r["fact_2026"]
        ccr[t] = r["model_2026"]
        naive[t] = r["naive_2026"]
        host[t] = 1 if t in hosted else 0
        y.append(math.log(fact[t] / ccr[t]))

        # зарплаты
        wv = wages.get(t, {})
        wage_rel19 = math.log(wv.get(2019, wage_by[2019]) / wage_by[2019])
        w15, w19 = wv.get(2015), wv.get(2019)
        wage_gr = math.log(w19 / w15) if (w15 and w19) else 0.0
        # доступность
        a = acc[t]
        access_eff = a["eff"]
        access_eu = a.get("eu2019", 0.0)
        # ночная светимость: лог душевой яркости 2019 + тренд ДОЛИ 2015-2019
        nl = nl_rows.get(t, {})
        light = nl.get("light", {})
        pop = nl.get("pop", {})
        l19 = light.get("2019")
        p19nl = pop.get("2019")
        nl_pc = math.log(l19 / p19nl) if (l19 and p19nl) else 0.0
        yrs = [2015, 2016, 2017, 2018, 2019]
        shares = [(yr, light.get(str(yr))) for yr in yrs]
        shares = [(yr, math.log(v / natlight[yr])) for yr, v in shares if v and natlight.get(yr)]
        nl_trend = _slope([s[0] for s in shares], [s[1] for s in shares]) if len(shares) >= 3 else 0.0
        # миграция
        mig_rate = mig.get(t, {}).get("rate1519", 0.0)
        # структура
        a19 = sh19[t]
        share014 = a19["y"] / a19["tot"]
        share65 = a19["o"] / a19["tot"]
        lnpop = math.log(a19["tot"])

        row = {
            "wage_rel19": wage_rel19, "wage_gr1519": wage_gr,
            "access_eff": access_eff, "access_eu2019": access_eu,
            "nl_pc19": nl_pc, "nl_trend1519": nl_trend,
            "mig_rate1519": mig_rate,
            "share014_19": share014, "share65_19": share65,
            "lnpop19": lnpop, "cher_class": (2 if t in chern else 0),
            "host_flag": host[t],
        }
        feat_rows[t] = row
        X.append([row[f] for f in FEATURES])
    return {"ids": ids, "oblast": {t: obl[t] for t in ids}, "X": X, "y": y,
            "ccr": ccr, "naive": naive, "fact": fact, "host": host,
            "feat_rows": feat_rows}


# ====================================================================
# градиентный бустинг (stdlib, сеяный) — регрессия, L2
# ====================================================================
class _Node:
    __slots__ = ("feat", "thr", "left", "right", "value")

    def __init__(self):
        self.feat = self.thr = self.left = self.right = self.value = None


def _fit_tree(X, y, idx, depth, max_depth, min_leaf, feats_pool, rng, imp):
    node = _Node()
    node.value = sum(y[i] for i in idx) / len(idx)
    if depth >= max_depth or len(idx) < 2 * min_leaf:
        return node
    nf = len(X[0])
    feats = list(range(nf))
    if feats_pool and feats_pool < nf:
        rng.shuffle(feats)
        feats = sorted(feats[:feats_pool])
    parent = sum((y[i] - node.value) ** 2 for i in idx)
    best = None
    for f in feats:
        vals = sorted(set(X[i][f] for i in idx))
        if len(vals) < 2:
            continue
        for k in range(len(vals) - 1):
            thr = (vals[k] + vals[k + 1]) / 2
            li = [i for i in idx if X[i][f] <= thr]
            ri = [i for i in idx if X[i][f] > thr]
            if len(li) < min_leaf or len(ri) < min_leaf:
                continue
            ml = sum(y[i] for i in li) / len(li)
            mr = sum(y[i] for i in ri) / len(ri)
            sse = sum((y[i] - ml) ** 2 for i in li) + sum((y[i] - mr) ** 2 for i in ri)
            gain = parent - sse
            if best is None or gain > best[0]:
                best = (gain, f, thr, li, ri)
    if best is None or best[0] <= 1e-12:
        return node
    gain, f, thr, li, ri = best
    imp[f] = imp.get(f, 0.0) + gain
    node.feat, node.thr = f, thr
    node.left = _fit_tree(X, y, li, depth + 1, max_depth, min_leaf, feats_pool, rng, imp)
    node.right = _fit_tree(X, y, ri, depth + 1, max_depth, min_leaf, feats_pool, rng, imp)
    return node


def _pred_tree(node, x):
    while node.feat is not None:
        node = node.left if x[node.feat] <= node.thr else node.right
    return node.value


class GBoost:
    def __init__(self, n_estimators, learning_rate, max_depth, min_leaf,
                 subsample, feat_sub, seed):
        self.M, self.lr = n_estimators, learning_rate
        self.max_depth, self.min_leaf = max_depth, min_leaf
        self.subsample, self.feat_sub, self.seed = subsample, feat_sub, seed
        self.trees, self.base, self.importances = [], 0.0, {}

    def fit(self, X, y):
        rng = random.Random(self.seed)
        n = len(y)
        self.base = sum(y) / n
        F = [self.base] * n
        self.trees, imp = [], {}
        for _ in range(self.M):
            resid = [y[i] - F[i] for i in range(n)]
            if self.subsample < 1.0:
                k = max(2 * self.min_leaf, int(round(self.subsample * n)))
                idx = sorted(rng.sample(range(n), min(k, n)))
            else:
                idx = list(range(n))
            tree = _fit_tree(X, resid, idx, 0, self.max_depth, self.min_leaf,
                             self.feat_sub, rng, imp)
            for i in range(n):
                F[i] += self.lr * _pred_tree(tree, X[i])
            self.trees.append(tree)
        tot = sum(imp.values()) or 1.0
        self.importances = {f: v / tot for f, v in imp.items()}
        return self

    def staged_predict(self, x):
        p = self.base
        out = [p]
        for t in self.trees:
            p += self.lr * _pred_tree(t, x)
            out.append(p)
        return out

    def predict(self, x, m=None):
        p = self.base
        for t in (self.trees if m is None else self.trees[:m]):
            p += self.lr * _pred_tree(t, x)
        return p


# ====================================================================
# кросс-валидация LOO-по-областям
# ====================================================================
def _folds(ids, oblast):
    obs = sorted(set(oblast.values()))
    out = []
    for o in obs:
        te = [i for i, t in enumerate(ids) if oblast[t] == o]
        tr = [i for i in range(len(ids)) if oblast[ids[i]] != o]
        out.append((o, tr, te))
    return out


def _sub(rows, idx):
    return [rows[i] for i in idx]


def cv_oof(X, y, ids, oblast, cfg, cols=None):
    """OOF-кривая по числу деревьев + OOF-предсказания на best_m."""
    n = len(y)
    if cols is not None:
        X = [[row[c] for c in cols] for row in X]
    M = cfg["n_estimators"]
    sse_m = [0.0] * (M + 1)
    staged = {}  # i -> list of staged preds
    for o, tr, te in _folds(ids, oblast):
        g = GBoost(**cfg).fit(_sub(X, tr), _sub(y, tr))
        for i in te:
            sp = g.staged_predict(X[i])
            staged[i] = sp
            for m in range(M + 1):
                sse_m[m] += (y[i] - sp[m]) ** 2
    # ранняя остановка: минимум OOF SSE с терпением
    best_m, best_v, since = 0, sse_m[0], 0
    for m in range(1, M + 1):
        if sse_m[m] < best_v - 1e-12:
            best_m, best_v, since = m, sse_m[m], 0
        else:
            since += 1
            if since >= PATIENCE:
                break
    oof = [staged[i][best_m] for i in range(n)]
    return oof, best_m, [math.sqrt(s / n) for s in sse_m]


def _cv_oof_at(X, y, ids, oblast, cfg, m, cols=None):
    """OOF-предсказания при РОВНО m деревьях (без ранней остановки) — чтобы
    реальная оценка и перестановочный нуль сравнивались при одном m."""
    if cols is not None:
        X = [[row[c] for c in cols] for row in X]
    oof = [0.0] * len(y)
    for o, tr, te in _folds(ids, oblast):
        g = GBoost(**{**cfg, "n_estimators": m}).fit(_sub(X, tr), _sub(y, tr))
        for i in te:
            oof[i] = g.predict(X[i])
    return oof


def _r2(y, pred):
    """OOF R2 против нуль-предсказания (=чистый CCR для остаточной мишени)."""
    ss_res = sum((y[i] - pred[i]) ** 2 for i in range(len(y)))
    ss_tot = sum(v ** 2 for v in y)  # baseline = 0 (чистый CCR)
    return 1 - ss_res / ss_tot if ss_tot else 0.0


def _r2_meanbase(y, pred):
    m = sum(y) / len(y)
    ss_res = sum((y[i] - pred[i]) ** 2 for i in range(len(y)))
    ss_tot = sum((v - m) ** 2 for v in y)
    return 1 - ss_res / ss_tot if ss_tot else 0.0


# ====================================================================
# перестановочный нуль, повторная CV, важности, PD, вклады
# ====================================================================
def permutation_null(X, y, ids, oblast, cfg, best_m, n_perm=N_PERM):
    """Нуль-распределение OOF R2: тасуем y, тот же CV при ФИКСИРОВАННОМ m
    (иначе ранняя остановка на шуме занизила бы нуль и раздула значимость)."""
    rng = random.Random(cfg["seed"] + 101)
    real = _r2(y, _cv_oof_at(X, y, ids, oblast, cfg, best_m))
    null = []
    order = list(range(len(y)))
    for _ in range(n_perm):
        rng.shuffle(order)
        yp = [y[k] for k in order]
        null.append(_r2(yp, _cv_oof_at(X, yp, ids, oblast, cfg, best_m)))
    null.sort()
    ge = sum(1 for v in null if v >= real)
    p = (ge + 1) / (n_perm + 1)
    return {"realR2": round(real, 4), "p": round(p, 4),
            "null_p05": round(null[int(0.05 * n_perm)], 4),
            "null_p95": round(null[int(0.95 * n_perm)], 4),
            "null_median": round(null[n_perm // 2], 4)}


def repeated_cv(X, y, ids, oblast, cfg, best_m, n_rep=N_REPEAT):
    vals = []
    for r in range(n_rep):
        oof = _cv_oof_at(X, y, ids, oblast, {**cfg, "seed": cfg["seed"] + r}, best_m)
        vals.append(_r2(y, oof))
    vals.sort()
    return {"median": round(vals[n_rep // 2], 4),
            "p05": round(vals[int(0.05 * n_rep)], 4),
            "p95": round(vals[int(0.95 * n_rep)], 4)}


def perm_importance(X, y, ids, oblast, cfg, best_m, n_rep=15):
    """OOF-важность перестановки признака (при фикс. m) + нуль-полоса."""
    base_oof = _cv_oof_at(X, y, ids, oblast, cfg, best_m)
    base_mse = sum((y[i] - base_oof[i]) ** 2 for i in range(len(y))) / len(y)
    rng = random.Random(cfg["seed"] + 202)
    imp = {}
    for f in range(len(FEATURES)):
        incs = []
        for _ in range(n_rep):
            order = list(range(len(y)))
            rng.shuffle(order)
            Xp = [row[:] for row in X]
            col = [X[order[i]][f] for i in range(len(y))]
            for i in range(len(y)):
                Xp[i][f] = col[i]
            oof = _cv_oof_at(Xp, y, ids, oblast, cfg, best_m)
            mse = sum((y[i] - oof[i]) ** 2 for i in range(len(y))) / len(y)
            incs.append(mse - base_mse)
        incs.sort()
        imp[FEATURES[f]] = {"mean": round(sum(incs) / n_rep, 6),
                            "p05": round(incs[int(0.05 * n_rep)], 6),
                            "p95": round(incs[int(0.95 * n_rep)], 6)}
    return imp


def partial_dependence(model, X, f, grid_n=12):
    vals = sorted(row[f] for row in X)
    lo, hi = vals[0], vals[-1]
    grid = [lo + (hi - lo) * k / (grid_n - 1) for k in range(grid_n)]
    out = []
    for gv in grid:
        s = 0.0
        for row in X:
            xr = row[:]
            xr[f] = gv
            s += model.predict(xr)
        out.append([round(gv, 4), round(s / len(X), 5)])
    return out


def contributions(model, x):
    """Аддитивное разложение (pred - base) по признакам (деревья глуб.<=2).
    Каждое дерево = lr*leaf, делится по признакам пройденного пути поровну
    (приближение для депт-2). Сумма ≈ pred-base ТОЧНО, когда все деревья
    имеют хотя бы один сплит; корневые «пни» (без сплита) вносят
    неатрибутируемую константу lr*value и пропускаются — при shipped-config
    (best_m=42, subsample≈83, min_leaf=10) пней нет, невязка = 0."""
    contrib = {f: 0.0 for f in range(len(FEATURES))}
    for t in model.trees:
        if t.feat is None:
            continue
        path, node = [], t
        while node.feat is not None:
            path.append(node.feat)
            node = node.left if x[node.feat] <= node.thr else node.right
        delta = model.lr * node.value  # вклад дерева в (pred - base)
        for f in path:
            contrib[f] += delta / len(path)
    return {FEATURES[f]: round(v, 5) for f, v in contrib.items()}


# ====================================================================
# гонка MAPE (ПОНИЖЕНА) + вторичное окно 2009->2019 (перепись-золото)
# ====================================================================
def mape_horserace(panel, oof_resid):
    """CCR vs CCR+OOF-коррекция vs наивная. Коррекция ре-нормируется к тем же
    областным итогам, что и CCR (честная внутриобластная гонка)."""
    ids, obl = panel["ids"], panel["oblast"]
    ccr, naive, fact = panel["ccr"], panel["naive"], panel["fact"]
    # скорректированный уровень = CCR * exp(oof_resid), ре-нормировка по области
    corr_raw = {t: ccr[t] * math.exp(oof_resid[i]) for i, t in enumerate(ids)}
    corr = {}
    for o in sorted(set(obl.values())):
        kids = [t for t in ids if obl[t] == o]
        tgt = sum(ccr[t] for t in kids)   # тот же областной итог, что у CCR
        ss = sum(corr_raw[t] for t in kids)
        for t in kids:
            corr[t] = corr_raw[t] * tgt / ss

    def mape(pred):
        return round(sum(abs(pred[t] - fact[t]) / fact[t] * 100 for t in ids) / len(ids), 3)
    return {"ccr": mape(ccr), "ccr_plus_ml": mape(corr), "naive": mape(naive), "n": len(ids)}


def gold_window() -> dict:
    """Вторичный кросс-чек: 2009->2019 (перепись->перепись, ЗОЛОТО). Только
    СТРУКТУРНЫЕ признаки (2009 и ранее; зарплаты/свет/доступность на 2009-базе
    анахроничны). CCR тут НЕ бэктестится (нет когорт 1999->2009). Гейт —
    OOF R2 против базлайна «средняя убыль»."""
    obl = sub.oblast_of()
    sh09 = _age_shares(2009)
    sh19 = _age_shares(2019)
    data = json.loads((OUT / "data.json").read_text())["territories"]
    ids = sorted(t for t in sh09 if t in sh19)
    X, y, keep = [], [], []
    for t in ids:
        tot09, tot19 = sh09[t]["tot"], sh19[t]["tot"]
        if tot09 <= 0 or tot19 <= 0:
            continue
        # прежний-декадный лог-прирост 1999->2009 из data.json (host-периметр,
        # но лог-ОТНОШЕНИЕ ~периметр-устойчиво)
        pop = data[t]["pop"]
        p99 = pop.get("1999", [None])[0]
        p09 = pop.get("2009", [None])[0]
        prior = math.log(p09 / p99) if (p99 and p09) else 0.0
        X.append([sh09[t]["y"] / tot09, sh09[t]["o"] / tot09, math.log(tot09), prior])
        y.append(math.log(tot19 / tot09))
        keep.append(t)
    cfg = {**GB, "feat_sub": 3, "n_estimators": 250}
    oof, best_m, _ = cv_oof(X, y, keep, {t: obl[t] for t in keep}, cfg)
    return {"n": len(keep), "best_m": best_m,
            "oofR2_vs_declinemean": round(_r2_meanbase(y, oof), 4),
            "features": ["share014_09", "share65_09", "lnpop09", "prior_1999_2009"],
            "meanLogChange": round(sum(y) / len(y), 4)}


# ====================================================================
# сборка
# ====================================================================
def build() -> dict:
    panel = build_panel()
    X, y, ids, obl = panel["X"], panel["y"], panel["ids"], panel["oblast"]
    ctrl_cols = [FEATURES.index(f) for f in CTRL]

    # полная модель M1 (все признаки) + OOF
    oof, best_m, curve = cv_oof(X, y, ids, obl, GB)
    r2_full = _r2(y, oof)
    # структурная база M0 (только контроли)
    oof0, best_m0, _ = cv_oof(X, y, ids, obl, GB, cols=ctrl_cols)
    r2_ctrl = _r2(y, oof0)
    # прозрачность (аудит): один только mig_rate1519 (доминирующий драйвер)
    oof_mig, _, _ = cv_oof(X, y, ids, obl, {**GB, "feat_sub": 1},
                           cols=[FEATURES.index("mig_rate1519")])
    r2_mig = _r2(y, oof_mig)

    # честность: перестановочный нуль + повторная CV
    null = permutation_null(X, y, ids, obl, GB, best_m)
    rep = repeated_cv(X, y, ids, obl, GB, best_m)
    imp = perm_importance(X, y, ids, obl, GB, best_m)

    # финальная модель на всех данных (для вкладов и PD)
    full = GBoost(**{**GB, "n_estimators": best_m}).fit(X, y)
    # PD для топ-3 экзогенных по важности
    ranked = sorted(EXO, key=lambda f: imp[f]["mean"], reverse=True)
    pd = {f: partial_dependence(full, X, FEATURES.index(f)) for f in ranked[:3]}

    # districts: знаковая ошибка CCR + OOF + вклады
    districts = []
    for i, t in enumerate(ids):
        contrib = contributions(full, X[i])
        top = sorted(EXO, key=lambda f: abs(contrib[f]), reverse=True)[:2]
        districts.append({
            "id": t, "oblast": obl[t],
            "ccrResid": round(y[i], 4),        # ln(факт/CCR): + => CCR недооценил
            "oofPred": round(oof[i], 4),
            "fact2026": panel["fact"][t], "ccr2026": panel["ccr"][t],
            "host": panel["host"][t],
            "topDrivers": [{"f": f, "c": contrib[f]} for f in top],
            "features": {f: round(panel["feat_rows"][t][f], 4) for f in FEATURES},
        })

    horse = mape_horserace(panel, oof)
    signal = null["p"] < 0.05

    return {
        "version": "1.0.0",
        "window": "2019->2026 (перепись->оценка, 7 лет, OOS-окно CCR)",
        "n": len(ids),
        "target": "e_i = ln(факт_2026 / CCR_2026); + => CCR недооценил район",
        "skill": {
            "oofR2_full": round(r2_full, 4),      # против чистого CCR (нуль-предск.)
            "oofR2_ctrlOnly": round(r2_ctrl, 4),
            "oofR2_migOnly": round(r2_mig, 4),    # прозрачность: миграция ≈ вся модель
            "incrementalExo": round(r2_full - r2_ctrl, 4),
            "best_m": best_m, "best_m_ctrl": best_m0,
            "repeatedCV": rep,
        },
        "caveat": (
            "Мишень факт_2026 — официальная ОЦЕНКА Белстата (перепись-2019, "
            "прокрученная вперёд с ЗАРЕГИСТРИРОВАННОЙ миграцией 2019-2025), не "
            "независимый счёт. Доминирование миграции (только mig_rate1519 даёт "
            f"OOF R2={round(r2_mig, 2)} ≈ полная {round(r2_full, 2)}) частично "
            "отражает персистентность миграции, попадающую в бухгалтерию самой "
            "оценки, а не только слепое пятно CCR относительно независимой "
            "истины. Перепись->перепись окно 2009-2019 не несёт миграционных "
            "признаков (R2≈0,02), поэтому миграционный сигнал не проверен против "
            "настоящего счёта. Выигрыш MAPE 0,5 п.п. на n=118 (~6 фолдов) — в "
            "пределах CV-шума как единичное число: показывает предсказуемость "
            "ошибки, а не прогнозное превосходство."),
        "permutationNull": null,
        "signalDetected": signal,
        "verdict": (
            "CCR оставляет ковариат-детектируемую систематическую ошибку "
            f"(OOF R2={null['realR2']}, p={null['p']})"
            if signal else
            "CCR НЕ оставляет ковариат-детектируемой систематической ошибки на "
            f"уровне районов (OOF R2={null['realR2']} внутри нуль-полосы, p={null['p']}) "
            "— положительная валидация структурной модели"),
        "importance": imp,
        "importanceRank": ranked,
        "partialDependence": pd,
        "mapeHorserace": horse,
        "goldWindow": gold_window(),
        "config": {k: GB[k] for k in ("n_estimators", "learning_rate", "max_depth",
                                      "min_leaf", "subsample", "feat_sub", "seed")},
        "features": FEATURES, "exogenous": EXO, "controls": CTRL,
        "districts": districts,
    }


def main() -> None:
    b = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mlchallenger.json").write_text(json.dumps(b, ensure_ascii=False))
    s = b["skill"]
    print(f"OK: mlchallenger.json ({b['n']} районов, окно {b['window']})")
    print(f"  OOF R2 (полная) = {s['oofR2_full']} · только контроли = {s['oofR2_ctrlOnly']} "
          f"· инкремент экзо = {s['incrementalExo']}")
    print(f"  повторная CV R2: медиана {s['repeatedCV']['median']} "
          f"[{s['repeatedCV']['p05']}; {s['repeatedCV']['p95']}]")
    print(f"  перестановочный нуль: p={b['permutationNull']['p']} "
          f"(нуль-полоса [{b['permutationNull']['null_p05']}; {b['permutationNull']['null_p95']}])")
    print(f"  ВЕРДИКТ: {b['verdict']}")
    print(f"  топ-важности (экзо): {b['importanceRank'][:3]}")
    h = b["mapeHorserace"]
    print(f"  MAPE (понижена): CCR {h['ccr']}% · CCR+ML {h['ccr_plus_ml']}% · наив {h['naive']}%")
    g = b["goldWindow"]
    print(f"  золото 2009->2019 (структ., {g['n']} р-нов): OOF R2 vs средняя убыль = {g['oofR2_vs_declinemean']}")


if __name__ == "__main__":
    main()
