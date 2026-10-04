# Лицензии

## Пакет

Код (`code/`, `checks/`), документация и производные данные
(`data/final/`, `sources/raw/cells.csv.gz`, `sources/raw/cities50k.json`)
— **CC BY 4.0**: используйте свободно со ссылкой на проект
«Население Беларуси, 1897–2026» и версию пакета (см. CITATION.cff).
Права на исходные наборы сохраняются за их правообладателями (ниже); при
использовании производных ссылайтесь и на первоисточники.

## Источники

- **WSF Evolution** — German Aerospace Center (DLR), CC BY 4.0.
  В пакете — только производные колонки `wsf_*` таблицы ячеек.
- **GHS-BUILT-S R2023A, GHS-POP R2023A** — European Commission, Joint
  Research Centre, CC BY 4.0. В пакете — колонки `built_*`, `pop_*`.
- **Гармонизированный ряд ночных огней Li et al., v10** (Figshare 9828827) —
  CC BY 4.0. В пакете — колонки `li_*`.
- **VIIRS VNL v2.1** (Earth Observation Group, Colorado School of Mines;
  зеркало OpenGeoHub на Zenodo 17294744) — зеркало под CC BY 4.0, EOG VNL —
  свободное использование с цитированием. В пакете — колонки `vnl_*`.
- **GLAD cropland** (Potapov et al., 2022, Nature Food 3: 19–28) — открытый
  доступ с цитированием; условия использования — на странице набора
  https://glad.umd.edu/dataset/croplands. В пакете — колонки `crop_*`.
- **GeoNames cities15000** — CC BY 4.0. В пакете — выжимка
  `sources/raw/cities50k.json` (93 города).
- **geoBoundaries gbOpen ADM0** (`sources/raw/neighbors_adm0.geojson`) —
  лицензии по странам указаны в свойствах каждого объекта: Польша — Other -
  Humanitarian (Wiki Commons Media); Литва, Россия, Украина — Open Data
  Commons Open Database License 1.0 (OpenStreetMap); Латвия — CC BY 4.0
  (Geoportal of Latvia). Файл распространяется в составе пакета на этих
  условиях; данные OpenStreetMap — © участники OpenStreetMap, ODbL.
- **Граница Беларуси проекта** (не вложена) — geoBoundaries gbOpen BLR ADM1,
  CC BY 3.0, обработка BY Maps.
- **Официальные ряды населения** (`sources/raw/units/`) — официальная
  статистика: Белстат (через ряды BY Maps, CC BY 4.0), GUS (Bank Danych
  Lokalnych), Статистика Литвы (OSP), Статистика Латвии (CSP), Росстат,
  перепись Украины 2001 и Госстат Украины (издания — CC BY 4.0), перепись 1989
  в публикации Демоскопа (ИД НИУ ВШЭ). Используется с указанием источника
  (столбец `source` каждой строки); статистические значения — факты. Центроиды:
  GUGiK PRG (открытые данные PZGiK), Wikidata (CC0). Сборка таблиц — CC BY 4.0.
