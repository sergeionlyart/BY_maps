"""Тесты ETL: полнота реестра, корректность парсинга, инварианты сборки."""
import json

import pytest

from etl.common import RAW
from etl.parse_popstat import parse_division, parse_cities
from etl.parse_demoscope import parse_regions
from etl.registry import RAIONS, WEST_1921, OBLAST_CITIES_HOST
from etl.build import build, DEMOSCOPE_YEARS

OBL_IDS = ["BY-BR", "BY-VI", "BY-HO", "BY-HR", "BY-MI", "BY-MA"]


@pytest.fixture(scope="session")
def div():
    return parse_division(RAW / "ps_div.html")


@pytest.fixture(scope="session")
def cities():
    return parse_cities(RAW / "ps_cities.html")


@pytest.fixture(scope="session")
def built():
    return build()


# --- реестр -----------------------------------------------------------------

def test_registry_counts():
    assert len(RAIONS) == 118
    assert len(WEST_1921) == 46
    assert WEST_1921 <= set(RAIONS)


def test_registry_matches_geoboundaries():
    gj = json.loads((RAW / "gb-BLR-ADM2.geojson").read_text())
    shape_names = {f["properties"]["shapeName"] for f in gj["features"]}
    reg_names = {g for _, g, _ in RAIONS.values() if g is not None}
    assert reg_names <= shape_names
    # все фичи использованы: 117 районов + Minsk City
    assert shape_names - reg_names == {"Minsk City"}
    missing_poly = [lat for lat, (_, g, _) in RAIONS.items() if g is None]
    assert missing_poly == ["Drybinski"]  # берётся из OSM


# --- парсинг pop-stat --------------------------------------------------------

def test_division_raions_complete(div):
    parsed = {lat for lat, _, _ in div["raions"].values()}
    assert parsed == set(RAIONS)


def test_division_known_census_values(div):
    assert div["country"][1999] == (10_045_237, "census")
    assert div["country"][2019] == (9_413_446, "census")
    assert div["minsk"][2009] == (1_836_808, "census")


def test_oblast_cities_parsed(div):
    assert set(div["obl_cities"]) == set(OBLAST_CITIES_HOST)


def test_cities_known_values(cities):
    assert cities["Мінск"]["series"][1897] == (90_912, "census")
    assert cities["Гомель"]["series"][2019][0] == 510_459
    # приоритет переписи над оценкой того же года
    assert cities["Мінск"]["series"][2019] == (1_992_685, "estimate") or \
           cities["Мінск"]["series"][2019][1] == "census"


def test_raion_centers_exist(cities):
    for lat, (_, _, center) in RAIONS.items():
        if center is not None:
            assert center in cities, f"центр района {lat} ({center}) не найден"


# --- демоскоп ----------------------------------------------------------------

@pytest.mark.parametrize("year", sorted(DEMOSCOPE_YEARS))
def test_demoscope_internally_consistent(year):
    res = parse_regions(RAW / DEMOSCOPE_YEARS[year])
    total = sum(v[0] for v in res["oblasts"].values()) + res["minsk_city"][0]
    assert total == res["country"][0]
    # городское + сельское = всего
    t, u, r = res["country"]
    assert u + r == t


# --- сборка ------------------------------------------------------------------

def test_territory_counts(built):
    t = built["territories"]
    assert sum(1 for x in t.values() if x["level"] == "raion") == 118
    assert sum(1 for x in t.values() if x["level"] == "oblast") == 7
    assert sum(1 for x in t.values() if x["level"] == "country") == 1
    assert sum(1 for x in t.values() if x["level"] == "city") > 200


def test_oblast_sums_match_country(built):
    t = built["territories"]
    for y in ["1959", "1970", "1989", "1999", "2009", "2019", "2025"]:
        vals = [t[o]["pop"].get(y) for o in OBL_IDS + ["BY-HM"]]
        if not all(vals):
            continue
        s = sum(v[0] for v in vals)
        country = t["BY"]["pop"][y][0]
        assert abs(s - country) / country < 0.005, (y, s, country)


def test_raion_sums_match_oblast_2019(built):
    t = built["territories"]
    for obl in OBL_IDS:
        s = sum(x["pop"]["2019"][0] for x in t.values()
                if x["level"] == "raion" and x["parent"] == obl)
        official = t[obl]["pop"]["2019"][0]
        assert abs(s - official) / official < 0.005, (obl, s, official)


def test_areas_positive_and_plausible(built):
    t = built["territories"]
    for x in t.values():
        if x["level"] in ("raion", "oblast", "country"):
            assert x["area"] > 100, x["id"]
    assert abs(t["BY"]["area"] - 207_600) / 207_600 < 0.01
    drybin = t["r-drybinski"]
    assert abs(drybin["area"] - 766) / 766 < 0.05


def test_no_center_le_total(built):
    t = built["territories"]
    for x in t.values():
        if x["level"] != "raion":
            continue
        for y, (v, _) in x["popNoCenter"].items():
            assert 0 <= v <= x["pop"][y][0], (x["id"], y)


def test_data_types_valid(built):
    t = built["territories"]
    for x in t.values():
        for key in ("pop", "urban", "popNoCenter", "popAdmin"):
            for y, (v, dt) in x.get(key, {}).items():
                assert dt in ("c", "e", "r", "m"), (x["id"], key, y, dt)
                assert v >= 0


def test_raion_centers_have_coords(built):
    t = built["territories"]
    for x in t.values():
        if x["level"] == "raion":
            for cid in x["center"]:
                assert t[cid].get("lon"), (x["id"], cid)


def test_urban_share_close_to_official(built):
    """Вычисленная сумма городских НП близка к официальной доле городского
    населения (справочно: 1999 - 69,3%, 2009 - 74,5%, 2019 - 77,6%)."""
    t = built["territories"]
    official = {"1999": 0.693, "2009": 0.745, "2019": 0.776}
    for y, share in official.items():
        urban = t["BY"]["urban"][y][0]
        pop = t["BY"]["pop"][y][0]
        assert abs(urban / pop - share) < 0.015, (y, urban / pop)


def test_urban_official_matches_demoscope(built):
    t = built["territories"]
    assert t["BY"]["urban"]["1959"] == [2_538_294, "c"] or \
           t["BY"]["urban"]["1959"] == (2_538_294, "c")


def test_panel_shares_increasing(built):
    """Гипотеза концентрации: доля Минска и семи крупнейших городов растёт
    на каждом переписном интервале с 1959 г."""
    panel = {row["year"]: row for row in built["panel"]}
    years = [1959, 1970, 1979, 1989, 1999, 2009, 2019]
    for a, b in zip(years, years[1:]):
        sa = panel[a]["minsk"] / panel[a]["pop"]
        sb = panel[b]["minsk"] / panel[b]["pop"]
        assert sb > sa, ("minsk", a, b)
        ta = panel[a]["top7"] / panel[a]["pop"]
        tb = panel[b]["top7"] / panel[b]["pop"]
        assert tb > ta, ("top7", a, b)
