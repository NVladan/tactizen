// This file contains basic information about countries
// In a production environment, this would typically be fetched from an API

const countriesData = {
    // Sample data structure for countries
    // The keys correspond to the ISO 3166-1 alpha-3 country codes
    "USA": {
        name: "United States",
        capital: "Washington D.C.",
        population: "331 million",
        area: "9,833,517 km²",
        region: "North America",
        languages: ["English"],
        currency: "US Dollar (USD)"
    },
    "CAN": {
        name: "Canada",
        capital: "Ottawa",
        population: "38 million",
        area: "9,984,670 km²",
        region: "North America",
        languages: ["English", "French"],
        currency: "Canadian Dollar (CAD)"
    },
    "MEX": {
        name: "Mexico",
        capital: "Mexico City",
        population: "126 million",
        area: "1,964,375 km²",
        region: "North America",
        languages: ["Spanish"],
        currency: "Mexican Peso (MXN)"
    },
    "BRA": {
        name: "Brazil",
        capital: "Brasília",
        population: "213 million",
        area: "8,515,767 km²",
        region: "South America",
        languages: ["Portuguese"],
        currency: "Brazilian Real (BRL)"
    },
    "ARG": {
        name: "Argentina",
        capital: "Buenos Aires",
        population: "45 million",
        area: "2,780,400 km²",
        region: "South America",
        languages: ["Spanish"],
        currency: "Argentine Peso (ARS)"
    },
    "GBR": {
        name: "United Kingdom",
        capital: "London",
        population: "67 million",
        area: "242,495 km²",
        region: "Europe",
        languages: ["English"],
        currency: "Pound Sterling (GBP)"
    },
    "FRA": {
        name: "France",
        capital: "Paris",
        population: "67 million",
        area: "551,695 km²",
        region: "Europe",
        languages: ["French"],
        currency: "Euro (EUR)"
    },
    "DEU": {
        name: "Germany",
        capital: "Berlin",
        population: "83 million",
        area: "357,022 km²",
        region: "Europe",
        languages: ["German"],
        currency: "Euro (EUR)"
    },
    "ITA": {
        name: "Italy",
        capital: "Rome",
        population: "60 million",
        area: "301,340 km²",
        region: "Europe",
        languages: ["Italian"],
        currency: "Euro (EUR)"
    },
    "ESP": {
        name: "Spain",
        capital: "Madrid",
        population: "47 million",
        area: "505,990 km²",
        region: "Europe",
        languages: ["Spanish"],
        currency: "Euro (EUR)"
    },
    "RUS": {
        name: "Russia",
        capital: "Moscow",
        population: "144 million",
        area: "17,098,246 km²",
        region: "Europe/Asia",
        languages: ["Russian"],
        currency: "Russian Ruble (RUB)"
    },
    "CHN": {
        name: "China",
        capital: "Beijing",
        population: "1.4 billion",
        area: "9,596,960 km²",
        region: "Asia",
        languages: ["Mandarin Chinese"],
        currency: "Renminbi (Yuan, CNY)"
    },
    "JPN": {
        name: "Japan",
        capital: "Tokyo",
        population: "126 million",
        area: "377,975 km²",
        region: "Asia",
        languages: ["Japanese"],
        currency: "Japanese Yen (JPY)"
    },
    "IND": {
        name: "India",
        capital: "New Delhi",
        population: "1.38 billion",
        area: "3,287,263 km²",
        region: "Asia",
        languages: ["Hindi", "English"],
        currency: "Indian Rupee (INR)"
    },
    "AUS": {
        name: "Australia",
        capital: "Canberra",
        population: "25 million",
        area: "7,692,024 km²",
        region: "Oceania",
        languages: ["English"],
        currency: "Australian Dollar (AUD)"
    },
    "NZL": {
        name: "New Zealand",
        capital: "Wellington",
        population: "5 million",
        area: "270,467 km²",
        region: "Oceania",
        languages: ["English", "Māori"],
        currency: "New Zealand Dollar (NZD)"
    },
    "ZAF": {
        name: "South Africa",
        capital: "Pretoria, Cape Town, Bloemfontein",
        population: "59 million",
        area: "1,221,037 km²",
        region: "Africa",
        languages: ["Afrikaans", "English", "Zulu", "Xhosa"],
        currency: "South African Rand (ZAR)"
    },
    "EGY": {
        name: "Egypt",
        capital: "Cairo",
        population: "102 million",
        area: "1,002,450 km²",
        region: "Africa",
        languages: ["Arabic"],
        currency: "Egyptian Pound (EGP)"
    },
    "NGA": {
        name: "Nigeria",
        capital: "Abuja",
        population: "206 million",
        area: "923,768 km²",
        region: "Africa",
        languages: ["English"],
        currency: "Nigerian Naira (NGN)"
    },
    "KEN": {
        name: "Kenya",
        capital: "Nairobi",
        population: "53 million",
        area: "580,367 km²",
        region: "Africa",
        languages: ["Swahili", "English"],
        currency: "Kenyan Shilling (KES)"
    }
    // More countries would be added in a real application
};

// Export for use in other scripts
if (typeof module !== 'undefined') {
    module.exports = countriesData;
}
