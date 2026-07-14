# Происхождение данных (INF-08, v2.0.0)

```
РЕТРО 1992-2013                          СОВРЕМЕННОСТЬ 2012-2024
Li et al., Harmonization of DMSP         EOG VIIRS VNL v2.1 annual
and VIIRS NTL 1992-2024 (Figshare,       «average» (Colorado School of
CC BY 4.0): calDMSP - DMSP-OLS           Mines / Payne Institute) в
stable lights, интеркалиброван,          зеркале OpenGeoHub (Zenodo
DN 0-63, ~1 км; simVIIRS - VIIRS         17294744, CC BY 4.0), 500 м
в DMSP-шкале (мост + спайк)              EPSG:4326, значения x10
        │                                        │
        ▼  etl/nightlights_fetch.py (rasterio, однократно):
        │  вырезка bbox Беларуси, маска страны (adm1, all_touched),
        │  обнуление факелов двух НПЗ (диски 2,5 км, assumptions),
        │  VNL x0,1 -> нВт/см²/ср; sha256 глобальных файлов и вырезок
        │  -> sources/registry.csv (83 записи)
        ▼
  data/raw/nightlights/rasters/{dmsp_1992..2013, vnl_2012..2024}.tif
        │
        ▼  etl/nightlights_zonal.py (rasterio, однократно):
        │  растеризация 118 районов (adm2) + Минск (adm1) по центру
        │  пикселя; пороги DN>=1 / >=1 нВт; освещённая площадь (км²);
        │  разложение 2024 на floor (1-5 нВт) и bright (>=5 нВт)
        ▼
  zonal_dmsp.csv · zonal_vnl.csv · zonal_simviirs.csv · floor_2024.csv
        │
        ▼  etl/nightlights_harmonize.py (stdlib):
        │  f18-коррекция (x0,486) -> мост ln V = a_y + b ln S
        │  (simVIIRS/VNL 2014-2024, R² 0,92) -> ретро в радианс-экв.;
        │  стык out-of-sample -3,0%; кросс-проверка WorldPop fvf
        │  (zonal_light.csv, источник v1) R² 0,93-0,98
        ▼  etl/nightlights_model.py (stdlib):
        │  межрайонные эластичности (bright ~ pop, 2024) по классам;
        │  light(t) = bright*(pop(t)/pop2024)^beta + floor;
        │  входы: web/public/data/forecast.json (v2026.4, 3 сценария
        │  x 2 старта; районы adjusted = official x обл. отношение)
        ▼  etl/nightlights_v2.py (stdlib):
  web/public/data/nightlights_v2.json  (доли 1992-2024 + модель
        │                               2030-2075 + v1-индекс по VNL)
        ▼  etl/nightlights_frames.py / tools/render_reel_space.py
  PNG-кадры сайта и рилс 9:16 (детерминированы, сид 20260712)
```

Все шаги от зональных CSV детерминированы и идут на стандартной
библиотеке (run.sh); rasterio нужен только для однократных растровых
шагов (код вендорен, вырезки растров вендорены — цепочку можно
проверить с любого звена). Ряды населения — web/public/data/data.json;
прогноз — web/public/data/forecast.json (пакет forecast v1.3.0).

Отвергнутые альтернативы: «NPP-VIIRS-like» V2 (v1; нефизичная
нестабильность) и «готовый» гармонизированный simVIIRS как современный
сегмент (волатильность долей x1,9 от фактического VNL, 13 нулевых
зоно-лет малых районов) — числа в docs/notes/nightlights_v2_validation.md.
