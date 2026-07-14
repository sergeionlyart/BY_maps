#!/usr/bin/env python3
"""Черновой датасет для раздела «Пирамида» (INF-11 / R-1).

Собирает национальные возрастно-половые структуры из уже завендоренных
данных репозитория BY_maps и пишет pyramids_draft.json.

Состав:
  2009, 2019          — переписи (curated/age2009.csv, age2019.csv; OLAP F201N);
  2020–2026           — официальные оценки (curated/age_current.csv, dataportal);
  2030–2075 (шаг 5)   — ЗАГЛУШКА из UN WPP 2024 single-age (medium/high/low),
                        подлежит замене экспортом CCMPP (см. TZ_PYRAMID.md, задача P-3).

Запуск из корня репозитория:  python3 handoff/08_pyramid/build_pyramids_draft.py
Выход: handoff/08_pyramid/data/pyramids_draft.json

Только stdlib. Детерминированно (sort_keys, фикс. разделители).
"""
import csv, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'pyramids_draft.json')
OBLASTS = {'BY-BR', 'BY-HM', 'BY-HO', 'BY-HR', 'BY-MA', 'BY-MI', 'BY-VI'}
GROUPS = ['0-4','5-9','10-14','15-19','20-24','25-29','30-34','35-39','40-44',
          '45-49','50-54','55-59','60-64','65-69','70-74','75-79','80+']

def norm_group(a: str) -> str:
    a = a.replace(' ', '')
    # переписные файлы могут дробить/именовать старшие группы иначе — сводим в 80+
    if a in ('80-84', '85-89', '90-94', '95-99', '100+', '85+', '90+') or a.startswith('80и'):
        return '80+'
    if 'неопредел' in a.lower() or 'н/у' in a.lower():
        return 'unknown'
    return a

def load_census(path):
    g = defaultdict(lambda: defaultdict(int))
    with open(path) as f:
        for r in csv.DictReader(f):
            if r['territory_id'] in OBLASTS and r.get('locality') in ('urban', 'rural'):
                g[r['sex']][norm_group(r['age_group'])] += int(r['pop'])
    return g

def load_current(path):
    by_year = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    with open(path) as f:
        for r in csv.DictReader(f):
            if r['territory_id'] == 'BY' and r['locality'] == 'total':
                by_year[int(r['year'])][r['sex']][norm_group(r['age_group'])] += int(r['pop'])
    return by_year

def load_wpp(variant):
    path = os.path.join(ROOT, 'data/raw/wpp2024', f'blr_single_age_{variant}_2024-2100.csv')
    by_year = defaultdict(lambda: {'m': defaultdict(float), 'f': defaultdict(float)})
    with open(path) as f:
        for r in csv.DictReader(f):
            y = int(r['Time']); a = int(r['AgeGrpStart'])
            grp = GROUPS[min(a // 5, 16)]
            by_year[y]['m'][grp] += float(r['PopMale']) * 1000
            by_year[y]['f'][grp] += float(r['PopFemale']) * 1000
    return by_year

def as_series(g):
    d = {s: [round(g[s].get(a, 0)) for a in GROUPS] for s in ('m', 'f')}
    unknown = round(g['m'].get('unknown', 0) + g['f'].get('unknown', 0))
    if unknown:
        d['unknown'] = unknown  # «возраст не определён»: в бары не входит, в итог входит
    return d

def main():
    series = {}
    for year, path in ((2009, 'data/curated/age2009.csv'), (2019, 'data/curated/age2019.csv')):
        g = load_census(os.path.join(ROOT, path))
        series[str(year)] = {'type': 'census', 'source': os.path.basename(path), **as_series(g)}
    cur = load_current(os.path.join(ROOT, 'data/curated/age_current.csv'))
    for y in sorted(cur):
        if y == 2019:  # за 2019 приоритет у переписи
            continue
        series[str(y)] = {'type': 'estimate', 'source': 'age_current.csv (Белстат dataportal)', **as_series(cur[y])}
    variant_map = {'base': 'medium', 'optimistic': 'high', 'negative': 'low'}
    for scen, variant in variant_map.items():
        wpp = load_wpp(variant)
        for y in range(2030, 2076, 5):
            key = f'{y}:{scen}'
            series[key] = {'type': 'model-placeholder',
                           'source': f'UN WPP 2024 {variant} (ЗАГЛУШКА: заменить экспортом CCMPP v2026.4)',
                           **as_series(wpp[y])}
    out = {
        'version': 'draft-0.1',
        'unit': 'человек',
        'age_groups': GROUPS,
        'note': ('Черновик для прототипирования UI. Будущие годы — варианты WPP-2024 как заглушка; '
                 'сценарии сайта (base/optimistic/negative) должны прийти из экспорта CCMPP. '
                 'История 1959–1999 добавляется по задаче P-2 (Демоскоп/Белстат).'),
        'series': series,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(out, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    # контрольные значения
    def tot(k):
        s = series[k]; return sum(s['m']) + sum(s['f']) + s.get('unknown', 0)
    checks = {'2009': 9503807, '2019': 9413446, '2026': 9056080}
    for k, expect in checks.items():
        got = tot(k)
        status = 'OK' if got == expect else f'MISMATCH (expect {expect})'
        print(f'check {k}: {got} {status}')
    print('written', OUT, '| series:', len(series))

if __name__ == '__main__':
    sys.exit(main())
