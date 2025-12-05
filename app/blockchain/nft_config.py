"""
NFT Configuration for Tactizen GamePlay NFT System
Defines all NFT types, categories, tiers, and bonus values
"""

from enum import Enum
from typing import Dict, List, Tuple

# NFT Types
class NFTType(str, Enum):
    PLAYER = "player"
    COMPANY = "company"
    VEHICLE = "vehicle"  # NEW: Vehicle NFTs

# Player NFT Categories
class PlayerNFTCategory(str, Enum):
    COMBAT_BOOST = "combat_boost"
    ENERGY_REGEN = "energy_regen"
    WELLNESS_REGEN = "wellness_regen"
    MILITARY_TUTOR = "military_tutor"
    TRAVEL_DISCOUNT = "travel_discount"
    STORAGE_INCREASE = "storage_increase"

# Company NFT Categories
class CompanyNFTCategory(str, Enum):
    PRODUCTION_BOOST = "production_boost"
    MATERIAL_EFFICIENCY = "material_efficiency"
    UPGRADE_DISCOUNT = "upgrade_discount"
    SPEED_BOOST = "speed_boost"
    ANDROID_WORKER = "android_worker"
    TAX_BREAKS = "tax_breaks"

# Tier Names
class Tier(Enum):
    Q1 = 1  # Common
    Q2 = 2  # Uncommon
    Q3 = 3  # Rare
    Q4 = 4  # Epic
    Q5 = 5  # Legendary

# Tier Rarity Names
TIER_RARITY_NAMES = {
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Epic",
    5: "Legendary"
}

# Player NFT Bonus Values (tier -> bonus_value)
PLAYER_NFT_BONUSES = {
    PlayerNFTCategory.COMBAT_BOOST: {
        1: 5,    # Q1: +5% damage
        2: 15,   # Q2: +15% damage
        3: 25,   # Q3: +25% damage
        4: 40,   # Q4: +40% damage
        5: 60    # Q5: +60% damage
    },
    PlayerNFTCategory.ENERGY_REGEN: {
        1: 2,    # Q1: +2/hr
        2: 5,    # Q2: +5/hr
        3: 10,   # Q3: +10/hr
        4: 20,   # Q4: +20/hr
        5: 35    # Q5: +35/hr
    },
    PlayerNFTCategory.WELLNESS_REGEN: {
        1: 2,    # Q1: +2/hr
        2: 5,    # Q2: +5/hr
        3: 10,   # Q3: +10/hr
        4: 20,   # Q4: +20/hr
        5: 35    # Q5: +35/hr
    },
    PlayerNFTCategory.MILITARY_TUTOR: {
        1: 20,   # Q1: +20% Military Rank XP
        2: 40,   # Q2: +40% Military Rank XP
        3: 60,   # Q3: +60% Military Rank XP
        4: 80,   # Q4: +80% Military Rank XP
        5: 100   # Q5: +100% Military Rank XP (double)
    },
    PlayerNFTCategory.TRAVEL_DISCOUNT: {
        1: 20,   # Q1: 20% discount (0.8 Gold / 40 Energy)
        2: 40,   # Q2: 40% discount (0.6 Gold / 30 Energy)
        3: 60,   # Q3: 60% discount (0.4 Gold / 20 Energy)
        4: 80,   # Q4: 80% discount (0.2 Gold / 10 Energy)
        5: 100   # Q5: 100% discount (Free / 0 Energy)
    },
    PlayerNFTCategory.STORAGE_INCREASE: {
        1: 1000,  # Q1: +1000 storage
        2: 2000,  # Q2: +2000 storage
        3: 3000,  # Q3: +3000 storage
        4: 4000,  # Q4: +4000 storage
        5: 5000   # Q5: +5000 storage
    }
}

# Company NFT Bonus Values (tier -> bonus_value)
COMPANY_NFT_BONUSES = {
    CompanyNFTCategory.PRODUCTION_BOOST: {
        1: 10,   # Q1: +10% production
        2: 20,   # Q2: +20% production
        3: 35,   # Q3: +35% production
        4: 55,   # Q4: +55% production
        5: 80    # Q5: +80% production
    },
    CompanyNFTCategory.MATERIAL_EFFICIENCY: {
        1: 5,    # Q1: -5% materials
        2: 15,   # Q2: -15% materials
        3: 25,   # Q3: -25% materials
        4: 40,   # Q4: -40% materials
        5: 60    # Q5: -60% materials
    },
    CompanyNFTCategory.UPGRADE_DISCOUNT: {
        1: 5,    # Q1: -5% upgrade cost
        2: 15,   # Q2: -15% upgrade cost
        3: 25,   # Q3: -25% upgrade cost
        4: 40,   # Q4: -40% upgrade cost
        5: 50    # Q5: -50% upgrade cost (reduced from 60% to avoid exploit)
    },
    CompanyNFTCategory.SPEED_BOOST: {
        1: 10,   # Q1: -10% PP required
        2: 20,   # Q2: -20% PP required
        3: 30,   # Q3: -30% PP required
        4: 45,   # Q4: -45% PP required
        5: 65    # Q5: -65% PP required
    },
    CompanyNFTCategory.ANDROID_WORKER: {
        1: 1,    # Q1: Skill Level 1
        2: 2,    # Q2: Skill Level 2
        3: 3,    # Q3: Skill Level 3
        4: 4,    # Q4: Skill Level 4
        5: 5     # Q5: Skill Level 5
    },
    CompanyNFTCategory.TAX_BREAKS: {
        1: 20,   # Q1: -20% tax
        2: 40,   # Q2: -40% tax
        3: 60,   # Q3: -60% tax
        4: 80,   # Q4: -80% tax
        5: 100   # Q5: -100% tax (no tax)
    }
}

# ZEN Token Prices for NFT Purchase (tier -> price)
# Only Q1 is purchasable - higher tiers must be crafted via 3:1 burning
NFT_PURCHASE_PRICES = {
    1: 1,       # Q1: 1 ZEN (only tier available for purchase)
    2: None,    # Q2: Not purchasable (craft only)
    3: None,    # Q3: Not purchasable (craft only)
    4: None,    # Q4: Not purchasable (craft only)
    5: None     # Q5: Not purchasable (craft only)
}

# Drop Rates (tier -> drop_weight)
# Only Q1-Q3 can drop from loot
NFT_DROP_WEIGHTS = {
    1: 70,  # 70% of drops are Q1
    2: 25,  # 25% of drops are Q2
    3: 5    # 5% of drops are Q3
}

# Drop Chances by Source (source -> percentage)
# DISABLED: No drops for now
NFT_DROP_CHANCES = {
    'work': 0.0,         # DISABLED
    'training': 0.0,     # DISABLED
    'study': 0.0,        # DISABLED
    'battle_win': 0.0,   # DISABLED
    'daily_login': 0.0   # DISABLED
}

# Company NFT Slot Counts by Quality
COMPANY_NFT_SLOTS = {
    1: 1,  # Q1 company: 1 slot
    2: 1,  # Q2 company: 1 slot
    3: 2,  # Q3 company: 2 slots
    4: 2,  # Q4 company: 2 slots
    5: 3   # Q5 company: 3 slots
}

# Player NFT Slot Count (always 3)
PLAYER_NFT_SLOTS = 3

# NFT Display Names
PLAYER_NFT_NAMES = {
    PlayerNFTCategory.COMBAT_BOOST: {
        1: "Warrior's Token",
        2: "Soldier's Badge",
        3: "Warrior's Blade",
        4: "Champion's Crest",
        5: "Legendary Warlord's Crown"
    },
    PlayerNFTCategory.ENERGY_REGEN: {
        1: "Energy Drink Pack",
        2: "Caffeine Supplements",
        3: "Nutrient IV Drip",
        4: "Bio-Stimulant Injector",
        5: "Neural Energizer Implant"
    },
    PlayerNFTCategory.WELLNESS_REGEN: {
        1: "First Aid Kit",
        2: "Medical Subscription",
        3: "Health Monitor Device",
        4: "Regeneration Pod Access",
        5: "Advanced Med-Bay Pass"
    },
    PlayerNFTCategory.MILITARY_TUTOR: {
        1: "Drill Sergeant's Manual",
        2: "Combat Instructor's Codex",
        3: "War Academy Tome",
        4: "General's Strategy Compendium",
        5: "Art of War Masterwork"
    },
    PlayerNFTCategory.TRAVEL_DISCOUNT: {
        1: "Transit Pass",
        2: "Frequent Flyer Card",
        3: "Priority Travel License",
        4: "VIP Transport Pass",
        5: "Universal Travel Clearance"
    },
    PlayerNFTCategory.STORAGE_INCREASE: {
        1: "Storage Locker Rental",
        2: "Cargo Container Lease",
        3: "Warehouse Access Card",
        4: "Distribution Center Pass",
        5: "Logistics Hub License"
    }
}

COMPANY_NFT_NAMES = {
    CompanyNFTCategory.PRODUCTION_BOOST: {
        1: "Basic Assembly Tool",
        2: "Production Enhancer",
        3: "Industrial Optimizer",
        4: "Advanced Automation System",
        5: "Quantum Production Matrix"
    },
    CompanyNFTCategory.MATERIAL_EFFICIENCY: {
        1: "Material Saver",
        2: "Resource Optimizer",
        3: "Efficient Processor",
        4: "Nano-Material Converter",
        5: "Zero-Waste Recycler"
    },
    CompanyNFTCategory.UPGRADE_DISCOUNT: {
        1: "Budget Planner",
        2: "Cost Reducer",
        3: "Investment Optimizer",
        4: "Financial Genius AI",
        5: "Government Subsidy Grant"
    },
    CompanyNFTCategory.SPEED_BOOST: {
        1: "Quick Assembly Kit",
        2: "Speed Booster",
        3: "Rapid Production Unit",
        4: "Parallel Assembly Line",
        5: "Hyper-Automation System"
    },
    CompanyNFTCategory.ANDROID_WORKER: {
        1: "Labor Droid Mk-I",
        2: "Labor Droid Mk-II",
        3: "Labor Droid Mk-III",
        4: "Labor Droid Mk-IV",
        5: "Labor Droid Mk-V"
    },
    CompanyNFTCategory.TAX_BREAKS: {
        1: "Tax Consultant Contract",
        2: "Corporate Accountant",
        3: "Tax Optimization Firm",
        4: "Offshore Holdings License",
        5: "Tax Exemption Certificate"
    }
}

def get_nft_bonus_value(nft_type: str, category: str, tier: int) -> int:
    """Get bonus value for a specific NFT type, category, and tier"""
    if nft_type == NFTType.PLAYER:
        return PLAYER_NFT_BONUSES.get(PlayerNFTCategory(category), {}).get(tier, 0)
    elif nft_type == NFTType.COMPANY:
        return COMPANY_NFT_BONUSES.get(CompanyNFTCategory(category), {}).get(tier, 0)
    return 0

def get_nft_name(nft_type: str, category: str, tier: int) -> str:
    """Get display name for a specific NFT"""
    rarity = TIER_RARITY_NAMES.get(tier, "Unknown")

    if nft_type == NFTType.PLAYER:
        base_name = PLAYER_NFT_NAMES.get(PlayerNFTCategory(category), {}).get(tier, "Unknown NFT")
    elif nft_type == NFTType.COMPANY:
        base_name = COMPANY_NFT_NAMES.get(CompanyNFTCategory(category), {}).get(tier, "Unknown NFT")
    else:
        base_name = "Unknown NFT"

    return f"{base_name} - {rarity}"

def get_nft_description(nft_type: str, category: str, tier: int) -> str:
    """Get description for a specific NFT"""
    bonus = get_nft_bonus_value(nft_type, category, tier)
    rarity = TIER_RARITY_NAMES.get(tier, "Unknown")

    # Category-specific descriptions
    if category == PlayerNFTCategory.COMBAT_BOOST or category == "combat_boost":
        return f"A {rarity.lower()} item that increases your combat damage by {bonus}%"
    elif category == PlayerNFTCategory.ENERGY_REGEN or category == "energy_regen":
        return f"A {rarity.lower()} item that regenerates {bonus} energy per hour"
    elif category == PlayerNFTCategory.WELLNESS_REGEN or category == "wellness_regen":
        return f"A {rarity.lower()} item that regenerates {bonus} wellness per hour"
    elif category == PlayerNFTCategory.MILITARY_TUTOR or category == "military_tutor":
        return f"A {rarity.lower()} training guide that increases Military Rank XP gained by {bonus}%"
    elif category == PlayerNFTCategory.TRAVEL_DISCOUNT or category == "travel_discount":
        if tier == 5:
            return f"A {rarity.lower()} authorization that eliminates all travel costs"
        gold_cost = round(1.0 * (100 - bonus) / 100, 1)
        energy_cost = int(50 * (100 - bonus) / 100)
        return f"A {rarity.lower()} pass that reduces travel costs to {gold_cost} Gold / {energy_cost} Energy"
    elif category == PlayerNFTCategory.STORAGE_INCREASE or category == "storage_increase":
        return f"A {rarity.lower()} storage contract that increases capacity by {bonus:,} units"
    elif category == CompanyNFTCategory.PRODUCTION_BOOST or category == "production_boost":
        return f"A {rarity.lower()} system that boosts production output by {bonus}%"
    elif category == CompanyNFTCategory.MATERIAL_EFFICIENCY or category == "material_efficiency":
        return f"A {rarity.lower()} processor that reduces material consumption by {bonus}%"
    elif category == CompanyNFTCategory.UPGRADE_DISCOUNT or category == "upgrade_discount":
        return f"A {rarity.lower()} optimizer that reduces upgrade costs by {bonus}%"
    elif category == CompanyNFTCategory.SPEED_BOOST or category == "speed_boost":
        return f"A {rarity.lower()} accelerator that reduces production points required by {bonus}%"
    elif category == CompanyNFTCategory.ANDROID_WORKER or category == "android_worker":
        return f"A {rarity.lower()} android unit with Skill Level {bonus}. Works 12-hour shifts autonomously."
    elif category == CompanyNFTCategory.TAX_BREAKS or category == "tax_breaks":
        if tier == 5:
            return f"A {rarity.lower()} exemption that eliminates all company taxes on withdrawals and sales"
        return f"A {rarity.lower()} financial service that reduces company taxes by {bonus}%"

    return f"A {rarity.lower()} NFT with {bonus} bonus"

def get_all_player_categories() -> List[str]:
    """Get list of all player NFT categories"""
    return [cat.value for cat in PlayerNFTCategory]

def get_all_company_categories() -> List[str]:
    """Get list of all company NFT categories"""
    return [cat.value for cat in CompanyNFTCategory]

def get_purchase_price(tier: int) -> int:
    """Get ZEN token price for purchasing NFT of given tier"""
    return NFT_PURCHASE_PRICES.get(tier, 0)

def get_company_slot_count(company_quality: int) -> int:
    """Get number of NFT slots for a company based on its quality"""
    return COMPANY_NFT_SLOTS.get(company_quality, 1)

def can_upgrade_tier(tier: int) -> bool:
    """Check if NFTs of this tier can be upgraded"""
    return tier < 5

def get_upgrade_tier(current_tier: int) -> int:
    """Get the next tier when upgrading"""
    if can_upgrade_tier(current_tier):
        return current_tier + 1
    return current_tier

# IPFS Metadata URIs for NFTs
# Format: NFT_METADATA_URIS[nft_type][category][tier] = 'ipfs://...'
# Generated 2024-12-03 and uploaded to Pinata IPFS
NFT_METADATA_URIS = {
    'player': {
        'combat_boost': {
            1: 'ipfs://QmWr24Bb2Z7vmFj6n4JWtVgs5q4Ve1uwgXkab8Z8tWy51t',
            2: 'ipfs://QmNd7huveQaRYJHQ9rEqqX9EVoa5mmDJNQ6CiRbiLxoEcb',
            3: 'ipfs://QmRgQ1fVNs3kTvVQCVumTSSKQvbeKGaLNPQdh5kdTepZ6v',
            4: 'ipfs://QmZM4GXxGv5pNYiPMed8KetsUmp6R43s2m7BmT7vNKrP8M',
            5: 'ipfs://QmfUpPb8BCus62TS5tkzyZbyC5KwF9tyydbUfeUjE5fVk1',
        },
        'energy_regen': {
            1: 'ipfs://QmZR4PrejTPfuHACSsi3HRDpwvZtNMWh4vwefy9E34htS2',
            2: 'ipfs://QmSbYNEihGqQfQk4aWcmo3Gq6giUFQ2rNqEo2jG7Zrr4Rn',
            3: 'ipfs://QmUQ9nAqR1GJqGRpgLSkTtLtzSMzA9tp7zBDoPMP8k2Wgj',
            4: 'ipfs://QmTgWhb2toVYxUwBvvauSKNdKCVNgJdqiWykPEZE15Wjew',
            5: 'ipfs://QmTH8cFB1MjW59Jup2G3wJ1jfd431MGAzRzTLrTaurHGUc',
        },
        'wellness_regen': {
            1: 'ipfs://Qmd5WmEeLP5666KFPKtT9DXvesx6m8j5XkjMSUoyQh51tA',
            2: 'ipfs://QmZwsX21btbbZGisWZ1nwXfgYbvRucQP2V2JiBPJXDvX9n',
            3: 'ipfs://QmbdPKLqoN2FzkdBGqqa7bbfKZpH4BV1xKTSWwgKeGCfgT',
            4: 'ipfs://QmSChSN1ZvdZiKsB32umzxp2r3JiCwNbqM1VzbM9SW1qZc',
            5: 'ipfs://QmUu8e27b7XD4GPrf6wTjWPL9qTqroStsntN7W6wNbMEQy',
        },
        'military_tutor': {
            1: 'ipfs://QmWPFAnucZ7cHEC113BUZxpnrt6AqnS1yqBEcNGGoH8FcP',
            2: 'ipfs://QmSXcr6uhLyasDB53i9QMdMkJdMfCXrKqWXLC9fTnygiKS',
            3: 'ipfs://QmdtnoDUGXdoSNw1VNUvQ9W7dgJAfTWwiFhrAGeiHQpWLN',
            4: 'ipfs://QmXv8hvsqb9E71WVRJxovV9v13H1xBabrWvoxJfNcpAxcW',
            5: 'ipfs://QmV6dTbMZCMDwifZTf1qUPWygTtaLnrdue99aT1RQ6Sc79',
        },
        'travel_discount': {
            1: 'ipfs://QmQzP7B27C6uHwubFJqdpJPj1Ae91on3EnWAcun9aPQT6Y',
            2: 'ipfs://QmPSzznzwMcRcWVCqg28DKeRRGpDLQgmga47GFMpqE6qkd',
            3: 'ipfs://QmX9BTYyPZixhdeNKgeb2LyVTMW8BtVhRwqibSCvsi7XZV',
            4: 'ipfs://Qme76tic8q75GMbzRxo8QFhTSL7btGqJfgAoFTDnb6hE8B',
            5: 'ipfs://QmYkdaXvwJG3rpBnUqhzjwfLBk5fLVwtyBttx5TvnDn3ca',
        },
        'storage_increase': {
            1: 'ipfs://QmXXxybE1ULJ47y89wqc9eSq85AhGmG6FzBLngHbqpdDWT',
            2: 'ipfs://Qma3w7AoPFQynsnHRPp3dSRKupKQhQ8RFtcCw5xS9eNHh9',
            3: 'ipfs://QmX8AZ6YUswM6cjdSSncZnTjQpSNxVBceuhZ6AfZxkw3JC',
            4: 'ipfs://QmXMtkHjKdouck1eNZ1Mrb9g231Nf87J4pdi8a7fr3cVH2',
            5: 'ipfs://QmNuasXu4Wvge5kUSQFbPZyBTEyTBydB2v7n52NeSqsvo2',
        },
    },
    'company': {
        'production_boost': {
            1: 'ipfs://QmY1BWAQzX9NgpxAr4VTTJFgQhxo3vwMFnnEcMFTCHh5BF',
            2: 'ipfs://QmNqdT1hNLfKEaGNawacqHYAQk4W4en4WmtCXA3qaD4sEH',
            3: 'ipfs://QmbzFsw8g3W3LtKgih9FjgVScupGaWaUAZ2ZdgttrJabXf',
            4: 'ipfs://QmXmipubAzVtqvMVzNkwBYSPvBksZWDJ6MoPNqp44Y6ujC',
            5: 'ipfs://QmVBJ5A9XLyjmfaGnTEXpKHL8m2mezSkvNkw24f1zEjNRo',
        },
        'material_efficiency': {
            1: 'ipfs://QmUPyHz1U7Cxcs76tDWbGHVxcukUNWf1G9V1S6hD6jF3uQ',
            2: 'ipfs://QmXfyuj3YEiwdXASGDpkTrC1CtQZdUgVyjy77Bc2Xs8FUL',
            3: 'ipfs://Qmc43Ba9g3as1TdH5CVUpGWqPCEdLj5ESG27tR3Esss1E9',
            4: 'ipfs://QmcvTxdfqzhhchFoJLdYbsAb1r2SoDYU8wJkrsFB2R47o9',
            5: 'ipfs://Qme48XhGkuBMeLeQZaj5pkyMitSdk9WAzRfcqfDnMRJ29x',
        },
        'upgrade_discount': {
            1: 'ipfs://QmVyEsktKhgrf1AEHxhzW3giRJdD9wnimW3ie3uQ7Fm76M',
            2: 'ipfs://QmPWLPzQmUKcdXj4naMBCdWNdBotW1F44DgesETEfxGx2j',
            3: 'ipfs://QmctzCFbwZcUpiQP8T7PsbkSqfTmi8vzyHM321o9x94uTY',
            4: 'ipfs://QmZCY43K4gEW12Rk4qbXyodgnKfSvTeEtqnBiTnAy5rqWe',
            5: 'ipfs://Qmd75J49C166LJx9B5KWeqaZxfBM8DLTzd7ehvdn1EJQUB',
        },
        'speed_boost': {
            1: 'ipfs://Qmd7sWYMtDqtEdtb59AYENECBwTPK4zFHGLNY7MKUK1uky',
            2: 'ipfs://QmcsCydujtmGNBaAaTVUC98cqwQP4VTWonN9KyNKXK3tFb',
            3: 'ipfs://QmRa8bQfDpcD9D4QMcmbakPE7u1EvK9Hs9tuwAgd6gfbjF',
            4: 'ipfs://QmZaEbwDDKDFSGsVzQWAG6AqDcz3ABCQyNt9rjHjg6777K',
            5: 'ipfs://QmYQ94Rmzzy213ooFD5782WMgW8y1fN7f9GQzhoDaahcrY',
        },
        'android_worker': {
            1: 'ipfs://QmfS6cB6YTrot9gzPtfArZKXX3Cuk6qkUsxxpCa8kvFR8B',
            2: 'ipfs://Qmf4sU3NvcvakueyXbzAAxwJxX5QRXg1MGbN86ks1ZuohR',
            3: 'ipfs://QmdiykTcFBVUkTFr6ukSHba5WuTvfTeGcjrMye4bpULYoY',
            4: 'ipfs://QmXFUqh5qsZnR2hzrCrdomsD4BPbCNEk3JYihWtTauqD1h',
            5: 'ipfs://QmY7PAqpobezKRmek3VsysUYTUrvXozaqcLGCAeUYZxufm',
        },
        'tax_breaks': {
            1: 'ipfs://QmUdwZZyrT2qTLqgAjJLewSMviBE3ZnCLih7mUTSWy839R',
            2: 'ipfs://QmbS6NPPN2SYw9h43ixaz6HS8GeTJqLvgwj7MAH94n866E',
            3: 'ipfs://QmVPbQEsYX41x1uwbLQPi7xBThS4V7BfJpwWmbVKiLw85b',
            4: 'ipfs://QmQiLqYb4wrgbnp5UABPqMZNH76JUnu3pU6799j1bBqJMf',
            5: 'ipfs://QmZ4uPDnM1YGL1uNfnTtD84TV6JdnZw2Te8NTNswtduePE',
        },
    },
}

def get_nft_metadata_uri(nft_type: str, category: str, tier: int) -> str:
    """Get IPFS metadata URI for a specific NFT"""
    return NFT_METADATA_URIS.get(nft_type, {}).get(category, {}).get(tier, '')


def get_nft_image_url(nft_type: str, category: str, tier: int) -> str:
    """
    Get the HTTP gateway URL for the NFT image.
    Constructs Pinata gateway URL for easy display in browsers.
    """
    # Image IPFS CIDs - uploaded 2024-12-03
    IMAGE_CIDS = {
        'player': {
            'combat_boost': {
                1: 'QmdNdmuAuE1ukzbSFKvU6RwBNrRucognKC2nGK4ST1XHqt',
                2: 'QmS6WMaEmQx2XCVdiwUASkvLhUqR15MPGx67NoBMroQGwy',
                3: 'QmbAQ2FzHCNiiKvSg5Lo8pszH659FPjQK6edhda6ULMZpt',
                4: 'QmdXcHHqDFYtPtYdbk1dWTsw8HsgEAQ4Qv3c9yZdrmqHPc',
                5: 'QmTsJ9KxinAXGeoFxP6LeR53tkhbiqxxN2rNRvYiKPeZdC',
            },
            'energy_regen': {
                1: 'QmW7Km95khzJ4WPmEKwcMPVh13HL12oFxGPUrKXgvNSW2k',
                2: 'QmSgJ37ArS4WwQJARUi1V3QDtYH4UWhdcGPcNT1Veee1rG',
                3: 'QmRJpJgZdUWcpAWQqEUPwmPw3uDnb5CtfqCiXxQ4DphXdo',
                4: 'QmaCHTUNvcBS9GQHCxvVKvCtTKgGDnZN1Jni6cjzaEN7NH',
                5: 'QmQUo5sihQu756osJyjfTwN2K1EYMhQNANodHkjuxHSKV1',
            },
            'wellness_regen': {
                1: 'QmPbyxn4qFFj3zV1yF95BpVUhBGaFdBthMxiMCphrmrt64',
                2: 'QmbpQknmgWVCXzffaJv2DsTTPm71WnmbUpCqk7ZqxGkxzG',
                3: 'QmdUnY5ZQgaEEFSo4KGPWcZSc6gMjYJ9i51Lnpy461nDSG',
                4: 'Qmb2oVL3jEz2v3vjCFW5X8xB4JRwtE5tcSKXqbHqCj9PhK',
                5: 'QmTaCPUzTMUSU2wkKmVebDhmEBr9vvfx22o4wWL4CQNJCm',
            },
            'military_tutor': {
                1: 'QmZRZH2WoWqxhBV5jhi8HdGmfrrrz7pE5CybSv8Z2mrt8R',
                2: 'QmcTbokGST6XRtxHymbD1A647qJYyo8yPbsjMH6zHQgGCt',
                3: 'QmQXMjb6crPsKHn38wr2V99Vb6d3qPNEqeX32z7kW7SH4n',
                4: 'QmdBazCVJi717KYpiXb1Q8REvijQ9pn3VDVQC1EiYeJPHK',
                5: 'QmeF4CJjpJVMvkDf2HYKzzCFsnpHBPjM1VAwsjtiSx25A2',
            },
            'travel_discount': {
                1: 'QmaoZNnpPQyDH3JvTsv4HUJCsmHgMq8rSEdBfrsjRyhz7b',
                2: 'QmUWV2RsadiLxzmqkUwqkPeBCkmDX3KA8uDWL96XGALC3C',
                3: 'QmNQemjqfpLoxR5HMroYqfSHNUxHzXkfSs1z5aiyM6Hro6',
                4: 'QmRQVHanAgB6SRLPKxfcA59DdwLrBQk6HdFqNsb13Xb8uD',
                5: 'QmXFo22W2HKHY3A6v96yLvCwQ3bdcZTgDEaeDT7pefGGnG',
            },
            'storage_increase': {
                1: 'QmYrb5XsDPgqsUmS1W4rP7DLghYxkWPxQKzapGB7yNvJvf',
                2: 'QmUFCXXPRURYEKEnRbV573M1sKAFcVYMxX9GPjS6K7ZPpp',
                3: 'QmQz7LVp2b64cPvbPvfXwbNodhWEwFiJc9NpRkk32Jvja6',
                4: 'QmQFj235autUSb3nxviHehMaHHngNqvdjhK1G1QJgxT53P',
                5: 'QmWEdgHuWFjSikmN6VS6EgLBjzAqReTi4izhZnEeuY7Y9t',
            },
        },
        'company': {
            'production_boost': {
                1: 'QmfBaipvZQXG7QxUg7dQqB75xV76tg96P3pxysnh6jydTk',
                2: 'QmRPSFsoUjdfwfv2aAvazVNQCJDMsmtCfZqs2TAHnkBSC6',
                3: 'QmVq9xooTstZcMLqYsrLaVeE5ZiYY8bmGoWL167YFEN5hy',
                4: 'QmQwALe3mu138B4Qjmgpanzw597YnUtyTSc3GB2Y232iha',
                5: 'QmXoRaPdza3nXX3NoBvCVnYE94HqgVfBCpT5vKERVkEs2p',
            },
            'material_efficiency': {
                1: 'QmS9e4vf5jTdKttLV5ceG4eBfErcHDZcA59MLH26FhUPzv',
                2: 'QmWXsRYjTNyAwDFAndKWywTB8w9n7LKUc5z9Ck4uSwCvtk',
                3: 'QmPbVnUPaJk6gfhMiPk3aCCRN5h4e1gm2nJ4swE1RyzCsR',
                4: 'QmV2W6Nvk81D6Y87SXnbZZqFGRw8U3Hu55xsJuET9KrxTa',
                5: 'QmVNWaNTfh8a8ttEJiitG9wDD7LuEQXXkrZgwdmqekzDNC',
            },
            'upgrade_discount': {
                1: 'QmZXpYggLHfDsiTRFTQ8ndiZSpyvXixXyXhtetHpJnpY62',
                2: 'QmSGXAGZmv6ai1XhvBhuZm3nYCaJ6vwYaKq2jcKsQu2AgD',
                3: 'QmQV7wKJZtqeRN2jzbZHAjEWirbePLzvYo9Debfhg8GLkz',
                4: 'QmW4HJ1GGZxRWJ58VDt3i58uDQPZRo61Csgnr2b5LxUi1Q',
                5: 'QmNpidYvj3q17LTjxqxvqSQyHp71YKfHofr1m3xUxXRLV2',
            },
            'speed_boost': {
                1: 'QmVM3kpSwBBsYfUtthBjcddEujrZE39NUNsx7sVVJFiupA',
                2: 'Qmc4Mra9EtjbrNyskviLhXmvjA8vzJ71Ej8jw2haKFHxaa',
                3: 'QmdXJGPPVqUjYKd1fArAz4HwxPeiJFyzcB34vZGJdjuvZW',
                4: 'QmaccWi2sv8RAnmfpcLoWwkkmHgNFvTLkfLhGAeMNQYjV1',
                5: 'QmWdVvDCoxvCrPa9cpGA7SKSPQZrYQiuVwLf813tgdTJUT',
            },
            'android_worker': {
                1: 'Qmad7FkqXManp8fnBqicUfdyYrWXSwA85YEEM1Fk8f73Yg',
                2: 'QmVrHw4yKQJ1MBrSvdyebZrt9rR7JGb9dFHa5bMcwUhsv1',
                3: 'QmS75qc6KC7wTjCKRHVCz1Ah3cb7xq7icefWPdJC7ySbdQ',
                4: 'QmZJYsDdxvaYcH5qdrJKaPJp7dhGEuVMM3BVCs9gXXiyzw',
                5: 'QmXGwwrjx6jz8q7d3yyi1ND2832KCTCG8usu91tY3e2aCu',
            },
            'tax_breaks': {
                1: 'QmWBLbV5XUQvTikKarpgkhz98WU2HzDX318ei7Zyv8vP8a',
                2: 'QmRPzn6H47oBLVwRgftz8RkG7g4VhMPV6pzvn9ZE2BPXSL',
                3: 'QmPW1nEzZwuyX6KM8akSgGtBsrvmMfnek1G4W7ndf6bVjP',
                4: 'QmR4nh8LczTNeJvfYwhjJkjmhSwxaM93t3hyBcJZ3oWDE8',
                5: 'QmVpRc7zeS8RD8tjqhzV6LAz2S8iXBzaF24LsHsfSTQifC',
            },
        },
    }

    cid = IMAGE_CIDS.get(nft_type, {}).get(category, {}).get(tier, '')
    if cid:
        # Use local proxy endpoint to avoid COEP blocking
        return f'/api/nft/image/{cid}'
    return ''
