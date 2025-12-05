"""
Seed script for adding new countries, regions, currencies, markets, and neighbors.
Run this script to add 69 new countries to the game.

IMPORTANT: This script ONLY adds new countries. It will NOT modify:
- Existing countries (USA, Canada, Mexico)
- Their regions, markets, governments, wars, battles, etc.
"""

from app import create_app, db
from app.models import Country, Region, Resource, CountryMarketItem, GoldMarket
from slugify import slugify
from decimal import Decimal
import sys

# Fix console encoding for Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Countries that already exist in the database - DO NOT TOUCH
EXISTING_COUNTRIES = ["United States", "Mexico", "Canada"]

# All NEW countries data: (name, flag_code, currency_code, [regions])
COUNTRIES_DATA = [
    # EUROPE
    ("United Kingdom", "gb", "GBP", [
        "Greater London",
        "South England",
        "Midlands",
        "North England",
        "Scotland",
        "Wales & Northern Ireland"
    ]),
    ("Germany", "de", "DEM", [
        "Bavaria",
        "Baden-Württemberg",
        "North Rhine-Westphalia",
        "Berlin & Brandenburg",
        "Lower Saxony & Hamburg",
        "Saxony & Thuringia"
    ]),
    ("France", "fr", "FRF", [
        "Île-de-France",
        "Provence-Côte d'Azur",
        "Auvergne-Rhône-Alpes",
        "Nouvelle-Aquitaine",
        "Occitanie",
        "Hauts-de-France & Normandy"
    ]),
    ("Italy", "it", "ITL", [
        "Lombardy",
        "Lazio",
        "Veneto",
        "Piedmont & Liguria",
        "Tuscany & Emilia-Romagna",
        "Southern Italy & Sicily"
    ]),
    ("Spain", "es", "ESP", [
        "Madrid",
        "Catalonia",
        "Andalusia",
        "Valencia",
        "Basque Country & Navarra",
        "Galicia & Castile"
    ]),
    ("Portugal", "pt", "PTE", [
        "Lisbon",
        "Porto & Norte",
        "Algarve",
        "Central Portugal"
    ]),
    ("Netherlands", "nl", "NLG", [
        "North Holland",
        "South Holland",
        "Brabant & Limburg",
        "Eastern Netherlands"
    ]),
    ("Belgium", "be", "BEF", [
        "Brussels",
        "Flanders",
        "Wallonia"
    ]),
    ("Switzerland", "ch", "CHF", [
        "Zurich & Northeast",
        "Bern & Central",
        "Geneva & Romandy",
        "Ticino & Alps"
    ]),
    ("Austria", "at", "ATS", [
        "Vienna",
        "Upper & Lower Austria",
        "Tyrol & Vorarlberg",
        "Styria & Carinthia"
    ]),
    ("Poland", "pl", "PLN", [
        "Masovia",
        "Lesser Poland",
        "Greater Poland",
        "Silesia",
        "Pomerania"
    ]),
    ("Czech Republic", "cz", "CZK", [
        "Bohemia",
        "Moravia",
        "Czech Silesia"
    ]),
    ("Slovakia", "sk", "SKK", [
        "Bratislava",
        "Central Slovakia",
        "Eastern Slovakia"
    ]),
    ("Hungary", "hu", "HUF", [
        "Budapest",
        "Western Transdanubia",
        "Southern Hungary",
        "Eastern Hungary"
    ]),
    ("Romania", "ro", "RON", [
        "Bucharest & Wallachia",
        "Transylvania",
        "Moldova",
        "Banat & Crișana",
        "Dobrogea & Black Sea"
    ]),
    ("Bulgaria", "bg", "BGN", [
        "Sofia",
        "Plovdiv & Thrace",
        "Varna & Black Sea",
        "Northern Bulgaria"
    ]),
    ("Greece", "gr", "GRD", [
        "Attica",
        "Central Macedonia",
        "Peloponnese",
        "Crete",
        "Aegean Islands"
    ]),
    ("Serbia", "rs", "RSD", [
        "Belgrade",
        "Vojvodina",
        "Šumadija & Western Serbia",
        "Southern Serbia",
        "Kosovo and Metohija"
    ]),
    ("Croatia", "hr", "HRK", [
        "Zagreb",
        "Dalmatia",
        "Slavonia",
        "Istria & Kvarner"
    ]),
    ("Slovenia", "si", "SIT", [
        "Ljubljana",
        "Maribor & Styria",
        "Coastal Slovenia"
    ]),
    ("Bosnia and Herzegovina", "ba", "BAM", [
        "Sarajevo",
        "Republika Srpska",
        "Herzegovina",
        "Brčko District"
    ]),
    ("Montenegro", "me", "EUR", [
        "Podgorica",
        "Coastal Montenegro",
        "Northern Montenegro"
    ]),
    ("North Macedonia", "mk", "MKD", [
        "Skopje",
        "Western Macedonia",
        "Eastern Macedonia"
    ]),
    ("Albania", "al", "ALL", [
        "Tirana",
        "Southern Albania",
        "Northern Albania",
        "Central Albania & Coast"
    ]),
    ("Ukraine", "ua", "UAH", [
        "Kyiv",
        "Western Ukraine",
        "Southern Ukraine",
        "Eastern Ukraine",
        "Donbas",
        "Crimea",
        "Central Ukraine"
    ]),
    ("Belarus", "by", "BYN", [
        "Minsk",
        "Brest Region",
        "Grodno Region",
        "Gomel Region",
        "Vitebsk & Mogilev"
    ]),
    ("Moldova", "md", "MDL", [
        "Chișinău",
        "Transnistria",
        "Gagauzia & Southern Moldova"
    ]),
    ("Lithuania", "lt", "LTL", [
        "Vilnius",
        "Kaunas Region",
        "Klaipėda & Coast"
    ]),
    ("Latvia", "lv", "LVL", [
        "Riga",
        "Kurzeme",
        "Latgale"
    ]),
    ("Estonia", "ee", "EEK", [
        "Tallinn",
        "Tartu",
        "Western Estonia"
    ]),
    ("Finland", "fi", "FIM", [
        "Helsinki & Uusimaa",
        "Tampere & Pirkanmaa",
        "Turku & Southwest",
        "Eastern Finland",
        "Lapland & North"
    ]),
    ("Sweden", "se", "SEK", [
        "Stockholm",
        "Gothenburg & West",
        "Malmö & Skåne",
        "Central Sweden",
        "Norrland"
    ]),
    ("Norway", "no", "NOK", [
        "Oslo",
        "Bergen & West",
        "Trondheim & Central",
        "Stavanger & Southwest",
        "Northern Norway"
    ]),
    ("Denmark", "dk", "DKK", [
        "Copenhagen",
        "Jutland North",
        "Jutland South",
        "Bornholm & Islands"
    ]),
    ("Ireland", "ie", "IEP", [
        "Dublin",
        "Cork & Munster",
        "Galway & Connacht",
        "Ulster (Republic)"
    ]),
    ("Iceland", "is", "ISK", [
        "Reykjavik",
        "Northern Iceland",
        "Eastern & Southern Iceland"
    ]),

    # ASIA
    ("Russia", "ru", "RUB", [
        "Moscow",
        "Saint Petersburg",
        "Southern Russia",
        "Volga Region",
        "Ural",
        "Western Siberia",
        "Eastern Siberia",
        "Far East",
        "North Caucasus",
        "Arctic Russia"
    ]),
    ("China", "cn", "CNY", [
        "Beijing",
        "Shanghai",
        "Guangdong",
        "Sichuan",
        "Zhejiang & Jiangsu",
        "Shandong",
        "Hubei",
        "Xinjiang",
        "Tibet",
        "Manchuria"
    ]),
    ("Japan", "jp", "JPY", [
        "Tokyo",
        "Osaka & Kansai",
        "Nagoya & Chubu",
        "Kyushu",
        "Hokkaido",
        "Tohoku"
    ]),
    ("South Korea", "kr", "KRW", [
        "Seoul",
        "Busan",
        "Incheon & Gyeonggi",
        "Daegu & Gyeongsang",
        "Daejeon & Chungcheong"
    ]),

    # MIDDLE EAST
    ("Israel", "il", "ILS", [
        "Tel Aviv",
        "Jerusalem",
        "Haifa & North",
        "Negev & South"
    ]),
    ("Georgia", "ge", "GEL", [
        "Tbilisi",
        "Batumi & Adjara",
        "Kutaisi & Imereti",
        "Eastern Georgia"
    ]),
    ("United Arab Emirates", "ae", "AED", [
        "Dubai",
        "Abu Dhabi",
        "Sharjah & Northern Emirates",
        "Eastern Emirates"
    ]),
    ("Saudi Arabia", "sa", "SAR", [
        "Riyadh",
        "Jeddah & Mecca",
        "Eastern Province",
        "Medina",
        "Asir & South",
        "Tabuk & Northern Borders"
    ]),
    ("Qatar", "qa", "QAR", [
        "Doha",
        "Al Wakrah & South",
        "Al Khor & North"
    ]),
    ("Kuwait", "kw", "KWD", [
        "Kuwait City",
        "Ahmadi",
        "Jahra"
    ]),
    ("Bahrain", "bh", "BHD", [
        "Manama",
        "Muharraq & Southern Bahrain"
    ]),
    ("Oman", "om", "OMR", [
        "Muscat",
        "Dhofar",
        "Al Batinah",
        "Al Dakhiliyah"
    ]),
    ("Turkey", "tr", "TRY", [
        "Istanbul",
        "Ankara",
        "Izmir & Aegean",
        "Antalya & Mediterranean",
        "Eastern Anatolia",
        "Black Sea Region",
        "Central Anatolia"
    ]),
    ("Iran", "ir", "IRR", [
        "Tehran",
        "Isfahan",
        "Mashhad & Khorasan",
        "Shiraz & Fars",
        "Tabriz & Azerbaijan",
        "Khuzestan"
    ]),

    # SOUTH AMERICA
    ("Brazil", "br", "BRL", [
        "São Paulo",
        "Rio de Janeiro",
        "Brasília",
        "Minas Gerais",
        "Bahia & Northeast",
        "Rio Grande do Sul",
        "Amazonas",
        "Paraná & Santa Catarina"
    ]),
    ("Argentina", "ar", "ARS", [
        "Buenos Aires",
        "Córdoba",
        "Mendoza",
        "Patagonia",
        "Rosario & Santa Fe",
        "Tucumán & Northwest"
    ]),
    ("Colombia", "co", "COP", [
        "Bogotá",
        "Medellín & Antioquia",
        "Cali & Valle del Cauca",
        "Colombian Caribbean",
        "Coffee Region"
    ]),
    ("Chile", "cl", "CLP", [
        "Santiago",
        "Valparaíso",
        "Concepción & Biobío",
        "Atacama & Norte Grande",
        "Patagonia & Magallanes"
    ]),
    ("Peru", "pe", "PEN", [
        "Lima",
        "Cusco & Highlands",
        "Arequipa",
        "Trujillo & North Coast",
        "Amazonia"
    ]),
    ("Venezuela", "ve", "VES", [
        "Caracas",
        "Maracaibo & Zulia",
        "Valencia & Central",
        "Barquisimeto & Lara",
        "Guayana"
    ]),
    ("Ecuador", "ec", "USD", [
        "Quito",
        "Guayaquil",
        "Cuenca & Southern Highlands",
        "Amazonia & Galápagos"
    ]),
    ("Uruguay", "uy", "UYU", [
        "Montevideo",
        "Punta del Este & Southeast",
        "Interior"
    ]),
    ("Paraguay", "py", "PYG", [
        "Asunción",
        "Ciudad del Este",
        "Chaco"
    ]),
    ("Bolivia", "bo", "BOB", [
        "La Paz",
        "Santa Cruz",
        "Cochabamba",
        "Sucre & Potosí"
    ]),

    # CENTRAL AMERICA & CARIBBEAN
    ("Panama", "pa", "PAB", [
        "Panama City",
        "Colón",
        "Western Panama"
    ]),
    ("Costa Rica", "cr", "CRC", [
        "San José",
        "Costa Rican Caribbean",
        "Costa Rican Pacific"
    ]),
    ("Guatemala", "gt", "GTQ", [
        "Guatemala City",
        "Quetzaltenango",
        "Petén",
        "Pacific Lowlands"
    ]),
    ("Honduras", "hn", "HNL", [
        "Tegucigalpa",
        "San Pedro Sula",
        "Honduran Caribbean"
    ]),
    ("El Salvador", "sv", "USD", [
        "San Salvador",
        "Santa Ana",
        "San Miguel"
    ]),
    ("Nicaragua", "ni", "NIO", [
        "Managua",
        "León & Pacific",
        "Nicaraguan Caribbean"
    ]),
    ("Dominican Republic", "do", "DOP", [
        "Santo Domingo",
        "Santiago de los Caballeros",
        "Punta Cana & East",
        "Puerto Plata & North Coast"
    ]),

    # AFRICA
    ("Egypt", "eg", "EGP", [
        "Cairo",
        "Alexandria",
        "Luxor & Upper Egypt",
        "Suez & Canal Zone",
        "Sinai Peninsula"
    ]),
    ("South Africa", "za", "ZAR", [
        "Johannesburg & Gauteng",
        "Cape Town & Western Cape",
        "Durban & KwaZulu-Natal",
        "Pretoria",
        "Port Elizabeth & Eastern Cape"
    ]),
]

# Region neighbors mapping: region_name -> [list of neighbor region names]
# This includes both intra-country and inter-country neighbors
REGION_NEIGHBORS = {
    # UNITED KINGDOM
    "Greater London": ["South England", "Midlands"],
    "South England": ["Greater London", "Midlands", "Wales & Northern Ireland"],
    "Midlands": ["Greater London", "South England", "North England", "Wales & Northern Ireland"],
    "North England": ["Midlands", "Scotland", "Wales & Northern Ireland"],
    "Scotland": ["North England"],
    "Wales & Northern Ireland": ["South England", "Midlands", "North England", "Dublin"],  # Ireland connection

    # GERMANY
    "Bavaria": ["Baden-Württemberg", "Saxony & Thuringia", "Vienna"],  # Austria connection
    "Baden-Württemberg": ["Bavaria", "North Rhine-Westphalia", "Zurich & Northeast", "Île-de-France"],  # Swiss/French connections
    "North Rhine-Westphalia": ["Baden-Württemberg", "Lower Saxony & Hamburg", "Brussels", "North Holland"],  # Belgium/Netherlands connections
    "Berlin & Brandenburg": ["Lower Saxony & Hamburg", "Saxony & Thuringia", "Masovia"],  # Poland connection
    "Lower Saxony & Hamburg": ["North Rhine-Westphalia", "Berlin & Brandenburg", "Saxony & Thuringia", "Copenhagen"],  # Denmark connection
    "Saxony & Thuringia": ["Bavaria", "Berlin & Brandenburg", "Lower Saxony & Hamburg", "Bohemia"],  # Czech connection

    # FRANCE
    "Île-de-France": ["Hauts-de-France & Normandy", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Baden-Württemberg"],
    "Provence-Côte d'Azur": ["Auvergne-Rhône-Alpes", "Occitanie", "Piedmont & Liguria", "Geneva & Romandy"],  # Italy/Swiss connections
    "Auvergne-Rhône-Alpes": ["Île-de-France", "Provence-Côte d'Azur", "Occitanie", "Nouvelle-Aquitaine", "Geneva & Romandy"],
    "Nouvelle-Aquitaine": ["Île-de-France", "Auvergne-Rhône-Alpes", "Occitanie", "Basque Country & Navarra"],  # Spain connection
    "Occitanie": ["Provence-Côte d'Azur", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Catalonia"],  # Spain connection
    "Hauts-de-France & Normandy": ["Île-de-France", "Brussels", "South England"],  # Belgium/UK connections

    # ITALY
    "Lombardy": ["Piedmont & Liguria", "Veneto", "Tuscany & Emilia-Romagna", "Ticino & Alps"],  # Swiss connection
    "Lazio": ["Tuscany & Emilia-Romagna", "Southern Italy & Sicily"],
    "Veneto": ["Lombardy", "Tuscany & Emilia-Romagna", "Ljubljana"],  # Slovenia connection
    "Piedmont & Liguria": ["Lombardy", "Tuscany & Emilia-Romagna", "Provence-Côte d'Azur"],  # France connection
    "Tuscany & Emilia-Romagna": ["Lombardy", "Lazio", "Veneto", "Piedmont & Liguria"],
    "Southern Italy & Sicily": ["Lazio"],

    # SPAIN
    "Madrid": ["Catalonia", "Andalusia", "Valencia", "Galicia & Castile", "Basque Country & Navarra"],
    "Catalonia": ["Madrid", "Valencia", "Occitanie"],  # France connection
    "Andalusia": ["Madrid", "Valencia", "Algarve"],  # Portugal connection
    "Valencia": ["Madrid", "Catalonia", "Andalusia"],
    "Basque Country & Navarra": ["Madrid", "Galicia & Castile", "Nouvelle-Aquitaine"],  # France connection
    "Galicia & Castile": ["Madrid", "Basque Country & Navarra", "Porto & Norte"],  # Portugal connection

    # PORTUGAL
    "Lisbon": ["Porto & Norte", "Algarve", "Central Portugal"],
    "Porto & Norte": ["Lisbon", "Central Portugal", "Galicia & Castile"],  # Spain connection
    "Algarve": ["Lisbon", "Central Portugal", "Andalusia"],  # Spain connection
    "Central Portugal": ["Lisbon", "Porto & Norte", "Algarve"],

    # NETHERLANDS
    "North Holland": ["South Holland", "Eastern Netherlands", "North Rhine-Westphalia"],  # Germany connection
    "South Holland": ["North Holland", "Brabant & Limburg", "Eastern Netherlands"],
    "Brabant & Limburg": ["South Holland", "Eastern Netherlands", "Brussels", "North Rhine-Westphalia"],  # Belgium/Germany
    "Eastern Netherlands": ["North Holland", "South Holland", "Brabant & Limburg", "Lower Saxony & Hamburg"],  # Germany

    # BELGIUM
    "Brussels": ["Flanders", "Wallonia", "North Rhine-Westphalia", "Hauts-de-France & Normandy", "Brabant & Limburg"],
    "Flanders": ["Brussels", "Wallonia", "South Holland"],  # Netherlands connection
    "Wallonia": ["Brussels", "Flanders", "Hauts-de-France & Normandy"],  # France connection

    # SWITZERLAND
    "Zurich & Northeast": ["Bern & Central", "Ticino & Alps", "Baden-Württemberg"],  # Germany connection
    "Bern & Central": ["Zurich & Northeast", "Geneva & Romandy", "Ticino & Alps"],
    "Geneva & Romandy": ["Bern & Central", "Ticino & Alps", "Auvergne-Rhône-Alpes", "Provence-Côte d'Azur"],  # France
    "Ticino & Alps": ["Zurich & Northeast", "Bern & Central", "Geneva & Romandy", "Lombardy"],  # Italy connection

    # AUSTRIA
    "Vienna": ["Upper & Lower Austria", "Styria & Carinthia", "Bratislava", "Budapest", "Bavaria"],  # Slovakia/Hungary/Germany
    "Upper & Lower Austria": ["Vienna", "Tyrol & Vorarlberg", "Styria & Carinthia", "Bohemia"],  # Czech connection
    "Tyrol & Vorarlberg": ["Upper & Lower Austria", "Styria & Carinthia", "Bavaria", "Ticino & Alps"],  # Germany/Swiss
    "Styria & Carinthia": ["Vienna", "Upper & Lower Austria", "Tyrol & Vorarlberg", "Ljubljana", "Budapest"],  # Slovenia/Hungary

    # POLAND
    "Masovia": ["Lesser Poland", "Greater Poland", "Silesia", "Pomerania", "Berlin & Brandenburg", "Minsk"],  # Germany/Belarus
    "Lesser Poland": ["Masovia", "Silesia", "Eastern Slovakia", "Western Ukraine"],  # Slovakia/Ukraine
    "Greater Poland": ["Masovia", "Silesia", "Pomerania"],
    "Silesia": ["Masovia", "Lesser Poland", "Greater Poland", "Bohemia", "Moravia"],  # Czech connection
    "Pomerania": ["Masovia", "Greater Poland", "Berlin & Brandenburg"],  # Germany connection

    # CZECH REPUBLIC
    "Bohemia": ["Moravia", "Czech Silesia", "Saxony & Thuringia", "Bavaria", "Upper & Lower Austria"],  # Germany/Austria
    "Moravia": ["Bohemia", "Czech Silesia", "Bratislava", "Upper & Lower Austria"],  # Slovakia/Austria
    "Czech Silesia": ["Bohemia", "Moravia", "Silesia"],  # Poland Silesia connection

    # SLOVAKIA
    "Bratislava": ["Central Slovakia", "Vienna", "Moravia", "Budapest"],  # Austria/Czech/Hungary
    "Central Slovakia": ["Bratislava", "Eastern Slovakia", "Budapest"],  # Hungary connection
    "Eastern Slovakia": ["Central Slovakia", "Lesser Poland", "Western Ukraine"],  # Poland/Ukraine

    # HUNGARY
    "Budapest": ["Western Transdanubia", "Southern Hungary", "Eastern Hungary", "Vienna", "Bratislava", "Styria & Carinthia", "Zagreb"],
    "Western Transdanubia": ["Budapest", "Southern Hungary", "Styria & Carinthia", "Zagreb"],  # Austria/Croatia
    "Southern Hungary": ["Budapest", "Western Transdanubia", "Eastern Hungary", "Vojvodina", "Zagreb"],  # Serbia/Croatia
    "Eastern Hungary": ["Budapest", "Southern Hungary", "Transylvania"],  # Romania connection

    # ROMANIA
    "Bucharest & Wallachia": ["Transylvania", "Moldova", "Dobrogea & Black Sea", "Northern Bulgaria"],  # Bulgaria
    "Transylvania": ["Bucharest & Wallachia", "Moldova", "Banat & Crișana", "Eastern Hungary"],  # Hungary
    "Moldova": ["Bucharest & Wallachia", "Transylvania", "Banat & Crișana", "Dobrogea & Black Sea", "Chișinău"],  # Moldova country
    "Banat & Crișana": ["Transylvania", "Moldova", "Vojvodina"],  # Serbia connection
    "Dobrogea & Black Sea": ["Bucharest & Wallachia", "Moldova", "Varna & Black Sea"],  # Bulgaria connection

    # BULGARIA
    "Sofia": ["Plovdiv & Thrace", "Northern Bulgaria", "Skopje", "Belgrade"],  # N.Macedonia/Serbia
    "Plovdiv & Thrace": ["Sofia", "Varna & Black Sea", "Northern Bulgaria", "Istanbul"],  # Turkey connection
    "Varna & Black Sea": ["Plovdiv & Thrace", "Northern Bulgaria", "Dobrogea & Black Sea"],  # Romania
    "Northern Bulgaria": ["Sofia", "Plovdiv & Thrace", "Varna & Black Sea", "Bucharest & Wallachia"],  # Romania

    # GREECE
    "Attica": ["Central Macedonia", "Peloponnese", "Aegean Islands"],
    "Central Macedonia": ["Attica", "Skopje", "Sofia", "Istanbul"],  # N.Macedonia/Bulgaria/Turkey
    "Peloponnese": ["Attica", "Crete"],
    "Crete": ["Peloponnese", "Aegean Islands"],
    "Aegean Islands": ["Attica", "Crete", "Izmir & Aegean"],  # Turkey connection

    # SERBIA
    "Belgrade": ["Vojvodina", "Šumadija & Western Serbia", "Southern Serbia", "Sofia", "Zagreb"],  # Bulgaria/Croatia
    "Vojvodina": ["Belgrade", "Southern Hungary", "Zagreb", "Banat & Crișana"],  # Hungary/Croatia/Romania
    "Šumadija & Western Serbia": ["Belgrade", "Southern Serbia", "Kosovo and Metohija", "Sarajevo", "Podgorica"],  # BiH/Montenegro
    "Southern Serbia": ["Belgrade", "Šumadija & Western Serbia", "Kosovo and Metohija", "Skopje"],  # N.Macedonia
    "Kosovo and Metohija": ["Šumadija & Western Serbia", "Southern Serbia", "Skopje", "Podgorica", "Tirana"],  # N.Macedonia/Montenegro/Albania

    # CROATIA
    "Zagreb": ["Dalmatia", "Slavonia", "Istria & Kvarner", "Ljubljana", "Budapest", "Belgrade", "Vojvodina"],
    "Dalmatia": ["Zagreb", "Slavonia", "Istria & Kvarner", "Herzegovina", "Coastal Montenegro"],  # BiH/Montenegro
    "Slavonia": ["Zagreb", "Dalmatia", "Vojvodina", "Republika Srpska"],  # Serbia/BiH
    "Istria & Kvarner": ["Zagreb", "Dalmatia", "Ljubljana", "Coastal Slovenia"],  # Slovenia

    # SLOVENIA
    "Ljubljana": ["Maribor & Styria", "Coastal Slovenia", "Zagreb", "Veneto", "Styria & Carinthia"],  # Croatia/Italy/Austria
    "Maribor & Styria": ["Ljubljana", "Coastal Slovenia", "Styria & Carinthia"],  # Austria connection
    "Coastal Slovenia": ["Ljubljana", "Maribor & Styria", "Istria & Kvarner"],  # Croatia connection

    # BOSNIA AND HERZEGOVINA
    "Sarajevo": ["Republika Srpska", "Herzegovina", "Šumadija & Western Serbia", "Dalmatia"],  # Serbia/Croatia
    "Republika Srpska": ["Sarajevo", "Herzegovina", "Brčko District", "Slavonia", "Belgrade"],  # Croatia/Serbia
    "Herzegovina": ["Sarajevo", "Republika Srpska", "Dalmatia", "Coastal Montenegro"],  # Croatia/Montenegro
    "Brčko District": ["Republika Srpska", "Slavonia"],  # Croatia connection

    # MONTENEGRO
    "Podgorica": ["Coastal Montenegro", "Northern Montenegro", "Šumadija & Western Serbia", "Kosovo and Metohija", "Tirana"],
    "Coastal Montenegro": ["Podgorica", "Northern Montenegro", "Dalmatia", "Herzegovina", "Northern Albania"],
    "Northern Montenegro": ["Podgorica", "Coastal Montenegro", "Kosovo and Metohija"],

    # NORTH MACEDONIA
    "Skopje": ["Western Macedonia", "Eastern Macedonia", "Kosovo and Metohija", "Southern Serbia", "Sofia", "Tirana"],
    "Western Macedonia": ["Skopje", "Eastern Macedonia", "Tirana", "Central Macedonia"],  # Albania/Greece
    "Eastern Macedonia": ["Skopje", "Western Macedonia", "Plovdiv & Thrace"],  # Bulgaria connection

    # ALBANIA
    "Tirana": ["Southern Albania", "Northern Albania", "Central Albania & Coast", "Kosovo and Metohija", "Podgorica", "Skopje", "Western Macedonia"],
    "Southern Albania": ["Tirana", "Central Albania & Coast", "Western Macedonia"],
    "Northern Albania": ["Tirana", "Central Albania & Coast", "Coastal Montenegro"],
    "Central Albania & Coast": ["Tirana", "Southern Albania", "Northern Albania"],

    # UKRAINE
    "Kyiv": ["Western Ukraine", "Southern Ukraine", "Eastern Ukraine", "Central Ukraine", "Gomel Region"],  # Belarus
    "Western Ukraine": ["Kyiv", "Central Ukraine", "Lesser Poland", "Eastern Slovakia", "Chișinău"],  # Poland/Slovakia/Moldova
    "Southern Ukraine": ["Kyiv", "Eastern Ukraine", "Central Ukraine", "Crimea", "Chișinău"],  # Moldova connection
    "Eastern Ukraine": ["Kyiv", "Southern Ukraine", "Donbas", "Central Ukraine", "Southern Russia"],  # Russia
    "Donbas": ["Eastern Ukraine", "Crimea", "Southern Russia"],  # Russia connection
    "Crimea": ["Southern Ukraine", "Donbas", "Southern Russia"],  # Russia connection
    "Central Ukraine": ["Kyiv", "Western Ukraine", "Southern Ukraine", "Eastern Ukraine"],

    # BELARUS
    "Minsk": ["Brest Region", "Grodno Region", "Gomel Region", "Vitebsk & Mogilev", "Masovia", "Vilnius"],  # Poland/Lithuania
    "Brest Region": ["Minsk", "Grodno Region", "Gomel Region", "Masovia"],  # Poland connection
    "Grodno Region": ["Minsk", "Brest Region", "Vitebsk & Mogilev", "Vilnius"],  # Lithuania connection
    "Gomel Region": ["Minsk", "Brest Region", "Vitebsk & Mogilev", "Kyiv"],  # Ukraine connection
    "Vitebsk & Mogilev": ["Minsk", "Grodno Region", "Gomel Region", "Moscow", "Saint Petersburg"],  # Russia

    # MOLDOVA
    "Chișinău": ["Transnistria", "Gagauzia & Southern Moldova", "Moldova", "Southern Ukraine", "Western Ukraine"],  # Romania/Ukraine
    "Transnistria": ["Chișinău", "Gagauzia & Southern Moldova", "Southern Ukraine"],  # Ukraine connection
    "Gagauzia & Southern Moldova": ["Chișinău", "Transnistria", "Dobrogea & Black Sea"],  # Romania connection

    # LITHUANIA
    "Vilnius": ["Kaunas Region", "Klaipėda & Coast", "Minsk", "Grodno Region", "Riga"],  # Belarus/Latvia
    "Kaunas Region": ["Vilnius", "Klaipėda & Coast"],
    "Klaipėda & Coast": ["Vilnius", "Kaunas Region", "Kurzeme"],  # Latvia connection

    # LATVIA
    "Riga": ["Kurzeme", "Latgale", "Vilnius", "Tallinn"],  # Lithuania/Estonia
    "Kurzeme": ["Riga", "Latgale", "Klaipėda & Coast"],  # Lithuania connection
    "Latgale": ["Riga", "Kurzeme", "Vitebsk & Mogilev"],  # Belarus connection

    # ESTONIA
    "Tallinn": ["Tartu", "Western Estonia", "Riga", "Saint Petersburg"],  # Latvia/Russia
    "Tartu": ["Tallinn", "Western Estonia"],
    "Western Estonia": ["Tallinn", "Tartu", "Helsinki & Uusimaa"],  # Finland connection (sea)

    # FINLAND
    "Helsinki & Uusimaa": ["Tampere & Pirkanmaa", "Turku & Southwest", "Eastern Finland", "Western Estonia", "Saint Petersburg"],  # Estonia/Russia
    "Tampere & Pirkanmaa": ["Helsinki & Uusimaa", "Turku & Southwest", "Eastern Finland", "Lapland & North"],
    "Turku & Southwest": ["Helsinki & Uusimaa", "Tampere & Pirkanmaa", "Stockholm"],  # Sweden connection (sea)
    "Eastern Finland": ["Helsinki & Uusimaa", "Tampere & Pirkanmaa", "Lapland & North", "Saint Petersburg"],  # Russia
    "Lapland & North": ["Tampere & Pirkanmaa", "Eastern Finland", "Northern Norway", "Norrland"],  # Norway/Sweden

    # SWEDEN
    "Stockholm": ["Gothenburg & West", "Malmö & Skåne", "Central Sweden", "Norrland", "Turku & Southwest", "Helsinki & Uusimaa"],  # Finland (sea)
    "Gothenburg & West": ["Stockholm", "Malmö & Skåne", "Central Sweden", "Oslo"],  # Norway connection
    "Malmö & Skåne": ["Stockholm", "Gothenburg & West", "Copenhagen"],  # Denmark connection
    "Central Sweden": ["Stockholm", "Gothenburg & West", "Norrland", "Trondheim & Central"],  # Norway
    "Norrland": ["Stockholm", "Central Sweden", "Lapland & North", "Northern Norway", "Trondheim & Central"],  # Finland/Norway

    # NORWAY
    "Oslo": ["Bergen & West", "Trondheim & Central", "Stavanger & Southwest", "Gothenburg & West"],  # Sweden
    "Bergen & West": ["Oslo", "Trondheim & Central", "Stavanger & Southwest"],
    "Trondheim & Central": ["Oslo", "Bergen & West", "Northern Norway", "Central Sweden", "Norrland"],  # Sweden
    "Stavanger & Southwest": ["Oslo", "Bergen & West"],
    "Northern Norway": ["Trondheim & Central", "Lapland & North", "Norrland", "Arctic Russia"],  # Finland/Sweden/Russia

    # DENMARK
    "Copenhagen": ["Jutland North", "Jutland South", "Malmö & Skåne", "Lower Saxony & Hamburg"],  # Sweden/Germany
    "Jutland North": ["Copenhagen", "Jutland South", "Bornholm & Islands"],
    "Jutland South": ["Copenhagen", "Jutland North", "Bornholm & Islands", "Lower Saxony & Hamburg"],  # Germany
    "Bornholm & Islands": ["Jutland North", "Jutland South"],

    # IRELAND
    "Dublin": ["Cork & Munster", "Galway & Connacht", "Ulster (Republic)", "Wales & Northern Ireland"],  # UK connection
    "Cork & Munster": ["Dublin", "Galway & Connacht", "Ulster (Republic)"],
    "Galway & Connacht": ["Dublin", "Cork & Munster", "Ulster (Republic)"],
    "Ulster (Republic)": ["Dublin", "Cork & Munster", "Galway & Connacht"],

    # ICELAND
    "Reykjavik": ["Northern Iceland", "Eastern & Southern Iceland"],
    "Northern Iceland": ["Reykjavik", "Eastern & Southern Iceland"],
    "Eastern & Southern Iceland": ["Reykjavik", "Northern Iceland"],

    # RUSSIA
    "Moscow": ["Saint Petersburg", "Southern Russia", "Volga Region", "Ural", "Vitebsk & Mogilev"],  # Belarus
    "Saint Petersburg": ["Moscow", "Arctic Russia", "Tallinn", "Helsinki & Uusimaa", "Eastern Finland"],  # Estonia/Finland
    "Southern Russia": ["Moscow", "Volga Region", "North Caucasus", "Eastern Ukraine", "Donbas", "Crimea"],  # Ukraine
    "Volga Region": ["Moscow", "Southern Russia", "Ural", "North Caucasus"],
    "Ural": ["Moscow", "Volga Region", "Western Siberia"],
    "Western Siberia": ["Ural", "Eastern Siberia", "Manchuria"],  # China connection
    "Eastern Siberia": ["Western Siberia", "Far East", "Manchuria", "Beijing"],  # China
    "Far East": ["Eastern Siberia", "Manchuria", "Hokkaido"],  # China/Japan (sea)
    "North Caucasus": ["Southern Russia", "Volga Region", "Tbilisi", "Eastern Georgia"],  # Georgia
    "Arctic Russia": ["Saint Petersburg", "Northern Norway"],  # Norway

    # CHINA
    "Beijing": ["Shanghai", "Shandong", "Manchuria", "Xinjiang", "Eastern Siberia"],  # Russia
    "Shanghai": ["Beijing", "Guangdong", "Zhejiang & Jiangsu", "Hubei"],
    "Guangdong": ["Shanghai", "Zhejiang & Jiangsu", "Hubei", "Sichuan"],
    "Sichuan": ["Guangdong", "Hubei", "Xinjiang", "Tibet"],
    "Zhejiang & Jiangsu": ["Shanghai", "Guangdong", "Shandong", "Hubei"],
    "Shandong": ["Beijing", "Zhejiang & Jiangsu", "Hubei", "Seoul"],  # South Korea (sea)
    "Hubei": ["Shanghai", "Guangdong", "Sichuan", "Zhejiang & Jiangsu", "Shandong"],
    "Xinjiang": ["Beijing", "Sichuan", "Tibet", "Mashhad & Khorasan"],  # Iran connection
    "Tibet": ["Sichuan", "Xinjiang"],
    "Manchuria": ["Beijing", "Western Siberia", "Eastern Siberia", "Far East", "Seoul"],  # Russia/S.Korea

    # JAPAN
    "Tokyo": ["Osaka & Kansai", "Nagoya & Chubu", "Tohoku"],
    "Osaka & Kansai": ["Tokyo", "Nagoya & Chubu", "Kyushu"],
    "Nagoya & Chubu": ["Tokyo", "Osaka & Kansai"],
    "Kyushu": ["Osaka & Kansai", "Busan"],  # South Korea (sea)
    "Hokkaido": ["Tohoku", "Far East"],  # Russia (sea)
    "Tohoku": ["Tokyo", "Hokkaido"],

    # SOUTH KOREA
    "Seoul": ["Busan", "Incheon & Gyeonggi", "Daegu & Gyeongsang", "Daejeon & Chungcheong", "Shandong", "Manchuria"],  # China
    "Busan": ["Seoul", "Daegu & Gyeongsang", "Kyushu"],  # Japan (sea)
    "Incheon & Gyeonggi": ["Seoul", "Daejeon & Chungcheong"],
    "Daegu & Gyeongsang": ["Seoul", "Busan", "Daejeon & Chungcheong"],
    "Daejeon & Chungcheong": ["Seoul", "Incheon & Gyeonggi", "Daegu & Gyeongsang"],

    # ISRAEL
    "Tel Aviv": ["Jerusalem", "Haifa & North", "Negev & South", "Cairo"],  # Egypt connection
    "Jerusalem": ["Tel Aviv", "Haifa & North", "Negev & South"],
    "Haifa & North": ["Tel Aviv", "Jerusalem"],
    "Negev & South": ["Tel Aviv", "Jerusalem", "Sinai Peninsula"],  # Egypt

    # GEORGIA
    "Tbilisi": ["Batumi & Adjara", "Kutaisi & Imereti", "Eastern Georgia", "North Caucasus", "Tabriz & Azerbaijan"],  # Russia/Iran
    "Batumi & Adjara": ["Tbilisi", "Kutaisi & Imereti", "Black Sea Region"],  # Turkey
    "Kutaisi & Imereti": ["Tbilisi", "Batumi & Adjara", "Eastern Georgia"],
    "Eastern Georgia": ["Tbilisi", "Kutaisi & Imereti", "North Caucasus"],  # Russia

    # UAE
    "Dubai": ["Abu Dhabi", "Sharjah & Northern Emirates", "Muscat"],  # Oman
    "Abu Dhabi": ["Dubai", "Sharjah & Northern Emirates", "Eastern Emirates", "Eastern Province"],  # Saudi
    "Sharjah & Northern Emirates": ["Dubai", "Abu Dhabi", "Eastern Emirates"],
    "Eastern Emirates": ["Abu Dhabi", "Sharjah & Northern Emirates", "Muscat"],  # Oman

    # SAUDI ARABIA
    "Riyadh": ["Jeddah & Mecca", "Eastern Province", "Medina", "Asir & South", "Tabuk & Northern Borders"],
    "Jeddah & Mecca": ["Riyadh", "Medina", "Asir & South"],
    "Eastern Province": ["Riyadh", "Kuwait City", "Manama", "Doha", "Abu Dhabi"],  # Kuwait/Bahrain/Qatar/UAE
    "Medina": ["Riyadh", "Jeddah & Mecca", "Tabuk & Northern Borders"],
    "Asir & South": ["Riyadh", "Jeddah & Mecca"],
    "Tabuk & Northern Borders": ["Riyadh", "Medina", "Negev & South", "Ankara"],  # Israel/Turkey (distant)

    # QATAR
    "Doha": ["Al Wakrah & South", "Al Khor & North", "Eastern Province", "Manama"],  # Saudi/Bahrain
    "Al Wakrah & South": ["Doha", "Al Khor & North"],
    "Al Khor & North": ["Doha", "Al Wakrah & South"],

    # KUWAIT
    "Kuwait City": ["Ahmadi", "Jahra", "Eastern Province"],  # Saudi connection
    "Ahmadi": ["Kuwait City", "Jahra"],
    "Jahra": ["Kuwait City", "Ahmadi"],

    # BAHRAIN
    "Manama": ["Muharraq & Southern Bahrain", "Eastern Province", "Doha"],  # Saudi/Qatar
    "Muharraq & Southern Bahrain": ["Manama"],

    # OMAN
    "Muscat": ["Dhofar", "Al Batinah", "Al Dakhiliyah", "Dubai", "Eastern Emirates"],  # UAE
    "Dhofar": ["Muscat", "Al Dakhiliyah"],
    "Al Batinah": ["Muscat", "Al Dakhiliyah"],
    "Al Dakhiliyah": ["Muscat", "Dhofar", "Al Batinah"],

    # TURKEY
    "Istanbul": ["Ankara", "Izmir & Aegean", "Black Sea Region", "Plovdiv & Thrace", "Central Macedonia"],  # Bulgaria/Greece
    "Ankara": ["Istanbul", "Izmir & Aegean", "Antalya & Mediterranean", "Central Anatolia", "Black Sea Region", "Eastern Anatolia"],
    "Izmir & Aegean": ["Istanbul", "Ankara", "Antalya & Mediterranean", "Aegean Islands"],  # Greece (sea)
    "Antalya & Mediterranean": ["Ankara", "Izmir & Aegean", "Central Anatolia", "Eastern Anatolia"],
    "Eastern Anatolia": ["Ankara", "Antalya & Mediterranean", "Central Anatolia", "Black Sea Region", "Tbilisi", "Tehran", "Tabriz & Azerbaijan"],  # Georgia/Iran
    "Black Sea Region": ["Istanbul", "Ankara", "Eastern Anatolia", "Batumi & Adjara"],  # Georgia
    "Central Anatolia": ["Ankara", "Antalya & Mediterranean", "Eastern Anatolia"],

    # IRAN
    "Tehran": ["Isfahan", "Mashhad & Khorasan", "Tabriz & Azerbaijan", "Eastern Anatolia"],  # Turkey
    "Isfahan": ["Tehran", "Shiraz & Fars", "Mashhad & Khorasan", "Khuzestan"],
    "Mashhad & Khorasan": ["Tehran", "Isfahan", "Xinjiang"],  # China connection
    "Shiraz & Fars": ["Isfahan", "Khuzestan"],
    "Tabriz & Azerbaijan": ["Tehran", "Eastern Anatolia", "Tbilisi"],  # Turkey/Georgia
    "Khuzestan": ["Isfahan", "Shiraz & Fars", "Eastern Province"],  # Saudi (Persian Gulf)

    # BRAZIL
    "São Paulo": ["Rio de Janeiro", "Minas Gerais", "Paraná & Santa Catarina", "Brasília"],
    "Rio de Janeiro": ["São Paulo", "Minas Gerais", "Bahia & Northeast"],
    "Brasília": ["São Paulo", "Minas Gerais", "Bahia & Northeast", "Amazonas"],
    "Minas Gerais": ["São Paulo", "Rio de Janeiro", "Brasília", "Bahia & Northeast"],
    "Bahia & Northeast": ["Rio de Janeiro", "Brasília", "Minas Gerais", "Amazonas"],
    "Rio Grande do Sul": ["Paraná & Santa Catarina", "Montevideo", "Buenos Aires"],  # Uruguay/Argentina
    "Amazonas": ["Brasília", "Bahia & Northeast", "Bogotá", "Lima", "Caracas"],  # Colombia/Peru/Venezuela
    "Paraná & Santa Catarina": ["São Paulo", "Rio Grande do Sul"],

    # ARGENTINA
    "Buenos Aires": ["Córdoba", "Rosario & Santa Fe", "Patagonia", "Montevideo", "Rio Grande do Sul"],  # Uruguay/Brazil
    "Córdoba": ["Buenos Aires", "Mendoza", "Rosario & Santa Fe", "Tucumán & Northwest"],
    "Mendoza": ["Córdoba", "Patagonia", "Santiago", "Valparaíso"],  # Chile
    "Patagonia": ["Buenos Aires", "Mendoza", "Patagonia & Magallanes"],  # Chile
    "Rosario & Santa Fe": ["Buenos Aires", "Córdoba", "Asunción"],  # Paraguay
    "Tucumán & Northwest": ["Córdoba", "La Paz", "Asunción"],  # Bolivia/Paraguay

    # COLOMBIA
    "Bogotá": ["Medellín & Antioquia", "Cali & Valle del Cauca", "Coffee Region", "Amazonas", "Caracas"],  # Brazil/Venezuela
    "Medellín & Antioquia": ["Bogotá", "Colombian Caribbean", "Coffee Region", "Panama City"],  # Panama
    "Cali & Valle del Cauca": ["Bogotá", "Coffee Region", "Quito"],  # Ecuador
    "Colombian Caribbean": ["Medellín & Antioquia", "Maracaibo & Zulia"],  # Venezuela
    "Coffee Region": ["Bogotá", "Medellín & Antioquia", "Cali & Valle del Cauca"],

    # CHILE
    "Santiago": ["Valparaíso", "Concepción & Biobío", "Atacama & Norte Grande", "Mendoza"],  # Argentina
    "Valparaíso": ["Santiago", "Concepción & Biobío", "Mendoza"],  # Argentina
    "Concepción & Biobío": ["Santiago", "Valparaíso", "Patagonia & Magallanes"],
    "Atacama & Norte Grande": ["Santiago", "La Paz", "Arequipa"],  # Bolivia/Peru
    "Patagonia & Magallanes": ["Concepción & Biobío", "Patagonia"],  # Argentina

    # PERU
    "Lima": ["Cusco & Highlands", "Arequipa", "Trujillo & North Coast", "Amazonia", "Amazonas"],  # Brazil
    "Cusco & Highlands": ["Lima", "Arequipa", "Amazonia", "La Paz"],  # Bolivia
    "Arequipa": ["Lima", "Cusco & Highlands", "Atacama & Norte Grande"],  # Chile
    "Trujillo & North Coast": ["Lima", "Amazonia", "Guayaquil"],  # Ecuador
    "Amazonia": ["Lima", "Cusco & Highlands", "Trujillo & North Coast", "Amazonas"],  # Brazil

    # VENEZUELA
    "Caracas": ["Maracaibo & Zulia", "Valencia & Central", "Barquisimeto & Lara", "Guayana", "Bogotá", "Amazonas"],  # Colombia/Brazil
    "Maracaibo & Zulia": ["Caracas", "Valencia & Central", "Caribbean Coast"],  # Colombia
    "Valencia & Central": ["Caracas", "Maracaibo & Zulia", "Barquisimeto & Lara", "Guayana"],
    "Barquisimeto & Lara": ["Caracas", "Valencia & Central"],
    "Guayana": ["Caracas", "Valencia & Central", "Amazonas"],  # Brazil

    # ECUADOR
    "Quito": ["Guayaquil", "Cuenca & Southern Highlands", "Amazonia & Galápagos", "Cali & Valle del Cauca"],  # Colombia
    "Guayaquil": ["Quito", "Cuenca & Southern Highlands", "Trujillo & North Coast"],  # Peru
    "Cuenca & Southern Highlands": ["Quito", "Guayaquil", "Amazonia & Galápagos"],
    "Amazonia & Galápagos": ["Quito", "Cuenca & Southern Highlands", "Amazonia"],  # Peru

    # URUGUAY
    "Montevideo": ["Punta del Este & Southeast", "Interior", "Buenos Aires", "Rio Grande do Sul"],  # Argentina/Brazil
    "Punta del Este & Southeast": ["Montevideo", "Interior"],
    "Interior": ["Montevideo", "Punta del Este & Southeast", "Rio Grande do Sul"],  # Brazil

    # PARAGUAY
    "Asunción": ["Ciudad del Este", "Chaco", "Rosario & Santa Fe", "Tucumán & Northwest", "Minas Gerais"],  # Argentina/Bolivia/Brazil
    "Ciudad del Este": ["Asunción", "Chaco", "Paraná & Santa Catarina"],  # Brazil
    "Chaco": ["Asunción", "Ciudad del Este", "Santa Cruz"],  # Bolivia

    # BOLIVIA
    "La Paz": ["Santa Cruz", "Cochabamba", "Sucre & Potosí", "Cusco & Highlands", "Atacama & Norte Grande", "Tucumán & Northwest"],  # Peru/Chile/Argentina
    "Santa Cruz": ["La Paz", "Cochabamba", "Sucre & Potosí", "Chaco", "Amazonas"],  # Paraguay/Brazil
    "Cochabamba": ["La Paz", "Santa Cruz", "Sucre & Potosí"],
    "Sucre & Potosí": ["La Paz", "Santa Cruz", "Cochabamba"],

    # PANAMA
    "Panama City": ["Colón", "Western Panama", "Medellín & Antioquia", "San José"],  # Colombia/Costa Rica
    "Colón": ["Panama City", "Western Panama"],
    "Western Panama": ["Panama City", "Colón", "San José"],  # Costa Rica

    # COSTA RICA
    "San José": ["Costa Rican Caribbean", "Costa Rican Pacific", "Panama City", "Western Panama", "Managua"],  # Panama/Nicaragua
    "Costa Rican Caribbean": ["San José", "Costa Rican Pacific"],
    "Costa Rican Pacific": ["San José", "Costa Rican Caribbean"],

    # GUATEMALA
    "Guatemala City": ["Quetzaltenango", "Petén", "Pacific Lowlands", "San Salvador", "Tegucigalpa"],  # El Salvador/Honduras
    "Quetzaltenango": ["Guatemala City", "Petén", "Pacific Lowlands"],
    "Petén": ["Guatemala City", "Quetzaltenango"],
    "Pacific Lowlands": ["Guatemala City", "Quetzaltenango"],

    # HONDURAS
    "Tegucigalpa": ["San Pedro Sula", "Honduran Caribbean", "Guatemala City", "San Salvador", "Managua"],  # Guatemala/El Salvador/Nicaragua
    "San Pedro Sula": ["Tegucigalpa", "Honduran Caribbean"],
    "Honduran Caribbean": ["Tegucigalpa", "San Pedro Sula"],

    # EL SALVADOR
    "San Salvador": ["Santa Ana", "San Miguel", "Guatemala City", "Tegucigalpa"],  # Guatemala/Honduras
    "Santa Ana": ["San Salvador", "San Miguel"],
    "San Miguel": ["San Salvador", "Santa Ana", "Tegucigalpa"],  # Honduras

    # NICARAGUA
    "Managua": ["León & Pacific", "Nicaraguan Caribbean", "San José", "Tegucigalpa"],  # Costa Rica/Honduras
    "León & Pacific": ["Managua", "Nicaraguan Caribbean"],
    "Nicaraguan Caribbean": ["Managua", "León & Pacific"],

    # DOMINICAN REPUBLIC
    "Santo Domingo": ["Santiago de los Caballeros", "Punta Cana & East", "Puerto Plata & North Coast"],
    "Santiago de los Caballeros": ["Santo Domingo", "Puerto Plata & North Coast"],
    "Punta Cana & East": ["Santo Domingo", "Puerto Plata & North Coast"],
    "Puerto Plata & North Coast": ["Santo Domingo", "Santiago de los Caballeros", "Punta Cana & East"],

    # EGYPT
    "Cairo": ["Alexandria", "Luxor & Upper Egypt", "Suez & Canal Zone", "Tel Aviv"],  # Israel
    "Alexandria": ["Cairo", "Suez & Canal Zone"],
    "Luxor & Upper Egypt": ["Cairo", "Suez & Canal Zone", "Sinai Peninsula"],
    "Suez & Canal Zone": ["Cairo", "Alexandria", "Luxor & Upper Egypt", "Sinai Peninsula"],
    "Sinai Peninsula": ["Luxor & Upper Egypt", "Suez & Canal Zone", "Negev & South"],  # Israel

    # SOUTH AFRICA
    "Johannesburg & Gauteng": ["Cape Town & Western Cape", "Durban & KwaZulu-Natal", "Pretoria", "Port Elizabeth & Eastern Cape"],
    "Cape Town & Western Cape": ["Johannesburg & Gauteng", "Port Elizabeth & Eastern Cape"],
    "Durban & KwaZulu-Natal": ["Johannesburg & Gauteng", "Pretoria", "Port Elizabeth & Eastern Cape"],
    "Pretoria": ["Johannesburg & Gauteng", "Durban & KwaZulu-Natal"],
    "Port Elizabeth & Eastern Cape": ["Johannesburg & Gauteng", "Cape Town & Western Cape", "Durban & KwaZulu-Natal"],
}


def seed_countries_and_regions(app):
    """Seed all NEW countries and their regions. Does NOT touch existing countries."""
    print("--- Seeding NEW Countries and Regions ---")
    print(f"    (Skipping existing countries: {', '.join(EXISTING_COUNTRIES)})")

    added_countries = 0
    added_regions = 0
    new_country_ids = []  # Track IDs of newly added countries

    with app.app_context():
        for country_name, flag_code, currency_code, region_names in COUNTRIES_DATA:
            # Check if country exists
            existing_country = db.session.scalar(
                db.select(Country).filter_by(slug=slugify(country_name))
            )

            if existing_country:
                print(f"  Skipping {country_name} - already exists")
                continue  # Skip entirely, don't add regions to existing countries
            else:
                print(f"  Adding country: {country_name}")
                country = Country(
                    name=country_name,
                    flag_code=flag_code,
                    currency_code=currency_code,
                    currency_name=currency_code
                )
                db.session.add(country)
                db.session.flush()
                added_countries += 1
                new_country_ids.append(country.id)

                # Add regions only for NEW countries
                for region_name in region_names:
                    existing_region = db.session.scalar(
                        db.select(Region).filter_by(slug=slugify(region_name))
                    )

                    if existing_region:
                        print(f"    Skipping region {region_name} - already exists")
                    else:
                        print(f"    Adding region: {region_name}")
                        region = Region(name=region_name, original_owner_id=country.id)
                        db.session.add(region)
                        db.session.flush()
                        country.current_regions.append(region)
                        added_regions += 1

        try:
            db.session.commit()
            print(f"\n  Successfully added {added_countries} countries and {added_regions} regions")
        except Exception as e:
            db.session.rollback()
            print(f"\n  ERROR committing countries/regions: {e}")
            return False, []

    return True, new_country_ids


def seed_region_neighbors(app):
    """Seed region neighbor relationships."""
    print("\n--- Seeding Region Neighbors ---")

    added_neighbors = 0

    with app.app_context():
        # Build a map of region slug -> region object
        all_regions = db.session.scalars(db.select(Region)).all()
        region_map = {r.slug: r for r in all_regions}

        for region_name, neighbor_names in REGION_NEIGHBORS.items():
            region_slug = slugify(region_name)
            region = region_map.get(region_slug)

            if not region:
                # Try exact name match as fallback
                region = db.session.scalar(db.select(Region).filter_by(name=region_name))
                if not region:
                    print(f"  WARNING: Region '{region_name}' not found, skipping neighbors")
                    continue

            for neighbor_name in neighbor_names:
                neighbor_slug = slugify(neighbor_name)
                neighbor = region_map.get(neighbor_slug)

                if not neighbor:
                    # Try exact name match as fallback
                    neighbor = db.session.scalar(db.select(Region).filter_by(name=neighbor_name))
                    if not neighbor:
                        # Skip silently - neighbor might be in a country not yet added
                        continue

                # Check if neighbor relationship already exists
                existing = db.session.scalar(
                    db.select(Region).filter(
                        Region.id == region.id
                    ).filter(
                        Region.neighbors.contains(neighbor)
                    )
                )

                if not existing:
                    region.neighbors.append(neighbor)
                    added_neighbors += 1

        try:
            db.session.commit()
            print(f"  Successfully added {added_neighbors} neighbor relationships")
        except Exception as e:
            db.session.rollback()
            print(f"  ERROR committing neighbors: {e}")
            return False

    return True


def seed_gold_markets(app, new_country_ids=None):
    """Seed gold markets for NEW countries only."""
    print("\n--- Seeding Gold Markets for NEW Countries ---")

    if not new_country_ids:
        print("  No new countries to seed gold markets for.")
        return True

    added_count = 0

    with app.app_context():
        # Only get new countries by ID
        countries = db.session.scalars(
            db.select(Country).filter(Country.id.in_(new_country_ids))
        ).all()

        for country in countries:
            existing = db.session.scalar(
                db.select(GoldMarket).filter_by(country_id=country.id)
            )

            if not existing:
                gold_market = GoldMarket(
                    country_id=country.id,
                    initial_exchange_rate=Decimal('100.00'),
                    price_level=0,
                    progress_within_level=0,
                    volume_per_level=1000,
                    price_adjustment_per_level=Decimal('1.00')
                )
                db.session.add(gold_market)
                added_count += 1
                print(f"    Added gold market for: {country.name}")

        try:
            db.session.commit()
            print(f"  Successfully added {added_count} gold markets")
        except Exception as e:
            db.session.rollback()
            print(f"  ERROR committing gold markets: {e}")
            return False

    return True


def seed_resource_markets(app, new_country_ids=None):
    """Seed resource markets for NEW countries only."""
    print("\n--- Seeding Resource Markets for NEW Countries ---")

    if not new_country_ids:
        print("  No new countries to seed resource markets for.")
        return True

    initial_price = Decimal('5.00')
    added_count = 0

    with app.app_context():
        all_resources = db.session.scalars(db.select(Resource)).all()

        # Only get new countries by ID
        countries = db.session.scalars(
            db.select(Country).filter(Country.id.in_(new_country_ids))
        ).all()

        if not all_resources:
            print("  No resources found. Run seed_resources.py first.")
            return False

        for country in countries:
            print(f"    Adding market items for: {country.name}")
            for resource in all_resources:
                # Determine quality levels
                if resource.can_have_quality:
                    quality_levels = [1, 2, 3, 4, 5]
                else:
                    quality_levels = [0]

                for quality in quality_levels:
                    existing = db.session.scalar(
                        db.select(CountryMarketItem).filter_by(
                            country_id=country.id,
                            resource_id=resource.id,
                            quality=quality
                        )
                    )

                    if not existing:
                        quality_multiplier = Decimal('1.0') + (Decimal('0.2') * quality) if quality > 0 else Decimal('1.0')
                        adjusted_price = initial_price * quality_multiplier

                        market_item = CountryMarketItem(
                            country_id=country.id,
                            resource_id=resource.id,
                            quality=quality,
                            initial_price=adjusted_price,
                            price_level=0,
                            progress_within_level=0
                        )
                        db.session.add(market_item)
                        added_count += 1

        try:
            db.session.commit()
            print(f"  Successfully added {added_count} market items")
        except Exception as e:
            db.session.rollback()
            print(f"  ERROR committing market items: {e}")
            return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("TACTIZEN - New Countries Seed Script")
    print("=" * 60)
    print("\nIMPORTANT: This script will NOT modify existing countries!")
    print(f"Protected countries: {', '.join(EXISTING_COUNTRIES)}")
    print("=" * 60)

    flask_app = create_app()

    # Step 1: Seed countries and regions
    result = seed_countries_and_regions(flask_app)
    if isinstance(result, tuple):
        success, new_country_ids = result
    else:
        success = result
        new_country_ids = []

    if not success:
        print("\nFailed to seed countries. Aborting.")
        sys.exit(1)

    if not new_country_ids:
        print("\nNo new countries were added (all may already exist).")
        print("Checking for region neighbors only...")

    # Step 2: Seed region neighbors (this can add neighbors between new and existing regions)
    if not seed_region_neighbors(flask_app):
        print("\nFailed to seed neighbors. Continuing anyway...")

    # Step 3: Seed gold markets (only for NEW countries)
    if not seed_gold_markets(flask_app, new_country_ids):
        print("\nFailed to seed gold markets. Continuing anyway...")

    # Step 4: Seed resource markets (only for NEW countries)
    if not seed_resource_markets(flask_app, new_country_ids):
        print("\nFailed to seed resource markets. Continuing anyway...")

    print("\n" + "=" * 60)
    print("Seeding Complete!")
    print(f"Added {len(new_country_ids)} new countries with markets.")
    print("Existing countries were NOT modified.")
    print("=" * 60)
