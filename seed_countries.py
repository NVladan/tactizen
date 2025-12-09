"""
Comprehensive seed script for ALL countries, regions, currencies, markets, and neighbors.
Run this script to seed 72 countries with all related data.

Usage:
    python seed_countries.py          # Normal seed (skips existing)
    python seed_countries.py --reset  # Clear all and reseed from scratch
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

# All countries data: (name, flag_code, currency_code, [regions])
COUNTRIES_DATA = [
    # NORTH AMERICA
    ("United States", "us", "USD", [
        "New England", "New York & New Jersey", "Mid-Atlantic", "Appalachia",
        "The Carolinas", "Southeastern Coast", "Florida Panhandle & Lower Gulf",
        "Deep South Interior", "Texas", "Southern Plains", "Central Plains",
        "Great Lakes", "Upper Midwest", "Mountain West", "Southwest",
        "Pacific Coast", "Alaska", "Hawaii"
    ]),
    ("Mexico", "mx", "MXN", [
        "Northwest Mexico", "Northeast Mexico", "Central Mexico",
        "Pacific Coast and Sierra Region", "Gulf and Southeast Region",
        "Yucatán Peninsula and Southern Highlands"
    ]),
    ("Canada", "ca", "CAD", [
        "Atlantic Canada", "Quebec", "Ontario", "Prairie Provinces",
        "British Columbia", "Northern Territories"
    ]),

    # EUROPE
    ("United Kingdom", "gb", "GBP", [
        "Greater London", "South England", "Midlands", "North England",
        "Scotland", "Wales & Northern Ireland"
    ]),
    ("Germany", "de", "DEM", [
        "Bavaria", "Baden-Württemberg", "North Rhine-Westphalia",
        "Berlin & Brandenburg", "Lower Saxony & Hamburg", "Saxony & Thuringia"
    ]),
    ("France", "fr", "FRF", [
        "Île-de-France", "Provence-Côte d'Azur", "Auvergne-Rhône-Alpes",
        "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France & Normandy"
    ]),
    ("Italy", "it", "ITL", [
        "Lombardy", "Lazio", "Veneto", "Piedmont & Liguria",
        "Tuscany & Emilia-Romagna", "Southern Italy & Sicily"
    ]),
    ("Spain", "es", "ESP", [
        "Madrid", "Catalonia", "Andalusia", "Valencia",
        "Basque Country & Navarra", "Galicia & Castile"
    ]),
    ("Portugal", "pt", "PTE", [
        "Lisbon", "Porto & Norte", "Algarve", "Central Portugal"
    ]),
    ("Netherlands", "nl", "NLG", [
        "North Holland", "South Holland", "Brabant & Limburg", "Eastern Netherlands"
    ]),
    ("Belgium", "be", "BEF", [
        "Brussels", "Flanders", "Wallonia"
    ]),
    ("Switzerland", "ch", "CHF", [
        "Zurich & Northeast", "Bern & Central", "Geneva & Romandy", "Ticino & Alps"
    ]),
    ("Austria", "at", "ATS", [
        "Vienna", "Upper & Lower Austria", "Tyrol & Vorarlberg", "Styria & Carinthia"
    ]),
    ("Poland", "pl", "PLN", [
        "Masovia", "Lesser Poland", "Greater Poland", "Silesia", "Pomerania"
    ]),
    ("Czech Republic", "cz", "CZK", [
        "Bohemia", "Moravia", "Czech Silesia"
    ]),
    ("Slovakia", "sk", "SKK", [
        "Bratislava", "Central Slovakia", "Eastern Slovakia"
    ]),
    ("Hungary", "hu", "HUF", [
        "Budapest", "Western Transdanubia", "Southern Hungary", "Eastern Hungary"
    ]),
    ("Romania", "ro", "RON", [
        "Bucharest & Wallachia", "Transylvania", "Moldova",
        "Banat & Crișana", "Dobrogea & Black Sea"
    ]),
    ("Bulgaria", "bg", "BGN", [
        "Sofia", "Plovdiv & Thrace", "Varna & Black Sea", "Northern Bulgaria"
    ]),
    ("Greece", "gr", "GRD", [
        "Attica", "Central Macedonia", "Peloponnese", "Crete", "Aegean Islands"
    ]),
    ("Serbia", "rs", "RSD", [
        "Belgrade", "Vojvodina", "Šumadija & Western Serbia",
        "Southern Serbia", "Kosovo and Metohija"
    ]),
    ("Croatia", "hr", "HRK", [
        "Zagreb", "Dalmatia", "Slavonia", "Istria & Kvarner"
    ]),
    ("Slovenia", "si", "SIT", [
        "Ljubljana", "Maribor & Styria", "Coastal Slovenia"
    ]),
    ("Bosnia and Herzegovina", "ba", "BAM", [
        "Sarajevo", "Republika Srpska", "Herzegovina", "Brčko District"
    ]),
    ("Montenegro", "me", "EUR", [
        "Podgorica", "Coastal Montenegro", "Northern Montenegro"
    ]),
    ("North Macedonia", "mk", "MKD", [
        "Skopje", "Western Macedonia", "Eastern Macedonia"
    ]),
    ("Albania", "al", "ALL", [
        "Tirana", "Southern Albania", "Northern Albania", "Central Albania & Coast"
    ]),
    ("Ukraine", "ua", "UAH", [
        "Kyiv", "Western Ukraine", "Southern Ukraine", "Eastern Ukraine",
        "Donbas", "Crimea", "Central Ukraine"
    ]),
    ("Belarus", "by", "BYN", [
        "Minsk", "Brest Region", "Grodno Region", "Gomel Region", "Vitebsk & Mogilev"
    ]),
    ("Moldova", "md", "MDL", [
        "Chișinău", "Transnistria", "Gagauzia & Southern Moldova"
    ]),
    ("Lithuania", "lt", "LTL", [
        "Vilnius", "Kaunas Region", "Klaipėda & Coast"
    ]),
    ("Latvia", "lv", "LVL", [
        "Riga", "Kurzeme", "Latgale"
    ]),
    ("Estonia", "ee", "EEK", [
        "Tallinn", "Tartu", "Western Estonia"
    ]),
    ("Finland", "fi", "FIM", [
        "Helsinki & Uusimaa", "Tampere & Pirkanmaa", "Turku & Southwest",
        "Eastern Finland", "Lapland & North"
    ]),
    ("Sweden", "se", "SEK", [
        "Stockholm", "Gothenburg & West", "Malmö & Skåne", "Central Sweden", "Norrland"
    ]),
    ("Norway", "no", "NOK", [
        "Oslo", "Bergen & West", "Trondheim & Central", "Stavanger & Southwest", "Northern Norway"
    ]),
    ("Denmark", "dk", "DKK", [
        "Copenhagen", "Jutland North", "Jutland South", "Bornholm & Islands"
    ]),
    ("Ireland", "ie", "IEP", [
        "Dublin", "Cork & Munster", "Galway & Connacht", "Ulster (Republic)"
    ]),
    ("Iceland", "is", "ISK", [
        "Reykjavik", "Northern Iceland", "Eastern & Southern Iceland"
    ]),

    # ASIA
    ("Russia", "ru", "RUB", [
        "Moscow", "Saint Petersburg", "Southern Russia", "Volga Region", "Ural",
        "Western Siberia", "Eastern Siberia", "Far East", "North Caucasus", "Arctic Russia"
    ]),
    ("China", "cn", "CNY", [
        "Beijing", "Shanghai", "Guangdong", "Sichuan", "Zhejiang & Jiangsu",
        "Shandong", "Hubei", "Xinjiang", "Tibet", "Manchuria"
    ]),
    ("Japan", "jp", "JPY", [
        "Tokyo", "Osaka & Kansai", "Nagoya & Chubu", "Kyushu", "Hokkaido", "Tohoku"
    ]),
    ("South Korea", "kr", "KRW", [
        "Seoul", "Busan", "Incheon & Gyeonggi", "Daegu & Gyeongsang", "Daejeon & Chungcheong"
    ]),

    # MIDDLE EAST
    ("Israel", "il", "ILS", [
        "Tel Aviv", "Jerusalem", "Haifa & North", "Negev & South"
    ]),
    ("Georgia", "ge", "GEL", [
        "Tbilisi", "Batumi & Adjara", "Kutaisi & Imereti", "Eastern Georgia"
    ]),
    ("United Arab Emirates", "ae", "AED", [
        "Dubai", "Abu Dhabi", "Sharjah & Northern Emirates", "Eastern Emirates"
    ]),
    ("Saudi Arabia", "sa", "SAR", [
        "Riyadh", "Jeddah & Mecca", "Eastern Province", "Medina",
        "Asir & South", "Tabuk & Northern Borders"
    ]),
    ("Qatar", "qa", "QAR", [
        "Doha", "Al Wakrah & South", "Al Khor & North"
    ]),
    ("Kuwait", "kw", "KWD", [
        "Kuwait City", "Ahmadi", "Jahra"
    ]),
    ("Bahrain", "bh", "BHD", [
        "Manama", "Muharraq & Southern Bahrain"
    ]),
    ("Oman", "om", "OMR", [
        "Muscat", "Dhofar", "Al Batinah", "Al Dakhiliyah"
    ]),
    ("Turkey", "tr", "TRY", [
        "Istanbul", "Ankara", "Izmir & Aegean", "Antalya & Mediterranean",
        "Eastern Anatolia", "Black Sea Region", "Central Anatolia"
    ]),
    ("Iran", "ir", "IRR", [
        "Tehran", "Isfahan", "Mashhad & Khorasan", "Shiraz & Fars",
        "Tabriz & Azerbaijan", "Khuzestan"
    ]),

    # SOUTH AMERICA
    ("Brazil", "br", "BRL", [
        "São Paulo", "Rio de Janeiro", "Brasília", "Minas Gerais",
        "Bahia & Northeast", "Rio Grande do Sul", "Amazonas", "Paraná & Santa Catarina"
    ]),
    ("Argentina", "ar", "ARS", [
        "Buenos Aires", "Córdoba", "Mendoza", "Patagonia",
        "Rosario & Santa Fe", "Tucumán & Northwest"
    ]),
    ("Colombia", "co", "COP", [
        "Bogotá", "Medellín & Antioquia", "Cali & Valle del Cauca",
        "Colombian Caribbean", "Coffee Region"
    ]),
    ("Chile", "cl", "CLP", [
        "Santiago", "Valparaíso", "Concepción & Biobío",
        "Atacama & Norte Grande", "Patagonia & Magallanes"
    ]),
    ("Peru", "pe", "PEN", [
        "Lima", "Cusco & Highlands", "Arequipa", "Trujillo & North Coast", "Amazonia"
    ]),
    ("Venezuela", "ve", "VES", [
        "Caracas", "Maracaibo & Zulia", "Valencia & Central",
        "Barquisimeto & Lara", "Guayana"
    ]),
    ("Ecuador", "ec", "USD", [
        "Quito", "Guayaquil", "Cuenca & Southern Highlands", "Amazonia & Galápagos"
    ]),
    ("Uruguay", "uy", "UYU", [
        "Montevideo", "Punta del Este & Southeast", "Interior"
    ]),
    ("Paraguay", "py", "PYG", [
        "Asunción", "Ciudad del Este", "Chaco"
    ]),
    ("Bolivia", "bo", "BOB", [
        "La Paz", "Santa Cruz", "Cochabamba", "Sucre & Potosí"
    ]),

    # CENTRAL AMERICA & CARIBBEAN
    ("Panama", "pa", "PAB", [
        "Panama City", "Colón", "Western Panama"
    ]),
    ("Costa Rica", "cr", "CRC", [
        "San José", "Costa Rican Caribbean", "Costa Rican Pacific"
    ]),
    ("Guatemala", "gt", "GTQ", [
        "Guatemala City", "Quetzaltenango", "Petén", "Pacific Lowlands"
    ]),
    ("Honduras", "hn", "HNL", [
        "Tegucigalpa", "San Pedro Sula", "Honduran Caribbean"
    ]),
    ("El Salvador", "sv", "USD", [
        "San Salvador", "Santa Ana", "San Miguel"
    ]),
    ("Nicaragua", "ni", "NIO", [
        "Managua", "León & Pacific", "Nicaraguan Caribbean"
    ]),
    ("Dominican Republic", "do", "DOP", [
        "Santo Domingo", "Santiago de los Caballeros",
        "Punta Cana & East", "Puerto Plata & North Coast"
    ]),

    # AFRICA
    ("Egypt", "eg", "EGP", [
        "Cairo", "Alexandria", "Luxor & Upper Egypt", "Suez & Canal Zone", "Sinai Peninsula"
    ]),
    ("South Africa", "za", "ZAR", [
        "Johannesburg & Gauteng", "Cape Town & Western Cape", "Durban & KwaZulu-Natal",
        "Pretoria", "Port Elizabeth & Eastern Cape"
    ]),
]

# Region neighbors mapping: region_name -> [list of neighbor region names]
REGION_NEIGHBORS = {
    # USA Internal
    "New England": ["New York & New Jersey", "Atlantic Canada", "Quebec"],
    "New York & New Jersey": ["New England", "Mid-Atlantic", "Great Lakes", "Quebec", "Ontario"],
    "Mid-Atlantic": ["New York & New Jersey", "Appalachia", "The Carolinas"],
    "Appalachia": ["Mid-Atlantic", "The Carolinas", "Deep South Interior", "Great Lakes"],
    "The Carolinas": ["Mid-Atlantic", "Appalachia", "Southeastern Coast", "Deep South Interior"],
    "Southeastern Coast": ["The Carolinas", "Florida Panhandle & Lower Gulf", "Deep South Interior"],
    "Florida Panhandle & Lower Gulf": ["Southeastern Coast", "Deep South Interior", "Texas"],
    "Deep South Interior": ["Appalachia", "The Carolinas", "Southeastern Coast", "Florida Panhandle & Lower Gulf", "Texas", "Southern Plains"],
    "Texas": ["Florida Panhandle & Lower Gulf", "Deep South Interior", "Southern Plains", "Central Plains", "Southwest", "Northeast Mexico"],
    "Southern Plains": ["Deep South Interior", "Texas", "Central Plains", "Southwest"],
    "Central Plains": ["Texas", "Southern Plains", "Great Lakes", "Upper Midwest", "Mountain West", "Southwest"],
    "Great Lakes": ["New York & New Jersey", "Appalachia", "Central Plains", "Upper Midwest", "Ontario"],
    "Upper Midwest": ["Great Lakes", "Central Plains", "Mountain West", "Prairie Provinces"],
    "Mountain West": ["Central Plains", "Upper Midwest", "Southwest", "Pacific Coast", "Prairie Provinces"],
    "Southwest": ["Texas", "Southern Plains", "Central Plains", "Mountain West", "Pacific Coast", "Northwest Mexico"],
    "Pacific Coast": ["Mountain West", "Southwest", "British Columbia", "Northwest Mexico"],
    "Alaska": ["Northern Territories"],
    "Hawaii": [],

    # Canada Internal
    "Atlantic Canada": ["Quebec", "New England"],
    "Quebec": ["Atlantic Canada", "Ontario", "Northern Territories", "New England", "New York & New Jersey"],
    "Ontario": ["Quebec", "Prairie Provinces", "Northern Territories", "New York & New Jersey", "Great Lakes"],
    "Prairie Provinces": ["Ontario", "British Columbia", "Northern Territories", "Upper Midwest", "Mountain West"],
    "British Columbia": ["Prairie Provinces", "Northern Territories", "Pacific Coast"],
    "Northern Territories": ["Quebec", "Ontario", "Prairie Provinces", "British Columbia", "Alaska"],

    # Mexico Internal
    "Northwest Mexico": ["Northeast Mexico", "Pacific Coast and Sierra Region", "Southwest", "Pacific Coast"],
    "Northeast Mexico": ["Northwest Mexico", "Central Mexico", "Gulf and Southeast Region", "Texas"],
    "Central Mexico": ["Northeast Mexico", "Pacific Coast and Sierra Region", "Gulf and Southeast Region"],
    "Pacific Coast and Sierra Region": ["Northwest Mexico", "Central Mexico", "Gulf and Southeast Region"],
    "Gulf and Southeast Region": ["Northeast Mexico", "Central Mexico", "Pacific Coast and Sierra Region", "Yucatán Peninsula and Southern Highlands"],
    "Yucatán Peninsula and Southern Highlands": ["Gulf and Southeast Region"],

    # UK
    "Greater London": ["South England", "Midlands"],
    "South England": ["Greater London", "Midlands", "Wales & Northern Ireland"],
    "Midlands": ["Greater London", "South England", "North England", "Wales & Northern Ireland"],
    "North England": ["Midlands", "Scotland", "Wales & Northern Ireland"],
    "Scotland": ["North England"],
    "Wales & Northern Ireland": ["South England", "Midlands", "North England", "Dublin"],

    # Germany
    "Bavaria": ["Baden-Württemberg", "Saxony & Thuringia", "Vienna"],
    "Baden-Württemberg": ["Bavaria", "North Rhine-Westphalia", "Zurich & Northeast", "Île-de-France"],
    "North Rhine-Westphalia": ["Baden-Württemberg", "Lower Saxony & Hamburg", "Brussels", "North Holland"],
    "Berlin & Brandenburg": ["Lower Saxony & Hamburg", "Saxony & Thuringia", "Masovia"],
    "Lower Saxony & Hamburg": ["North Rhine-Westphalia", "Berlin & Brandenburg", "Saxony & Thuringia", "Copenhagen"],
    "Saxony & Thuringia": ["Bavaria", "Berlin & Brandenburg", "Lower Saxony & Hamburg", "Bohemia"],

    # France
    "Île-de-France": ["Hauts-de-France & Normandy", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Baden-Württemberg"],
    "Provence-Côte d'Azur": ["Auvergne-Rhône-Alpes", "Occitanie", "Piedmont & Liguria", "Geneva & Romandy"],
    "Auvergne-Rhône-Alpes": ["Île-de-France", "Provence-Côte d'Azur", "Occitanie", "Nouvelle-Aquitaine", "Geneva & Romandy"],
    "Nouvelle-Aquitaine": ["Île-de-France", "Auvergne-Rhône-Alpes", "Occitanie", "Basque Country & Navarra"],
    "Occitanie": ["Provence-Côte d'Azur", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Catalonia"],
    "Hauts-de-France & Normandy": ["Île-de-France", "Brussels", "South England"],

    # Italy
    "Lombardy": ["Piedmont & Liguria", "Veneto", "Tuscany & Emilia-Romagna", "Ticino & Alps"],
    "Lazio": ["Tuscany & Emilia-Romagna", "Southern Italy & Sicily"],
    "Veneto": ["Lombardy", "Tuscany & Emilia-Romagna", "Ljubljana"],
    "Piedmont & Liguria": ["Lombardy", "Tuscany & Emilia-Romagna", "Provence-Côte d'Azur"],
    "Tuscany & Emilia-Romagna": ["Lombardy", "Lazio", "Veneto", "Piedmont & Liguria"],
    "Southern Italy & Sicily": ["Lazio"],

    # Spain
    "Madrid": ["Catalonia", "Andalusia", "Valencia", "Galicia & Castile", "Basque Country & Navarra"],
    "Catalonia": ["Madrid", "Valencia", "Occitanie"],
    "Andalusia": ["Madrid", "Valencia", "Algarve"],
    "Valencia": ["Madrid", "Catalonia", "Andalusia"],
    "Basque Country & Navarra": ["Madrid", "Galicia & Castile", "Nouvelle-Aquitaine"],
    "Galicia & Castile": ["Madrid", "Basque Country & Navarra", "Porto & Norte"],

    # Portugal
    "Lisbon": ["Porto & Norte", "Algarve", "Central Portugal"],
    "Porto & Norte": ["Lisbon", "Central Portugal", "Galicia & Castile"],
    "Algarve": ["Lisbon", "Central Portugal", "Andalusia"],
    "Central Portugal": ["Lisbon", "Porto & Norte", "Algarve"],

    # Netherlands
    "North Holland": ["South Holland", "Eastern Netherlands", "North Rhine-Westphalia"],
    "South Holland": ["North Holland", "Brabant & Limburg", "Eastern Netherlands"],
    "Brabant & Limburg": ["South Holland", "Eastern Netherlands", "Brussels", "North Rhine-Westphalia"],
    "Eastern Netherlands": ["North Holland", "South Holland", "Brabant & Limburg", "Lower Saxony & Hamburg"],

    # Belgium
    "Brussels": ["Flanders", "Wallonia", "North Rhine-Westphalia", "Hauts-de-France & Normandy", "Brabant & Limburg"],
    "Flanders": ["Brussels", "Wallonia", "South Holland"],
    "Wallonia": ["Brussels", "Flanders", "Hauts-de-France & Normandy"],

    # Switzerland
    "Zurich & Northeast": ["Bern & Central", "Ticino & Alps", "Baden-Württemberg"],
    "Bern & Central": ["Zurich & Northeast", "Geneva & Romandy", "Ticino & Alps"],
    "Geneva & Romandy": ["Bern & Central", "Ticino & Alps", "Auvergne-Rhône-Alpes", "Provence-Côte d'Azur"],
    "Ticino & Alps": ["Zurich & Northeast", "Bern & Central", "Geneva & Romandy", "Lombardy"],

    # Austria
    "Vienna": ["Upper & Lower Austria", "Styria & Carinthia", "Bratislava", "Budapest", "Bavaria"],
    "Upper & Lower Austria": ["Vienna", "Tyrol & Vorarlberg", "Styria & Carinthia", "Bohemia"],
    "Tyrol & Vorarlberg": ["Upper & Lower Austria", "Styria & Carinthia", "Bavaria", "Ticino & Alps"],
    "Styria & Carinthia": ["Vienna", "Upper & Lower Austria", "Tyrol & Vorarlberg", "Ljubljana", "Budapest"],

    # Poland
    "Masovia": ["Lesser Poland", "Greater Poland", "Silesia", "Pomerania", "Berlin & Brandenburg", "Minsk"],
    "Lesser Poland": ["Masovia", "Silesia", "Eastern Slovakia", "Western Ukraine"],
    "Greater Poland": ["Masovia", "Silesia", "Pomerania"],
    "Silesia": ["Masovia", "Lesser Poland", "Greater Poland", "Bohemia", "Moravia"],
    "Pomerania": ["Masovia", "Greater Poland", "Berlin & Brandenburg"],

    # Czech Republic
    "Bohemia": ["Moravia", "Czech Silesia", "Saxony & Thuringia", "Bavaria", "Upper & Lower Austria"],
    "Moravia": ["Bohemia", "Czech Silesia", "Bratislava", "Upper & Lower Austria"],
    "Czech Silesia": ["Bohemia", "Moravia", "Silesia"],

    # Slovakia
    "Bratislava": ["Central Slovakia", "Vienna", "Moravia", "Budapest"],
    "Central Slovakia": ["Bratislava", "Eastern Slovakia", "Budapest"],
    "Eastern Slovakia": ["Central Slovakia", "Lesser Poland", "Western Ukraine"],

    # Hungary
    "Budapest": ["Western Transdanubia", "Southern Hungary", "Eastern Hungary", "Vienna", "Bratislava", "Styria & Carinthia", "Zagreb"],
    "Western Transdanubia": ["Budapest", "Southern Hungary", "Styria & Carinthia", "Zagreb"],
    "Southern Hungary": ["Budapest", "Western Transdanubia", "Eastern Hungary", "Vojvodina", "Zagreb"],
    "Eastern Hungary": ["Budapest", "Southern Hungary", "Transylvania"],

    # Romania
    "Bucharest & Wallachia": ["Transylvania", "Moldova", "Dobrogea & Black Sea", "Northern Bulgaria"],
    "Transylvania": ["Bucharest & Wallachia", "Moldova", "Banat & Crișana", "Eastern Hungary"],
    "Moldova": ["Bucharest & Wallachia", "Transylvania", "Banat & Crișana", "Dobrogea & Black Sea", "Chișinău"],
    "Banat & Crișana": ["Transylvania", "Moldova", "Vojvodina"],
    "Dobrogea & Black Sea": ["Bucharest & Wallachia", "Moldova", "Varna & Black Sea"],

    # Bulgaria
    "Sofia": ["Plovdiv & Thrace", "Northern Bulgaria", "Skopje", "Belgrade"],
    "Plovdiv & Thrace": ["Sofia", "Varna & Black Sea", "Northern Bulgaria", "Istanbul"],
    "Varna & Black Sea": ["Plovdiv & Thrace", "Northern Bulgaria", "Dobrogea & Black Sea"],
    "Northern Bulgaria": ["Sofia", "Plovdiv & Thrace", "Varna & Black Sea", "Bucharest & Wallachia"],

    # Greece
    "Attica": ["Central Macedonia", "Peloponnese", "Aegean Islands"],
    "Central Macedonia": ["Attica", "Skopje", "Sofia", "Istanbul"],
    "Peloponnese": ["Attica", "Crete"],
    "Crete": ["Peloponnese", "Aegean Islands"],
    "Aegean Islands": ["Attica", "Crete", "Izmir & Aegean"],

    # Serbia
    "Belgrade": ["Vojvodina", "Šumadija & Western Serbia", "Southern Serbia", "Sofia", "Zagreb"],
    "Vojvodina": ["Belgrade", "Southern Hungary", "Zagreb", "Banat & Crișana"],
    "Šumadija & Western Serbia": ["Belgrade", "Southern Serbia", "Kosovo and Metohija", "Sarajevo", "Podgorica"],
    "Southern Serbia": ["Belgrade", "Šumadija & Western Serbia", "Kosovo and Metohija", "Skopje"],
    "Kosovo and Metohija": ["Šumadija & Western Serbia", "Southern Serbia", "Skopje", "Podgorica", "Tirana"],

    # Croatia
    "Zagreb": ["Dalmatia", "Slavonia", "Istria & Kvarner", "Ljubljana", "Budapest", "Belgrade", "Vojvodina"],
    "Dalmatia": ["Zagreb", "Slavonia", "Istria & Kvarner", "Herzegovina", "Coastal Montenegro"],
    "Slavonia": ["Zagreb", "Dalmatia", "Vojvodina", "Republika Srpska"],
    "Istria & Kvarner": ["Zagreb", "Dalmatia", "Ljubljana", "Coastal Slovenia"],

    # Slovenia
    "Ljubljana": ["Maribor & Styria", "Coastal Slovenia", "Zagreb", "Veneto", "Styria & Carinthia"],
    "Maribor & Styria": ["Ljubljana", "Coastal Slovenia", "Styria & Carinthia"],
    "Coastal Slovenia": ["Ljubljana", "Maribor & Styria", "Istria & Kvarner"],

    # Bosnia and Herzegovina
    "Sarajevo": ["Republika Srpska", "Herzegovina", "Šumadija & Western Serbia", "Dalmatia"],
    "Republika Srpska": ["Sarajevo", "Herzegovina", "Brčko District", "Slavonia", "Belgrade"],
    "Herzegovina": ["Sarajevo", "Republika Srpska", "Dalmatia", "Coastal Montenegro"],
    "Brčko District": ["Republika Srpska", "Slavonia"],

    # Montenegro
    "Podgorica": ["Coastal Montenegro", "Northern Montenegro", "Šumadija & Western Serbia", "Kosovo and Metohija", "Tirana"],
    "Coastal Montenegro": ["Podgorica", "Northern Montenegro", "Dalmatia", "Herzegovina", "Northern Albania"],
    "Northern Montenegro": ["Podgorica", "Coastal Montenegro", "Kosovo and Metohija"],

    # North Macedonia
    "Skopje": ["Western Macedonia", "Eastern Macedonia", "Kosovo and Metohija", "Southern Serbia", "Sofia", "Tirana"],
    "Western Macedonia": ["Skopje", "Eastern Macedonia", "Tirana", "Central Macedonia"],
    "Eastern Macedonia": ["Skopje", "Western Macedonia", "Plovdiv & Thrace"],

    # Albania
    "Tirana": ["Southern Albania", "Northern Albania", "Central Albania & Coast", "Kosovo and Metohija", "Podgorica", "Skopje", "Western Macedonia"],
    "Southern Albania": ["Tirana", "Central Albania & Coast", "Western Macedonia"],
    "Northern Albania": ["Tirana", "Central Albania & Coast", "Coastal Montenegro"],
    "Central Albania & Coast": ["Tirana", "Southern Albania", "Northern Albania"],

    # Ukraine
    "Kyiv": ["Western Ukraine", "Southern Ukraine", "Eastern Ukraine", "Central Ukraine", "Gomel Region"],
    "Western Ukraine": ["Kyiv", "Central Ukraine", "Lesser Poland", "Eastern Slovakia", "Chișinău"],
    "Southern Ukraine": ["Kyiv", "Eastern Ukraine", "Central Ukraine", "Crimea", "Chișinău"],
    "Eastern Ukraine": ["Kyiv", "Southern Ukraine", "Donbas", "Central Ukraine", "Southern Russia"],
    "Donbas": ["Eastern Ukraine", "Crimea", "Southern Russia"],
    "Crimea": ["Southern Ukraine", "Donbas", "Southern Russia"],
    "Central Ukraine": ["Kyiv", "Western Ukraine", "Southern Ukraine", "Eastern Ukraine"],

    # Belarus
    "Minsk": ["Brest Region", "Grodno Region", "Gomel Region", "Vitebsk & Mogilev", "Masovia", "Vilnius"],
    "Brest Region": ["Minsk", "Grodno Region", "Gomel Region", "Masovia"],
    "Grodno Region": ["Minsk", "Brest Region", "Vitebsk & Mogilev", "Vilnius"],
    "Gomel Region": ["Minsk", "Brest Region", "Vitebsk & Mogilev", "Kyiv"],
    "Vitebsk & Mogilev": ["Minsk", "Grodno Region", "Gomel Region", "Moscow", "Saint Petersburg"],

    # Moldova
    "Chișinău": ["Transnistria", "Gagauzia & Southern Moldova", "Moldova", "Southern Ukraine", "Western Ukraine"],
    "Transnistria": ["Chișinău", "Gagauzia & Southern Moldova", "Southern Ukraine"],
    "Gagauzia & Southern Moldova": ["Chișinău", "Transnistria", "Dobrogea & Black Sea"],

    # Lithuania
    "Vilnius": ["Kaunas Region", "Klaipėda & Coast", "Minsk", "Grodno Region", "Riga"],
    "Kaunas Region": ["Vilnius", "Klaipėda & Coast"],
    "Klaipėda & Coast": ["Vilnius", "Kaunas Region", "Kurzeme"],

    # Latvia
    "Riga": ["Kurzeme", "Latgale", "Vilnius", "Tallinn"],
    "Kurzeme": ["Riga", "Latgale", "Klaipėda & Coast"],
    "Latgale": ["Riga", "Kurzeme", "Vitebsk & Mogilev"],

    # Estonia
    "Tallinn": ["Tartu", "Western Estonia", "Riga", "Saint Petersburg"],
    "Tartu": ["Tallinn", "Western Estonia"],
    "Western Estonia": ["Tallinn", "Tartu", "Helsinki & Uusimaa"],

    # Finland
    "Helsinki & Uusimaa": ["Tampere & Pirkanmaa", "Turku & Southwest", "Eastern Finland", "Western Estonia", "Saint Petersburg"],
    "Tampere & Pirkanmaa": ["Helsinki & Uusimaa", "Turku & Southwest", "Eastern Finland", "Lapland & North"],
    "Turku & Southwest": ["Helsinki & Uusimaa", "Tampere & Pirkanmaa", "Stockholm"],
    "Eastern Finland": ["Helsinki & Uusimaa", "Tampere & Pirkanmaa", "Lapland & North", "Saint Petersburg"],
    "Lapland & North": ["Tampere & Pirkanmaa", "Eastern Finland", "Northern Norway", "Norrland"],

    # Sweden
    "Stockholm": ["Gothenburg & West", "Malmö & Skåne", "Central Sweden", "Norrland", "Turku & Southwest", "Helsinki & Uusimaa"],
    "Gothenburg & West": ["Stockholm", "Malmö & Skåne", "Central Sweden", "Oslo"],
    "Malmö & Skåne": ["Stockholm", "Gothenburg & West", "Copenhagen"],
    "Central Sweden": ["Stockholm", "Gothenburg & West", "Norrland", "Trondheim & Central"],
    "Norrland": ["Stockholm", "Central Sweden", "Lapland & North", "Northern Norway", "Trondheim & Central"],

    # Norway
    "Oslo": ["Bergen & West", "Trondheim & Central", "Stavanger & Southwest", "Gothenburg & West"],
    "Bergen & West": ["Oslo", "Trondheim & Central", "Stavanger & Southwest"],
    "Trondheim & Central": ["Oslo", "Bergen & West", "Northern Norway", "Central Sweden", "Norrland"],
    "Stavanger & Southwest": ["Oslo", "Bergen & West"],
    "Northern Norway": ["Trondheim & Central", "Lapland & North", "Norrland", "Arctic Russia"],

    # Denmark
    "Copenhagen": ["Jutland North", "Jutland South", "Malmö & Skåne", "Lower Saxony & Hamburg"],
    "Jutland North": ["Copenhagen", "Jutland South", "Bornholm & Islands"],
    "Jutland South": ["Copenhagen", "Jutland North", "Bornholm & Islands", "Lower Saxony & Hamburg"],
    "Bornholm & Islands": ["Jutland North", "Jutland South"],

    # Ireland
    "Dublin": ["Cork & Munster", "Galway & Connacht", "Ulster (Republic)", "Wales & Northern Ireland"],
    "Cork & Munster": ["Dublin", "Galway & Connacht", "Ulster (Republic)"],
    "Galway & Connacht": ["Dublin", "Cork & Munster", "Ulster (Republic)"],
    "Ulster (Republic)": ["Dublin", "Cork & Munster", "Galway & Connacht"],

    # Iceland
    "Reykjavik": ["Northern Iceland", "Eastern & Southern Iceland"],
    "Northern Iceland": ["Reykjavik", "Eastern & Southern Iceland"],
    "Eastern & Southern Iceland": ["Reykjavik", "Northern Iceland"],

    # Russia
    "Moscow": ["Saint Petersburg", "Southern Russia", "Volga Region", "Ural", "Vitebsk & Mogilev"],
    "Saint Petersburg": ["Moscow", "Arctic Russia", "Tallinn", "Helsinki & Uusimaa", "Eastern Finland"],
    "Southern Russia": ["Moscow", "Volga Region", "North Caucasus", "Eastern Ukraine", "Donbas", "Crimea"],
    "Volga Region": ["Moscow", "Southern Russia", "Ural", "North Caucasus"],
    "Ural": ["Moscow", "Volga Region", "Western Siberia"],
    "Western Siberia": ["Ural", "Eastern Siberia", "Manchuria"],
    "Eastern Siberia": ["Western Siberia", "Far East", "Manchuria", "Beijing"],
    "Far East": ["Eastern Siberia", "Manchuria", "Hokkaido"],
    "North Caucasus": ["Southern Russia", "Volga Region", "Tbilisi", "Eastern Georgia"],
    "Arctic Russia": ["Saint Petersburg", "Northern Norway"],

    # China
    "Beijing": ["Shanghai", "Shandong", "Manchuria", "Xinjiang", "Eastern Siberia"],
    "Shanghai": ["Beijing", "Guangdong", "Zhejiang & Jiangsu", "Hubei"],
    "Guangdong": ["Shanghai", "Zhejiang & Jiangsu", "Hubei", "Sichuan"],
    "Sichuan": ["Guangdong", "Hubei", "Xinjiang", "Tibet"],
    "Zhejiang & Jiangsu": ["Shanghai", "Guangdong", "Shandong", "Hubei"],
    "Shandong": ["Beijing", "Zhejiang & Jiangsu", "Hubei", "Seoul"],
    "Hubei": ["Shanghai", "Guangdong", "Sichuan", "Zhejiang & Jiangsu", "Shandong"],
    "Xinjiang": ["Beijing", "Sichuan", "Tibet", "Mashhad & Khorasan"],
    "Tibet": ["Sichuan", "Xinjiang"],
    "Manchuria": ["Beijing", "Western Siberia", "Eastern Siberia", "Far East", "Seoul"],

    # Japan
    "Tokyo": ["Osaka & Kansai", "Nagoya & Chubu", "Tohoku"],
    "Osaka & Kansai": ["Tokyo", "Nagoya & Chubu", "Kyushu"],
    "Nagoya & Chubu": ["Tokyo", "Osaka & Kansai"],
    "Kyushu": ["Osaka & Kansai", "Busan"],
    "Hokkaido": ["Tohoku", "Far East"],
    "Tohoku": ["Tokyo", "Hokkaido"],

    # South Korea
    "Seoul": ["Busan", "Incheon & Gyeonggi", "Daegu & Gyeongsang", "Daejeon & Chungcheong", "Shandong", "Manchuria"],
    "Busan": ["Seoul", "Daegu & Gyeongsang", "Kyushu"],
    "Incheon & Gyeonggi": ["Seoul", "Daejeon & Chungcheong"],
    "Daegu & Gyeongsang": ["Seoul", "Busan", "Daejeon & Chungcheong"],
    "Daejeon & Chungcheong": ["Seoul", "Incheon & Gyeonggi", "Daegu & Gyeongsang"],

    # Israel
    "Tel Aviv": ["Jerusalem", "Haifa & North", "Negev & South", "Cairo"],
    "Jerusalem": ["Tel Aviv", "Haifa & North", "Negev & South"],
    "Haifa & North": ["Tel Aviv", "Jerusalem"],
    "Negev & South": ["Tel Aviv", "Jerusalem", "Sinai Peninsula"],

    # Georgia
    "Tbilisi": ["Batumi & Adjara", "Kutaisi & Imereti", "Eastern Georgia", "North Caucasus", "Tabriz & Azerbaijan"],
    "Batumi & Adjara": ["Tbilisi", "Kutaisi & Imereti", "Black Sea Region"],
    "Kutaisi & Imereti": ["Tbilisi", "Batumi & Adjara", "Eastern Georgia"],
    "Eastern Georgia": ["Tbilisi", "Kutaisi & Imereti", "North Caucasus"],

    # UAE
    "Dubai": ["Abu Dhabi", "Sharjah & Northern Emirates", "Muscat"],
    "Abu Dhabi": ["Dubai", "Sharjah & Northern Emirates", "Eastern Emirates", "Eastern Province"],
    "Sharjah & Northern Emirates": ["Dubai", "Abu Dhabi", "Eastern Emirates"],
    "Eastern Emirates": ["Abu Dhabi", "Sharjah & Northern Emirates", "Muscat"],

    # Saudi Arabia
    "Riyadh": ["Jeddah & Mecca", "Eastern Province", "Medina", "Asir & South", "Tabuk & Northern Borders"],
    "Jeddah & Mecca": ["Riyadh", "Medina", "Asir & South"],
    "Eastern Province": ["Riyadh", "Kuwait City", "Manama", "Doha", "Abu Dhabi"],
    "Medina": ["Riyadh", "Jeddah & Mecca", "Tabuk & Northern Borders"],
    "Asir & South": ["Riyadh", "Jeddah & Mecca"],
    "Tabuk & Northern Borders": ["Riyadh", "Medina", "Negev & South", "Ankara"],

    # Qatar
    "Doha": ["Al Wakrah & South", "Al Khor & North", "Eastern Province", "Manama"],
    "Al Wakrah & South": ["Doha", "Al Khor & North"],
    "Al Khor & North": ["Doha", "Al Wakrah & South"],

    # Kuwait
    "Kuwait City": ["Ahmadi", "Jahra", "Eastern Province"],
    "Ahmadi": ["Kuwait City", "Jahra"],
    "Jahra": ["Kuwait City", "Ahmadi"],

    # Bahrain
    "Manama": ["Muharraq & Southern Bahrain", "Eastern Province", "Doha"],
    "Muharraq & Southern Bahrain": ["Manama"],

    # Oman
    "Muscat": ["Dhofar", "Al Batinah", "Al Dakhiliyah", "Dubai", "Eastern Emirates"],
    "Dhofar": ["Muscat", "Al Dakhiliyah"],
    "Al Batinah": ["Muscat", "Al Dakhiliyah"],
    "Al Dakhiliyah": ["Muscat", "Dhofar", "Al Batinah"],

    # Turkey
    "Istanbul": ["Ankara", "Izmir & Aegean", "Black Sea Region", "Plovdiv & Thrace", "Central Macedonia"],
    "Ankara": ["Istanbul", "Izmir & Aegean", "Antalya & Mediterranean", "Central Anatolia", "Black Sea Region", "Eastern Anatolia"],
    "Izmir & Aegean": ["Istanbul", "Ankara", "Antalya & Mediterranean", "Aegean Islands"],
    "Antalya & Mediterranean": ["Ankara", "Izmir & Aegean", "Central Anatolia", "Eastern Anatolia"],
    "Eastern Anatolia": ["Ankara", "Antalya & Mediterranean", "Central Anatolia", "Black Sea Region", "Tbilisi", "Tehran", "Tabriz & Azerbaijan"],
    "Black Sea Region": ["Istanbul", "Ankara", "Eastern Anatolia", "Batumi & Adjara"],
    "Central Anatolia": ["Ankara", "Antalya & Mediterranean", "Eastern Anatolia"],

    # Iran
    "Tehran": ["Isfahan", "Mashhad & Khorasan", "Tabriz & Azerbaijan", "Eastern Anatolia"],
    "Isfahan": ["Tehran", "Shiraz & Fars", "Mashhad & Khorasan", "Khuzestan"],
    "Mashhad & Khorasan": ["Tehran", "Isfahan", "Xinjiang"],
    "Shiraz & Fars": ["Isfahan", "Khuzestan"],
    "Tabriz & Azerbaijan": ["Tehran", "Eastern Anatolia", "Tbilisi"],
    "Khuzestan": ["Isfahan", "Shiraz & Fars", "Eastern Province"],

    # Brazil
    "São Paulo": ["Rio de Janeiro", "Minas Gerais", "Paraná & Santa Catarina", "Brasília"],
    "Rio de Janeiro": ["São Paulo", "Minas Gerais", "Bahia & Northeast"],
    "Brasília": ["São Paulo", "Minas Gerais", "Bahia & Northeast", "Amazonas"],
    "Minas Gerais": ["São Paulo", "Rio de Janeiro", "Brasília", "Bahia & Northeast"],
    "Bahia & Northeast": ["Rio de Janeiro", "Brasília", "Minas Gerais", "Amazonas"],
    "Rio Grande do Sul": ["Paraná & Santa Catarina", "Montevideo", "Buenos Aires"],
    "Amazonas": ["Brasília", "Bahia & Northeast", "Bogotá", "Lima", "Caracas"],
    "Paraná & Santa Catarina": ["São Paulo", "Rio Grande do Sul"],

    # Argentina
    "Buenos Aires": ["Córdoba", "Rosario & Santa Fe", "Patagonia", "Montevideo", "Rio Grande do Sul"],
    "Córdoba": ["Buenos Aires", "Mendoza", "Rosario & Santa Fe", "Tucumán & Northwest"],
    "Mendoza": ["Córdoba", "Patagonia", "Santiago", "Valparaíso"],
    "Patagonia": ["Buenos Aires", "Mendoza", "Patagonia & Magallanes"],
    "Rosario & Santa Fe": ["Buenos Aires", "Córdoba", "Asunción"],
    "Tucumán & Northwest": ["Córdoba", "La Paz", "Asunción"],

    # Colombia
    "Bogotá": ["Medellín & Antioquia", "Cali & Valle del Cauca", "Coffee Region", "Amazonas", "Caracas"],
    "Medellín & Antioquia": ["Bogotá", "Colombian Caribbean", "Coffee Region", "Panama City"],
    "Cali & Valle del Cauca": ["Bogotá", "Coffee Region", "Quito"],
    "Colombian Caribbean": ["Medellín & Antioquia", "Maracaibo & Zulia"],
    "Coffee Region": ["Bogotá", "Medellín & Antioquia", "Cali & Valle del Cauca"],

    # Chile
    "Santiago": ["Valparaíso", "Concepción & Biobío", "Atacama & Norte Grande", "Mendoza"],
    "Valparaíso": ["Santiago", "Concepción & Biobío", "Mendoza"],
    "Concepción & Biobío": ["Santiago", "Valparaíso", "Patagonia & Magallanes"],
    "Atacama & Norte Grande": ["Santiago", "La Paz", "Arequipa"],
    "Patagonia & Magallanes": ["Concepción & Biobío", "Patagonia"],

    # Peru
    "Lima": ["Cusco & Highlands", "Arequipa", "Trujillo & North Coast", "Amazonia", "Amazonas"],
    "Cusco & Highlands": ["Lima", "Arequipa", "Amazonia", "La Paz"],
    "Arequipa": ["Lima", "Cusco & Highlands", "Atacama & Norte Grande"],
    "Trujillo & North Coast": ["Lima", "Amazonia", "Guayaquil"],
    "Amazonia": ["Lima", "Cusco & Highlands", "Trujillo & North Coast", "Amazonas"],

    # Venezuela
    "Caracas": ["Maracaibo & Zulia", "Valencia & Central", "Barquisimeto & Lara", "Guayana", "Bogotá", "Amazonas"],
    "Maracaibo & Zulia": ["Caracas", "Valencia & Central", "Colombian Caribbean"],
    "Valencia & Central": ["Caracas", "Maracaibo & Zulia", "Barquisimeto & Lara", "Guayana"],
    "Barquisimeto & Lara": ["Caracas", "Valencia & Central"],
    "Guayana": ["Caracas", "Valencia & Central", "Amazonas"],

    # Ecuador
    "Quito": ["Guayaquil", "Cuenca & Southern Highlands", "Amazonia & Galápagos", "Cali & Valle del Cauca"],
    "Guayaquil": ["Quito", "Cuenca & Southern Highlands", "Trujillo & North Coast"],
    "Cuenca & Southern Highlands": ["Quito", "Guayaquil", "Amazonia & Galápagos"],
    "Amazonia & Galápagos": ["Quito", "Cuenca & Southern Highlands", "Amazonia"],

    # Uruguay
    "Montevideo": ["Punta del Este & Southeast", "Interior", "Buenos Aires", "Rio Grande do Sul"],
    "Punta del Este & Southeast": ["Montevideo", "Interior"],
    "Interior": ["Montevideo", "Punta del Este & Southeast", "Rio Grande do Sul"],

    # Paraguay
    "Asunción": ["Ciudad del Este", "Chaco", "Rosario & Santa Fe", "Tucumán & Northwest", "Minas Gerais"],
    "Ciudad del Este": ["Asunción", "Chaco", "Paraná & Santa Catarina"],
    "Chaco": ["Asunción", "Ciudad del Este", "Santa Cruz"],

    # Bolivia
    "La Paz": ["Santa Cruz", "Cochabamba", "Sucre & Potosí", "Cusco & Highlands", "Atacama & Norte Grande", "Tucumán & Northwest"],
    "Santa Cruz": ["La Paz", "Cochabamba", "Sucre & Potosí", "Chaco", "Amazonas"],
    "Cochabamba": ["La Paz", "Santa Cruz", "Sucre & Potosí"],
    "Sucre & Potosí": ["La Paz", "Santa Cruz", "Cochabamba"],

    # Panama
    "Panama City": ["Colón", "Western Panama", "Medellín & Antioquia", "San José"],
    "Colón": ["Panama City", "Western Panama"],
    "Western Panama": ["Panama City", "Colón", "San José"],

    # Costa Rica
    "San José": ["Costa Rican Caribbean", "Costa Rican Pacific", "Panama City", "Western Panama", "Managua"],
    "Costa Rican Caribbean": ["San José", "Costa Rican Pacific"],
    "Costa Rican Pacific": ["San José", "Costa Rican Caribbean"],

    # Guatemala
    "Guatemala City": ["Quetzaltenango", "Petén", "Pacific Lowlands", "San Salvador", "Tegucigalpa"],
    "Quetzaltenango": ["Guatemala City", "Petén", "Pacific Lowlands"],
    "Petén": ["Guatemala City", "Quetzaltenango"],
    "Pacific Lowlands": ["Guatemala City", "Quetzaltenango"],

    # Honduras
    "Tegucigalpa": ["San Pedro Sula", "Honduran Caribbean", "Guatemala City", "San Salvador", "Managua"],
    "San Pedro Sula": ["Tegucigalpa", "Honduran Caribbean"],
    "Honduran Caribbean": ["Tegucigalpa", "San Pedro Sula"],

    # El Salvador
    "San Salvador": ["Santa Ana", "San Miguel", "Guatemala City", "Tegucigalpa"],
    "Santa Ana": ["San Salvador", "San Miguel"],
    "San Miguel": ["San Salvador", "Santa Ana", "Tegucigalpa"],

    # Nicaragua
    "Managua": ["León & Pacific", "Nicaraguan Caribbean", "San José", "Tegucigalpa"],
    "León & Pacific": ["Managua", "Nicaraguan Caribbean"],
    "Nicaraguan Caribbean": ["Managua", "León & Pacific"],

    # Dominican Republic
    "Santo Domingo": ["Santiago de los Caballeros", "Punta Cana & East", "Puerto Plata & North Coast"],
    "Santiago de los Caballeros": ["Santo Domingo", "Puerto Plata & North Coast"],
    "Punta Cana & East": ["Santo Domingo", "Puerto Plata & North Coast"],
    "Puerto Plata & North Coast": ["Santo Domingo", "Santiago de los Caballeros", "Punta Cana & East"],

    # Egypt
    "Cairo": ["Alexandria", "Luxor & Upper Egypt", "Suez & Canal Zone", "Tel Aviv"],
    "Alexandria": ["Cairo", "Suez & Canal Zone"],
    "Luxor & Upper Egypt": ["Cairo", "Suez & Canal Zone", "Sinai Peninsula"],
    "Suez & Canal Zone": ["Cairo", "Alexandria", "Luxor & Upper Egypt", "Sinai Peninsula"],
    "Sinai Peninsula": ["Luxor & Upper Egypt", "Suez & Canal Zone", "Negev & South"],

    # South Africa
    "Johannesburg & Gauteng": ["Cape Town & Western Cape", "Durban & KwaZulu-Natal", "Pretoria", "Port Elizabeth & Eastern Cape"],
    "Cape Town & Western Cape": ["Johannesburg & Gauteng", "Port Elizabeth & Eastern Cape"],
    "Durban & KwaZulu-Natal": ["Johannesburg & Gauteng", "Pretoria", "Port Elizabeth & Eastern Cape"],
    "Pretoria": ["Johannesburg & Gauteng", "Durban & KwaZulu-Natal"],
    "Port Elizabeth & Eastern Cape": ["Johannesburg & Gauteng", "Cape Town & Western Cape", "Durban & KwaZulu-Natal"],
}


def clear_existing_data(app):
    """Clear all existing country, region, market data for fresh seed."""
    print("Clearing existing data...")
    with app.app_context():
        try:
            if db.engine.dialect.name == 'mysql':
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0"))

            # Clear in order of dependencies
            db.session.execute(db.text("DELETE FROM region_neighbors"))
            db.session.execute(db.text("DELETE FROM country_market_item"))
            db.session.execute(db.text("DELETE FROM gold_market"))
            db.session.execute(db.text("DELETE FROM country_regions"))
            db.session.execute(db.text("DELETE FROM region"))
            db.session.execute(db.text("DELETE FROM country"))

            if db.engine.dialect.name == 'mysql':
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1"))

            db.session.commit()
            print("  Existing data cleared successfully.")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"  Error clearing data: {e}")
            return False


def seed_countries_and_regions(app, skip_existing=True):
    """Seed all countries and their regions."""
    print("\n--- Seeding Countries and Regions ---")

    added_countries = 0
    added_regions = 0
    country_ids = []

    with app.app_context():
        for country_name, flag_code, currency_code, region_names in COUNTRIES_DATA:
            # Check if country exists
            existing_country = db.session.scalar(
                db.select(Country).filter_by(slug=slugify(country_name))
            )

            if existing_country and skip_existing:
                print(f"  Skipping {country_name} - already exists")
                country_ids.append(existing_country.id)
                continue

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
            country_ids.append(country.id)

            # Add regions
            for region_name in region_names:
                existing_region = db.session.scalar(
                    db.select(Region).filter_by(slug=slugify(region_name))
                )

                if existing_region and skip_existing:
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
            print(f"\n  ERROR committing: {e}")
            return False, []

    return True, country_ids


def seed_region_neighbors(app):
    """Seed region neighbor relationships."""
    print("\n--- Seeding Region Neighbors ---")

    added_neighbors = 0

    with app.app_context():
        all_regions = db.session.scalars(db.select(Region)).all()
        region_map = {r.slug: r for r in all_regions}

        for region_name, neighbor_names in REGION_NEIGHBORS.items():
            region_slug = slugify(region_name)
            region = region_map.get(region_slug)

            if not region:
                region = db.session.scalar(db.select(Region).filter_by(name=region_name))
                if not region:
                    continue

            for neighbor_name in neighbor_names:
                neighbor_slug = slugify(neighbor_name)
                neighbor = region_map.get(neighbor_slug)

                if not neighbor:
                    neighbor = db.session.scalar(db.select(Region).filter_by(name=neighbor_name))
                    if not neighbor:
                        continue

                # Check if already neighbors
                if neighbor not in region.neighbors:
                    region.neighbors.append(neighbor)
                    added_neighbors += 1

        try:
            db.session.commit()
            print(f"  Successfully added {added_neighbors} neighbor relationships")
        except Exception as e:
            db.session.rollback()
            print(f"  ERROR: {e}")
            return False

    return True


def seed_gold_markets(app, country_ids=None):
    """Seed gold markets for countries."""
    print("\n--- Seeding Gold Markets ---")

    added_count = 0

    with app.app_context():
        if country_ids:
            countries = db.session.scalars(
                db.select(Country).filter(Country.id.in_(country_ids))
            ).all()
        else:
            countries = db.session.scalars(db.select(Country)).all()

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
            print(f"  ERROR: {e}")
            return False

    return True


def seed_resource_markets(app, country_ids=None):
    """Seed resource markets for countries."""
    print("\n--- Seeding Resource Markets ---")

    initial_price = Decimal('5.00')
    added_count = 0

    with app.app_context():
        all_resources = db.session.scalars(db.select(Resource)).all()

        if not all_resources:
            print("  No resources found. Run seed_resources.py first.")
            return False

        if country_ids:
            countries = db.session.scalars(
                db.select(Country).filter(Country.id.in_(country_ids))
            ).all()
        else:
            countries = db.session.scalars(db.select(Country)).all()

        for country in countries:
            print(f"    Adding market items for: {country.name}")
            for resource in all_resources:
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
            print(f"  ERROR: {e}")
            return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("TACTIZEN - Countries Seed Script")
    print("=" * 60)

    reset_mode = "--reset" in sys.argv
    if reset_mode:
        print("\nRESET MODE: Will clear ALL existing data and reseed from scratch!")
    else:
        print("\nNormal mode: Will skip existing countries/regions")

    print(f"Total countries to seed: {len(COUNTRIES_DATA)}")
    print("=" * 60)

    flask_app = create_app()

    # Step 0: Clear data if reset mode
    if reset_mode:
        if not clear_existing_data(flask_app):
            print("\nFailed to clear existing data. Aborting.")
            sys.exit(1)

    # Step 1: Seed countries and regions
    success, country_ids = seed_countries_and_regions(flask_app, skip_existing=not reset_mode)
    if not success:
        print("\nFailed to seed countries. Aborting.")
        sys.exit(1)

    # Step 2: Seed region neighbors
    if not seed_region_neighbors(flask_app):
        print("\nFailed to seed neighbors. Continuing anyway...")

    # Step 3: Seed gold markets
    if not seed_gold_markets(flask_app, country_ids if not reset_mode else None):
        print("\nFailed to seed gold markets. Continuing anyway...")

    # Step 4: Seed resource markets
    if not seed_resource_markets(flask_app, country_ids if not reset_mode else None):
        print("\nFailed to seed resource markets. Continuing anyway...")

    print("\n" + "=" * 60)
    print("Seeding Complete!")
    print(f"Total countries: {len(COUNTRIES_DATA)}")
    print("=" * 60)
