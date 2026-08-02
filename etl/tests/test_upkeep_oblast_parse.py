from etl.upkeep_oblast_parse import parse_series, parse_year_labels


def test_parse_series_arrow_chain():
    s = "Бешенковичский 3622→1379; Браславский 5609→2388"
    assert parse_series(s, "Бешенковичский") == [3622.0, 1379.0]
    assert parse_series(s, "Браславский") == [5609.0, 2388.0]


def test_parse_series_colon_arrow():
    s = "Кореличский: 15/15/14/13/12/11"
    assert parse_series(s, "Кореличский") == [15.0, 15.0, 14.0, 13.0, 12.0, 11.0]


def test_parse_series_equals_single():
    s = "Гродненская область (итого)=470; Кореличский=15"
    assert parse_series(s, "Кореличский") == [15.0]


def test_parse_series_not_found():
    assert parse_series("Ушачский=5", "Кореличский") == []


def test_parse_year_labels_explicit_list():
    years = parse_year_labels("2015, 2018, 2019, 2020, 2021, 2022, 2023 (на начало уч. года)", 7)
    assert years == [2015, 2018, 2019, 2020, 2021, 2022, 2023]


def test_parse_year_labels_range_even_spread():
    years = parse_year_labels("2000/01-2018/19 (19 учебных лет)", 19)
    assert years[0] == 2000
    assert years[-1] == 2018
    assert len(years) == 19


def test_parse_year_labels_range_single_point():
    years = parse_year_labels("2000/01-2018/19", 1)
    assert years == [2018]


def test_parse_year_labels_no_match():
    assert parse_year_labels("что-то без годов", 3) == []
