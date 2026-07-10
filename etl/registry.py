"""Канонический реестр территорий Беларуси и таблицы гармонизации названий.

Все соответствия выверены вручную:
- 118 районов: латинка pop-stat -> shapeName geoBoundaries, русское название,
  центр района (белорусское кириллическое написание из таблицы pop-stat);
- 12 городов областного подчинения -> район, на территории которого они лежат;
- флаг принадлежности Западной Беларуси (Польша, 1921-1939) для построения
  исторической границы по Рижскому договору (агрегация по современным районам).
"""

OBLASTS = {
    # id: (name_ru, name_be, popstat be-name)
    "BY-BR": ("Брестская область", "Брэсцкая вобласць", "Брэсцкая"),
    "BY-VI": ("Витебская область", "Віцебская вобласць", "Віцебская"),
    "BY-HO": ("Гомельская область", "Гомельская вобласць", "Гомельская"),
    "BY-HR": ("Гродненская область", "Гродзенская вобласць", "Гродзенская"),
    "BY-MI": ("Минская область", "Мінская вобласць", "Мінская"),
    "BY-MA": ("Могилёвская область", "Магілёўская вобласць", "Магілёўская"),
}
MINSK_CITY = "BY-HM"
COUNTRY = "BY"

# ISO-код области -> shapeISO в geoBoundaries ADM1
OBLAST_GEO_ISO = {
    "BY-BR": "BY-BR", "BY-VI": "BY-VI", "BY-HO": "BY-HO",
    "BY-HR": "BY-HR", "BY-MI": "BY-MI", "BY-MA": "BY-MA", "BY-HM": "BY-HM",
}

# Латинка pop-stat -> (русское название района, shapeName geoBoundaries ADM2,
#                      центр района по-белорусски как в таблице городов pop-stat)
# geo=None: полигон отсутствует в geoBoundaries (Дрибинский; берётся из OSM).
RAIONS = {
    # Брестская область (16)
    "Baranavicki":      ("Барановичский",    "Baranovichy",     "Баранавічы"),
    "Brescki":          ("Брестский",        "Brest",           "Брэст"),
    "Biarozaŭski":      ("Березовский",      "Byaroza",         "Бяроза"),
    "Hancavicki":       ("Ганцевичский",     "Hantsavichy",     "Ганцавічы"),
    "Drahičynski":      ("Дрогичинский",     "Drahichyn",       "Драгічын"),
    "Žabinkaŭski":      ("Жабинковский",     "Zhabinka",        "Жабінка"),
    "Ivanaŭski":        ("Ивановский",       "Ivanava",         "Іванава"),
    "Ivacevicki":       ("Ивацевичский",     "Ivatsevichy",     "Івацэвічы"),
    "Kamianiecki":      ("Каменецкий",       "Kamenets",        "Камянец"),
    "Kobrynski":        ("Кобринский",       "Kobryn",          "Кобрын"),
    "Łuniniecki":       ("Лунинецкий",       "Luninets",        "Лунінец"),
    "Lachavicki":       ("Ляховичский",      "Lyakhavichy",     "Ляхавічы"),
    "Małarycki":        ("Малоритский",      "Malaryta",        "Маларыта"),
    "Pinski":           ("Пинский",          "Pinsk",           "Пінск"),
    "Pružanski":        ("Пружанский",       "Pruzhany",        "Пружаны"),
    "Stolinski":        ("Столинский",       "Stolin",          "Столін"),
    # Витебская область (21)
    "Aršanski":         ("Оршанский",        "Orsha",           "Орша"),
    "Biešankovicki":    ("Бешенковичский",   "Beshankovichy",   "Бешанковічы"),
    "Brasłaŭski":       ("Браславский",      "Braslaw",         "Браслаў"),
    "Vierchniadzvinski":("Верхнедвинский",   "Verkhnyadzvinsk", "Верхнядзвінск"),
    "Viciebski":        ("Витебский",        "Vitebsk",         "Віцебск"),
    "Haradocki":        ("Городокский",      "Haradok",         "Гарадок"),
    "Hłybocki":         ("Глубокский",       "Hlybokaye",       "Глыбокае"),
    "Dokšycki":         ("Докшицкий",        "Dokshytsy",       "Докшыцы"),
    "Dubrovienski":     ("Дубровенский",     "Dubrowna",        "Дуброўна"),
    "Loznienski":       ("Лиозненский",      "Liozna",          "Лёзна"),
    "Lepielski":        ("Лепельский",       "Lyepyel",         "Лепель"),
    "Mijorski":         ("Миорский",         "Miory",           "Міёры"),
    "Pastaŭski":        ("Поставский",       "Pastavy",         "Паставы"),
    "Połacki":          ("Полоцкий",         "Polotsk",         "Полацк"),
    "Rasonski":         ("Россонский",       "Rasony",          "Расоны"),
    "Siennienski":      ("Сенненский",       "Syanno",          "Сянно"),
    "Tałačynski":       ("Толочинский",      "Talachyn",        "Талачын"),
    "Ušacki":           ("Ушачский",         "Ushachy",         "Ушачы"),
    "Čašnicki":         ("Чашникский",       "Chashniki",       "Чашнікі"),
    "Šarkoŭščynski":    ("Шарковщинский",    "Sharkawshchyna",  "Шаркоўшчына"),
    "Šumilinski":       ("Шумилинский",      "Shumilina",       "Шуміліна"),
    # Гомельская область (21)
    "Akciabrski":       ("Октябрьский",      "Akciabrski",      "Акцябрскі"),
    "Brahinski":        ("Брагинский",       "Brahin",          "Брагін"),
    "Buda-Kašaloŭski":  ("Буда-Кошелёвский", "Buda-Kashalyova", "Буда-Кашалёва"),
    "Vietkaŭski":       ("Ветковский",       "Vietka",          "Ветка"),
    "Homielski":        ("Гомельский",       "Gomel",           "Гомель"),
    "Dobrušski":        ("Добрушский",       "Dobrush",         "Добруш"),
    "Jelski":           ("Ельский",          "Yelʹsk",          "Ельск"),
    "Žłobinski":        ("Жлобинский",       "Zhlobin",         "Жлобін"),
    "Žytkavicki":       ("Житковичский",     "Zhytkavichy",     "Жыткавічы"),
    "Kalinkavicki":     ("Калинковичский",   "Kalinkavichy",    "Калінкавічы"),
    "Karmianski":       ("Кормянский",       "Karma",           "Карма"),
    "Lelčycki":         ("Лельчицкий",       "Lyelchytsy",      "Лельчыцы"),
    "Łojeŭski":         ("Лоевский",         "Loyew",           "Лоеў"),
    "Mazyrski":         ("Мозырский",        "Mazyr",           "Мазыр"),
    "Naraŭlanski":      ("Наровлянский",     "Naroulia",        "Нароўля"),
    "Pietrykaŭski":     ("Петриковский",     "Pyetrykaw",       "Петрыкаў"),
    "Rahačoŭski":       ("Рогачёвский",      "Rahachow",        "Рагачоў"),
    "Rečycki":          ("Речицкий",         "Rechytsa",        "Рэчыца"),
    "Svietłahorski":    ("Светлогорский",    "Svietlahorsk",    "Светлагорск"),
    "Chojnicki":        ("Хойникский",       "Khoiniki",        "Хойнікі"),
    "Čačerski":         ("Чечерский",        "Chachersk",       "Чачэрск"),
    # Гродненская область (17)
    "Astraviecki":      ("Островецкий",      "Astravyets",      "Астравец"),
    "Ašmianski":        ("Ошмянский",        "Ashmyany",        "Ашмяны"),
    "Bierastavicki":    ("Берестовицкий",    "Byerastavitsa",   "Вялікая Бераставіца"),
    "Vaŭkavyski":       ("Волковысский",     "Vawkavysk",       "Ваўкавыск"),
    "Voranaŭski":       ("Вороновский",      "Voranava",        "Воранава"),
    "Hrodzienski":      ("Гродненский",      "Grodno",          "Гродна"),
    "Dziatłaŭski":      ("Дятловский",       "Dzyatlava",       "Дзятлава"),
    "Zelvienski":       ("Зельвенский",      "Zel'va",          "Зэльва"),
    "Iŭjeŭski":         ("Ивьевский",        "Iwye",            "Іўе"),
    "Karelicki":        ("Кореличский",      "Karelichy",       "Карэлічы"),
    "Lidski":           ("Лидский",          "Lida",            "Ліда"),
    "Mastoŭski":        ("Мостовский",       "Masty",           "Масты"),
    "Navahrudski":      ("Новогрудский",     "Novogrudok",      "Навагрудак"),
    "Svisłacki":        ("Свислочский",      "Svislach",        "Свіслач"),
    "Słonimski":        ("Слонимский",       "Slonim",          "Слонім"),
    "Smarhonski":       ("Сморгонский",      "Smarhon",         "Смаргонь"),
    "Ščučynski":        ("Щучинский",        "Shchuchyn",       "Шчучын"),
    # Минская область (22)
    "Barysaŭski":       ("Борисовский",      "Barysaw",         "Барысаў"),
    "Biarezinski":      ("Березинский",      "Byerazino",       "Беразіно"),
    "Vałožynski":       ("Воложинский",      "Valozhyn",        "Валожын"),
    "Vilejski":         ("Вилейский",        "Vileyka",         "Вілейка"),
    "Dziaržynski":      ("Дзержинский",      "Dzyarzhynsk",     "Дзяржынск"),
    "Kapylski":         ("Копыльский",       "Kapyl",           "Капыль"),
    "Klecki":           ("Клецкий",          "Kletsk",          "Клецк"),
    "Krupski":          ("Крупский",         "Krupki",          "Крупкі"),
    "Łahojski":         ("Логойский",        "Lahoysk",         "Лагойск"),
    "Lubanski":         ("Любанский",        "Lyuban",          "Любань"),
    "Maładziečanski":   ("Молодечненский",   "Maladzyechna",    "Маладзечна"),
    "Minski":           ("Минский",          "Minsk",           None),  # центр - Минск, вне района
    "Miadzielski":      ("Мядельский",       "Myadzyel",        "Мядзель"),
    "Niasvižski":       ("Несвижский",       "Nyasvizh",        "Нясвіж"),
    "Puchavicki":       ("Пуховичский",      "Puchavičy",       "Мар'іна Горка"),
    "Salihorski":       ("Солигорский",      "Salihorsk",       "Салігорск"),
    "Słucki":           ("Слуцкий",          "Slutsk",          "Слуцк"),
    "Smalavicki":       ("Смолевичский",     "Smalyavichy",     "Смалявічы"),
    "Staradarožski":    ("Стародорожский",   "Staryya Darohi",  "Старыя Дарогі"),
    "Staŭbcoŭski":      ("Столбцовский",     "Stowbtsy",        "Стоўбцы"),
    "Uzdzienski":       ("Узденский",        "Uzda",            "Узда"),
    "Červieński":       ("Червенский",       "Chervyen",        "Чэрвень"),
    # Могилёвская область (21)
    "Asipovicki":       ("Осиповичский",     "Asipovichy",      "Асіповічы"),
    "Babrujski":        ("Бобруйский",       "Babruysk",        "Бабруйск"),
    "Bychaŭski":        ("Быховский",        "Bykhaw",          "Быхаў"),
    "Białynicki":       ("Белыничский",      "Byalynichy",      "Бялынічы"),
    "Hłuski":           ("Глусский",         "Hlusk",           "Глуск"),
    "Horacki":          ("Горецкий",         "Horki",           "Горкі"),
    "Drybinski":        ("Дрибинский",       None,              "Дрыбін"),
    "Kasciukovicki":    ("Костюковичский",   "Kastsyukovichy",  "Касцюковічы"),
    "Kiraŭski":         ("Кировский",        "Kirawsk",         "Кіраўск"),
    "Klimavicki":       ("Климовичский",     "Klimavichy",      "Клімавічы"),
    "Kličaŭski":        ("Кличевский",       "Klichaw",         "Клічаў"),
    "Krasnapolski":     ("Краснопольский",   "Krasnapolle",     "Краснаполле"),
    "Kruhlanski":       ("Круглянский",      "Kruhlaye",        "Круглае"),
    "Kryčaŭski":        ("Кричевский",       "Krychaw",         "Крычаў"),
    "Mahiloŭski":       ("Могилёвский",      "Mogilev",         "Магілёў"),
    "Mscisłaŭski":      ("Мстиславский",     "Mstsislaw",       "Мсціслаў"),
    "Słaŭharadski":     ("Славгородский",    "Slawharad",       "Слаўгарад"),
    "Chocimski":        ("Хотимский",        "Khotsimsk",       "Хоцімск"),
    "Čavuski":          ("Чаусский",         "Chavusy",         "Чавусы"),
    "Čerykaŭski":       ("Чериковский",      "Cherykaw",        "Чэрыкаў"),
    "Škłoŭski":         ("Шкловский",        "Shklow",          "Шклоў"),
}

# Города областного подчинения (строки "г. X" в таблице районов pop-stat):
# белорусское название -> латинка района, внутри которого лежит город.
# Их население НЕ входит в административный итог района; для полигона района
# на карте оно прибавляется (см. METHODOLOGY.md).
OBLAST_CITIES_HOST = {
    "Баранавічы": "Baranavicki",
    "Брэст": "Brescki",
    "Пінск": "Pinski",
    "Віцебск": "Viciebski",
    "Наваполацк": "Połacki",
    "Орша": "Aršanski",
    "Полацк": "Połacki",
    "Гомель": "Homielski",
    "Гродна": "Hrodzienski",
    "Бабруйск": "Babrujski",
    "Магілёў": "Mahiloŭski",
    "Жодзіна": "Smalavicki",
}

# Областные центры (белорусские названия городов) и "большая семёрка" городов.
OBLAST_CENTERS = {"Мінск", "Брэст", "Віцебск", "Гомель", "Гродна", "Магілёў"}
TOP7_CITIES = {"Мінск", "Гомель", "Магілёў", "Віцебск", "Гродна", "Брэст", "Бабруйск"}

# Районы, территория которых в 1921-1939 гг. входила в состав Польши
# (Западная Беларусь). Граница агрегирована по современным районам.
WEST_1921 = {
    # Брестская область - целиком
    "Baranavicki", "Brescki", "Biarozaŭski", "Hancavicki", "Drahičynski",
    "Žabinkaŭski", "Ivanaŭski", "Ivacevicki", "Kamianiecki", "Kobrynski",
    "Łuniniecki", "Lachavicki", "Małarycki", "Pinski", "Pružanski", "Stolinski",
    # Гродненская область - целиком
    "Astraviecki", "Ašmianski", "Bierastavicki", "Vaŭkavyski", "Voranaŭski",
    "Hrodzienski", "Dziatłaŭski", "Zelvienski", "Iŭjeŭski", "Karelicki",
    "Lidski", "Mastoŭski", "Navahrudski", "Svisłacki", "Słonimski",
    "Smarhonski", "Ščučynski",
    # Запад Минской области
    "Vilejski", "Vałožynski", "Klecki", "Maładziečanski", "Miadzielski",
    "Niasvižski", "Staŭbcoŭski",
    # Северо-запад Витебской области
    "Brasłaŭski", "Mijorski", "Šarkoŭščynski", "Hłybocki", "Pastaŭski",
    "Dokšycki",
}

# 1959 (демоскоп): районы Молодечненской области -> современная область.
# Упразднённые районы отнесены к области района-преемника.
MOLODECHNO_1959 = {
    "Браславский": "BY-VI", "Видзовский": "BY-VI", "Шарковщинский": "BY-VI",
    "Дисненский": "BY-VI", "Плисский": "BY-VI", "Глубокский": "BY-VI",
    "Докшицкий": "BY-VI", "Дуниловичский": "BY-VI", "Поставский": "BY-VI",
    "Миорский": "BY-VI",
    "Вилейский": "BY-MI", "Молодечненский": "BY-MI", "Мядельский": "BY-MI",
    "Кривичский": "BY-MI", "Ильянский": "BY-MI", "Радошковичский": "BY-MI",
    "Воложинский": "BY-MI",
    "Юратишковский": "BY-HR", "Ивьевский": "BY-HR", "Ошмянский": "BY-HR",
    "Островецкий": "BY-HR", "Сморгонский": "BY-HR",
}


# Координаты городов, отсутствующих в выгрузке Wikidata под официальным
# белорусским написанием (расхождения с тарашкевицей и т.п.).
COORD_OVERRIDES = {
    "Камянец": (23.8163, 52.4022),
    "Міёры": (27.6293, 55.6255),
    "Шаркоўшчына": (27.4670, 55.3690),
    "Мядзель": (26.9387, 54.8760),
}


def raion_id(lat_name: str) -> str:
    """Стабильный id района из латинки pop-stat: 'Baranavicki' -> 'r-baranavicki'."""
    s = lat_name.lower()
    for a, b in [("š", "sh"), ("č", "ch"), ("ž", "zh"), ("ŭ", "u"), ("ł", "l"),
                 ("ń", "n"), ("ś", "s"), ("ć", "c"), ("ó", "o"), ("’", ""), ("'", "")]:
        s = s.replace(a, b)
    return "r-" + s.replace(" ", "-")


def city_id(lat_name: str) -> str:
    s = lat_name.lower()
    for a, b in [("š", "sh"), ("č", "ch"), ("ž", "zh"), ("ŭ", "u"), ("ł", "l"),
                 ("ń", "n"), ("ś", "s"), ("ć", "c"), ("ó", "o"), ("’", ""), ("'", "")]:
        s = s.replace(a, b)
    return "c-" + s.replace(" ", "-")
