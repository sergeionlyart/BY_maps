# Происхождение данных

- `web/public/data/nightlights_v2.json` — итог пакета `nightlights`
  v2.1.1 (тег `artifact-nightlights-v2.1.1`): гармонизация DMSP
  (Li et al., Figshare 9828827 v10, calDMSP) и VIIRS VNL v2.1
  (EOG, зеркало Zenodo 17294744) схемой «мост» (b=0,9151, R²=0,9217,
  стык −2,99 % out-of-sample), модель 2030–2075 на прогнозе v2026.4.
  Полный реестр сырья с URL и sha256 — `sources/registry.csv`.
- `web/public/data/data.json` — демографический ряд проекта по 119
  зонам (Белстат: переписи 1897–2019, текущие оценки до 2026).
- `params/assumptions.json` — канонические допущения INF-08
  (β-эластичности, классификация зон, пороги demo-слоя).
- Выходы (`research_candidates.json`, `divergence_decomposition.json`)
  детерминированы: одинаковые входы дают байт-в-байт одинаковый
  результат (проверяется `--check` при сборке).
