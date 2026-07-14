# Крыніцы даных

Усе сырыя файлы завендораныя ў `data/raw/` (здымак ад 2026-07-11) і
перазагружаюцца скрыптом `python -m etl.fetch --force`.

## Статыстыка насельніцтва

| Файл | Крыніца | Змест | Ліцэнзія/умовы |
|---|---|---|---|
| `ps_div.html` | [pop-stat.mashke.org/belarus-division.htm](https://pop-stat.mashke.org/belarus-division.htm) (склад. Tim Bespyatov) | Вобласці і 118 раёнаў: перапісы 1970, 1979, 1989, 1999, 2009, 2019 + штогадовыя афіцыйныя ацэнкі Белстата 1991, 2004–2026 | кампіляцыя афіцыйных публікацый (перапісы СССР/РБ, Белстат); выкарыстоўваецца з указаннем крыніцы |
| `ps_cities.html` | [pop-stat.mashke.org/belarus-cities.htm](https://pop-stat.mashke.org/belarus-cities.htm) | 220+ гарадоў і гп: перапісы 1897, 1923, 1926, 1939, 1959, 1970, 1979, 1989, 1999, 2009, 2019 + ацэнкі да 2026 | тое ж |
| `demo59.html` … `demo89.html` | Демоскоп Weekly: [ussr59_reg1](https://www.demoscope.ru/weekly/ssp/ussr59_reg1.php), ussr70_reg1, ussr79_reg1, sng89_reg1 | Вынікі перапісаў СССР 1959/1970/1979/1989 па абласцях БССР: усё/гарадское/сельскае насельніцтва | публікацыя вынікаў перапісаў; выкарыстоўваецца з указаннем крыніцы |
| `curated/country_history.csv` | Белстат, «Дэмаграфічны штогоднік Рэспублікі Беларусь» (рэтраспектыўныя ацэнкі ў сучасных межах) | Колькасць насельніцтва краіны: 1897 — 6 673 тыс., 1913 — 6 899 тыс., 1940 — 9 046 тыс., 1950 — 7 709 тыс. | афіцыйныя рэтраспектыўныя ацэнкі; тып `reconstructed` |

## Геаданыя

| Файл | Крыніца | Змест | Ліцэнзія |
|---|---|---|---|
| `gb-BLR-ADM1.geojson` | [geoBoundaries](https://www.geoboundaries.org/) gbOpen BLR ADM1 (першакрыніца CIESIN) | 6 абласцей + Мінск | CC BY 3.0 |
| `gb-BLR-ADM2.geojson` | geoBoundaries gbOpen BLR ADM2 | 117 раёнаў + Мінск (Дрыбінскі раён у крыніцы адсутнічае) | CC BY 3.0 |
| `drybin_osm.json` | OpenStreetMap праз Overpass API (relation 70618) | Мяжа Дрыбінскага раёна | ODbL |
| `wikidata_settlements.json` | Wikidata SPARQL (класы «горад», «горад абласнога/раённага падпарадкавання», «гарадскі/рабочы пасёлак») | Каардынаты і рускія назвы ~204 гарадскіх НП | CC0 |

## Праверачныя канстанты (у тэстах)

Афіцыйныя долі гарадскога насельніцтва па перапісах — 1999: 69,3%, 2009: 74,5%,
2019: 77,6% (Белстат, вынікі перапісаў) — выкарыстоўваюцца як эталон для праверкі
вылічаных сум па гарадах (допуск 1,5 п.п.).

## Начная свяцільнасць (INF-08 «Беларусь з космасу», v2)

| Файл | Крыніца | Змест | Ліцэнзія |
|---|---|---|---|
| `nightlights/rasters/dmsp_<1992–2013>.tif` | [Li et al., Harmonization of DMSP and VIIRS NTL 1992–2024](https://doi.org/10.6084/m9.figshare.9828827) (Figshare, v10) | Каліброваны DMSP-OLS stable lights, выразкі па Беларусі (DN 0–63, ~1 км); глабальныя файлы не вендорацца — URL і sha256 у `registry_v2.csv` | CC BY 4.0 |
| `nightlights/rasters/vnl_<2012–2024>.tif` | [EOG VIIRS VNL v2.1 annual, люстэрка OpenGeoHub](https://zenodo.org/records/17294744) (Zenodo) | Сапраўдныя гадавыя кампазіты EOG (average), 500 м, выразкі па Беларусі ў нВт/см²/ср; факелы двух НПЗ замаскаваныя | CC BY 4.0 (люстэрка); EOG VNL — свабоднае выкарыстанне з цытаваннем |
| `nightlights/zonal_light.csv` | [WorldPop VIIRS fvf](https://data.worldpop.org/GIS/Covariates/Global_2015_2030/BLR/VIIRS/v1/fvf/) | Занальныя сумы v1 (100 м, average_masked, 2015–2023) — незалежная крыжаваная праверка раду VNL | CC BY 4.0 |
