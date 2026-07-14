"""INF-08 v3: delta-слои карты света (изменение относительно базы).

delta = log1p(radiance_cur) - log1p(radiance_ref) на радианс-эквивалентных
полях визуального слоя (кэш data/tmp/nl_fields, единая сетка VNL);
даунсемпл 2x2 (подавление пиксельного шума) + сглаживание 3x3 + порог
значимости + кап насыщения. ОДНА фиксированная шкала на все годы -
по-кадровая нормализация запрещена (сравнимость между годами).

Наборы:
  previous_year/  py_<год>.png (внутри сегмента; 2012 исключён - смена
                  источника), pym_<узел>_<сцен>_<старт>.png (модель,
                  относительно предыдущего узла)
  base_2024/      b24_<узел>_<сцен>_<старт>.png (модель против
                  наблюдения-2024; помечено model_vs_observed)
  scenarios/      sc_<узел>_<негатив|оптимизм>_<старт>.png (signed-delta
                  сценария против базового того же узла)
  base_<год>/     ab_<год>.png (режим «Анализ»: наблюдаемые годы против
                  фиксированных базовых лет; кросс-источниковые пары
                  помечаются)

Палитра двунаправленная и дальтоник-безопасная: рост - тёплый янтарь,
спад - холодный сине-бирюзовый, |delta| ниже порога - прозрачно.
Направление дополнительно кодируется знаком в карточках UI.

Запуск (требует numpy+Pillow; поля - после etl.nightlights_visual):
  python -m etl.nightlights_delta
    -> web/public/data/nightlights/delta/...
    -> манифест дополняется секцией "deltas"
"""
from __future__ import annotations

import json
import math

import numpy as np
from PIL import Image

from .common import OUT
from . import nightlights_model as M
from .nightlights_visual import NL, FIELDS

DELTA = NL / "delta"

THRESHOLD = 0.15     # |dln(1+rad)| ниже - незначимо (прозрачно)
DIM_MASK_NW = 1.5    # оба пикселя тусклее - шум сенсора, не сигнал
CAP = 1.2            # кап насыщения шкалы
ALPHA_GAMMA = 0.7    # альфа = (|d|/CAP)^gamma
ANALYSIS_BASES = [1992, 2000, 2012, 2019, 2024]

WARM = (255, 176, 76)    # рост
COOL = (74, 189, 224)    # спад


def _load(key: str) -> np.ndarray:
    return np.load(FIELDS / f"{key}.npy").astype("float64")


def _downsample2(a: np.ndarray) -> np.ndarray:
    h, w = a.shape
    h2, w2 = h // 2 * 2, w // 2 * 2
    return a[:h2, :w2].reshape(h2 // 2, 2, w2 // 2, 2).mean(axis=(1, 3))


def _box3(a: np.ndarray) -> np.ndarray:
    p = np.pad(a, 1, mode="edge")
    return (p[:-2, :-2] + p[:-2, 1:-1] + p[:-2, 2:] +
            p[1:-1, :-2] + p[1:-1, 1:-1] + p[1:-1, 2:] +
            p[2:, :-2] + p[2:, 1:-1] + p[2:, 2:]) / 9.0


def delta_field(cur_key: str, ref_key: str) -> np.ndarray:
    cur, ref = _load(cur_key), _load(ref_key)
    d = np.log1p(cur) - np.log1p(ref)
    lit = np.maximum(cur, ref) >= DIM_MASK_NW   # тусклое = шум сенсора
    d = _box3(_downsample2(np.where(lit, d, 0.0)))
    d = np.where(np.abs(d) < THRESHOLD, 0.0, d)
    return np.clip(d, -CAP, CAP)


def render(d: np.ndarray, path) -> None:
    h, w = d.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    mag = np.abs(d) / CAP
    alpha = np.where(mag > 0, np.power(mag, ALPHA_GAMMA) * 230, 0)
    pos = d > 0
    for c in range(3):
        rgba[:, :, c] = np.where(pos, WARM[c], COOL[c])
    rgba[:, :, 3] = np.clip(alpha, 0, 255).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def main() -> None:
    for d in ["previous_year", "base_2024", "scenarios"] + \
             [f"base_{b}" for b in ANALYSIS_BASES]:
        (DELTA / d).mkdir(parents=True, exist_ok=True)
    assump = M.load_assumptions()
    nodes = assump["model"]["nodes"]
    index = []

    def emit(cur, ref, sub, name, kind, **meta):
        d = delta_field(cur, ref)
        p = DELTA / sub / name
        render(d, p)
        index.append({"kind": kind,
                      "asset": f"/data/nightlights/delta/{sub}/{name}",
                      "cur": cur, "ref": ref, **meta})

    # предыдущий сопоставимый год (внутри сегмента)
    for y in range(1993, 2012):
        emit(f"y{y}", f"y{y - 1}", "previous_year", f"py_{y}.png",
             "previous_year", year=y, refYear=y - 1,
             crossSource=False)
    for y in range(2013, 2025):
        emit(f"y{y}", f"y{y - 1}", "previous_year", f"py_{y}.png",
             "previous_year", year=y, refYear=y - 1, crossSource=False)
    print("  previous_year (наблюдения): ok")
    for jmp in M.JUMPOFFS:
        for scn in M.SCENARIOS:
            for i in range(1, len(nodes)):
                t, tp = nodes[i], nodes[i - 1]
                emit(f"m{t}_{scn}_{jmp}", f"m{tp}_{scn}_{jmp}",
                     "previous_year", f"pym_{t}_{scn}_{jmp}.png",
                     "previous_node", year=t, refYear=tp, scenario=scn,
                     jumpoff=jmp, crossSource=False)
    print("  previous_year (модель): ok")

    # модель против наблюдения-2024
    for jmp in M.JUMPOFFS:
        for scn in M.SCENARIOS:
            for t in nodes:
                emit(f"m{t}_{scn}_{jmp}", "y2024", "base_2024",
                     f"b24_{t}_{scn}_{jmp}.png", "base_2024",
                     year=t, refYear=2024, scenario=scn, jumpoff=jmp,
                     crossSource=True,
                     note="model_vs_observed")
    print("  base_2024: ok")

    # сценарии против базового (тот же узел)
    for jmp in M.JUMPOFFS:
        for scn in ["negative", "optimistic"]:
            for t in nodes:
                emit(f"m{t}_{scn}_{jmp}", f"m{t}_base_{jmp}",
                     "scenarios", f"sc_{t}_{scn}_{jmp}.png",
                     "scenario_vs_base", year=t, scenario=scn,
                     jumpoff=jmp, crossSource=False)
    print("  scenarios: ok")

    # режим «Анализ»: фиксированные базовые годы
    for b in ANALYSIS_BASES:
        for y in list(range(1992, 2025)):
            if y == b:
                continue
            cross = (y < 2012) != (b < 2012)
            emit(f"y{y}", f"y{b}", f"base_{b}", f"ab_{y}.png",
                 "analysis_base", year=y, refYear=b, crossSource=cross)
        print(f"  base_{b}: ok")

    manifest_p = NL / "nightlights_manifest.json"
    manifest = json.loads(manifest_p.read_text())
    manifest["deltas"] = {
        "note": ("delta = log1p(rad) - log1p(ref) на радианс-эквивалентных "
                 "полях; даунсемпл 2x2, сглаживание 3x3, порог "
                 f"{THRESHOLD}, кап {CAP}; единая шкала на все годы; "
                 "рост - тёплый, спад - холодный, незначимое - прозрачно; "
                 "кросс-источниковые пары помечены crossSource"),
        "threshold": THRESHOLD, "cap": CAP,
        "analysisBases": ANALYSIS_BASES,
        "items": index}
    manifest_p.write_text(json.dumps(manifest, ensure_ascii=False,
                                     indent=1))
    sizes = sorted((NL / i["asset"].removeprefix("/data/nightlights/"))
                   .stat().st_size for i in index)
    print(f"OK: {len(index)} delta-кадров, медиана "
          f"{sizes[len(sizes) // 2] // 1024} КБ, макс {sizes[-1] // 1024} КБ")


if __name__ == "__main__":
    main()
