"""
NFT Metadata Generator for Tactizen
Generates ERC-721 compliant metadata JSON files for all NFTs and uploads to Pinata IPFS
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Pinata API credentials
PINATA_API_KEY = os.getenv('PINATA_API_KEY')
PINATA_API_SECRET = os.getenv('PINATA_API_SECRET')
PINATA_JWT = os.getenv('PINATA_JWT')

# Pinata endpoints
PINATA_PIN_JSON_URL = 'https://api.pinata.cloud/pinning/pinJSONToIPFS'

# NFT Contract Address on Horizen L3 Testnet
NFT_CONTRACT_ADDRESS = os.getenv('NFT_CONTRACT_ADDRESS', '0x57e277b2d887C3C749757e36F0B6CFad32E00e8A')

# Tier names
TIER_RARITY_NAMES = {
    1: "Common",
    2: "Uncommon",
    3: "Rare",
    4: "Epic",
    5: "Legendary"
}

# Image IPFS CIDs (already uploaded)
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

# NFT Names
PLAYER_NFT_NAMES = {
    'combat_boost': {
        1: "Warrior's Token",
        2: "Soldier's Badge",
        3: "Warrior's Blade",
        4: "Champion's Crest",
        5: "Legendary Warlord's Crown"
    },
    'energy_regen': {
        1: "Energy Drink Pack",
        2: "Caffeine Supplements",
        3: "Nutrient IV Drip",
        4: "Bio-Stimulant Injector",
        5: "Neural Energizer Implant"
    },
    'wellness_regen': {
        1: "First Aid Kit",
        2: "Medical Subscription",
        3: "Health Monitor Device",
        4: "Regeneration Pod Access",
        5: "Advanced Med-Bay Pass"
    },
    'military_tutor': {
        1: "Drill Sergeant's Manual",
        2: "Combat Instructor's Codex",
        3: "War Academy Tome",
        4: "General's Strategy Compendium",
        5: "Art of War Masterwork"
    },
    'travel_discount': {
        1: "Transit Pass",
        2: "Frequent Flyer Card",
        3: "Priority Travel License",
        4: "VIP Transport Pass",
        5: "Universal Travel Clearance"
    },
    'storage_increase': {
        1: "Storage Locker Rental",
        2: "Cargo Container Lease",
        3: "Warehouse Access Card",
        4: "Distribution Center Pass",
        5: "Logistics Hub License"
    }
}

COMPANY_NFT_NAMES = {
    'production_boost': {
        1: "Basic Assembly Tool",
        2: "Production Enhancer",
        3: "Industrial Optimizer",
        4: "Advanced Automation System",
        5: "Quantum Production Matrix"
    },
    'material_efficiency': {
        1: "Material Saver",
        2: "Resource Optimizer",
        3: "Efficient Processor",
        4: "Nano-Material Converter",
        5: "Zero-Waste Recycler"
    },
    'upgrade_discount': {
        1: "Budget Planner",
        2: "Cost Reducer",
        3: "Investment Optimizer",
        4: "Financial Genius AI",
        5: "Government Subsidy Grant"
    },
    'speed_boost': {
        1: "Quick Assembly Kit",
        2: "Speed Booster",
        3: "Rapid Production Unit",
        4: "Parallel Assembly Line",
        5: "Hyper-Automation System"
    },
    'android_worker': {
        1: "Labor Droid Mk-I",
        2: "Labor Droid Mk-II",
        3: "Labor Droid Mk-III",
        4: "Labor Droid Mk-IV",
        5: "Labor Droid Mk-V"
    },
    'tax_breaks': {
        1: "Tax Consultant Contract",
        2: "Corporate Accountant",
        3: "Tax Optimization Firm",
        4: "Offshore Holdings License",
        5: "Tax Exemption Certificate"
    }
}

# Bonus values
PLAYER_NFT_BONUSES = {
    'combat_boost': {1: 5, 2: 15, 3: 25, 4: 40, 5: 60},
    'energy_regen': {1: 2, 2: 5, 3: 10, 4: 20, 5: 35},
    'wellness_regen': {1: 2, 2: 5, 3: 10, 4: 20, 5: 35},
    'military_tutor': {1: 20, 2: 40, 3: 60, 4: 80, 5: 100},
    'travel_discount': {1: 20, 2: 40, 3: 60, 4: 80, 5: 100},
    'storage_increase': {1: 1000, 2: 2000, 3: 3000, 4: 4000, 5: 5000}
}

COMPANY_NFT_BONUSES = {
    'production_boost': {1: 10, 2: 20, 3: 35, 4: 55, 5: 80},
    'material_efficiency': {1: 5, 2: 15, 3: 25, 4: 40, 5: 60},
    'upgrade_discount': {1: 5, 2: 15, 3: 25, 4: 40, 5: 50},
    'speed_boost': {1: 10, 2: 20, 3: 30, 4: 45, 5: 65},
    'android_worker': {1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
    'tax_breaks': {1: 20, 2: 40, 3: 60, 4: 80, 5: 100}
}


def get_description(nft_type: str, category: str, tier: int, bonus: int) -> str:
    """Generate description for NFT"""
    rarity = TIER_RARITY_NAMES[tier].lower()

    if category == 'combat_boost':
        return f"A {rarity} item that increases your combat damage by {bonus}%"
    elif category == 'energy_regen':
        return f"A {rarity} item that regenerates {bonus} energy per hour"
    elif category == 'wellness_regen':
        return f"A {rarity} item that regenerates {bonus} wellness per hour"
    elif category == 'military_tutor':
        return f"A {rarity} training guide that increases Military Rank XP gained by {bonus}%"
    elif category == 'travel_discount':
        if tier == 5:
            return f"A {rarity} authorization that eliminates all travel costs"
        gold_cost = round(1.0 * (100 - bonus) / 100, 1)
        energy_cost = int(50 * (100 - bonus) / 100)
        return f"A {rarity} pass that reduces travel costs to {gold_cost} Gold / {energy_cost} Energy"
    elif category == 'storage_increase':
        return f"A {rarity} storage contract that increases capacity by {bonus:,} units"
    elif category == 'production_boost':
        return f"A {rarity} system that boosts production output by {bonus}%"
    elif category == 'material_efficiency':
        return f"A {rarity} processor that reduces material consumption by {bonus}%"
    elif category == 'upgrade_discount':
        return f"A {rarity} optimizer that reduces upgrade costs by {bonus}%"
    elif category == 'speed_boost':
        return f"A {rarity} accelerator that reduces production points required by {bonus}%"
    elif category == 'android_worker':
        return f"A {rarity} android unit with Skill Level {bonus}. Works 12-hour shifts autonomously."
    elif category == 'tax_breaks':
        if tier == 5:
            return f"A {rarity} exemption that eliminates all company taxes on withdrawals and sales"
        return f"A {rarity} financial service that reduces company taxes by {bonus}%"

    return f"A {rarity} NFT with {bonus} bonus"


def generate_metadata(nft_type: str, category: str, tier: int) -> dict:
    """Generate ERC-721 compliant metadata for an NFT"""
    rarity = TIER_RARITY_NAMES[tier]
    image_cid = IMAGE_CIDS[nft_type][category][tier]

    if nft_type == 'player':
        name = PLAYER_NFT_NAMES[category][tier]
        bonus = PLAYER_NFT_BONUSES[category][tier]
    else:
        name = COMPANY_NFT_NAMES[category][tier]
        bonus = COMPANY_NFT_BONUSES[category][tier]

    description = get_description(nft_type, category, tier, bonus)

    # ERC-721 Metadata Standard
    metadata = {
        "name": f"{name} - {rarity}",
        "description": description,
        "image": f"ipfs://{image_cid}",
        "external_url": "https://tactizen.com",
        "attributes": [
            {
                "trait_type": "Type",
                "value": nft_type.capitalize()
            },
            {
                "trait_type": "Category",
                "value": category.replace('_', ' ').title()
            },
            {
                "trait_type": "Tier",
                "value": f"Q{tier}"
            },
            {
                "trait_type": "Rarity",
                "value": rarity
            },
            {
                "trait_type": "Bonus Value",
                "value": bonus,
                "display_type": "number"
            }
        ]
    }

    return metadata


def upload_to_pinata(metadata: dict, name: str) -> str:
    """Upload metadata JSON to Pinata IPFS and return CID"""
    headers = {
        'Authorization': f'Bearer {PINATA_JWT}',
        'Content-Type': 'application/json'
    }

    payload = {
        'pinataContent': metadata,
        'pinataMetadata': {
            'name': name
        }
    }

    response = requests.post(PINATA_PIN_JSON_URL, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()['IpfsHash']
    else:
        print(f"Error uploading {name}: {response.text}")
        return None


def main():
    print("Generating and uploading NFT metadata to Pinata IPFS...")
    print("=" * 60)

    metadata_cids = {
        'player': {},
        'company': {}
    }

    # Player NFTs
    player_categories = ['combat_boost', 'energy_regen', 'wellness_regen',
                         'military_tutor', 'travel_discount', 'storage_increase']

    for category in player_categories:
        metadata_cids['player'][category] = {}
        for tier in range(1, 6):
            metadata = generate_metadata('player', category, tier)
            name = f"tactizen_player_{category}_q{tier}"

            print(f"Uploading {name}...")
            cid = upload_to_pinata(metadata, name)

            if cid:
                metadata_cids['player'][category][tier] = cid
                print(f"  -> ipfs://{cid}")
            else:
                print(f"  -> FAILED!")

    # Company NFTs
    company_categories = ['production_boost', 'material_efficiency', 'upgrade_discount',
                          'speed_boost', 'android_worker', 'tax_breaks']

    for category in company_categories:
        metadata_cids['company'][category] = {}
        for tier in range(1, 6):
            metadata = generate_metadata('company', category, tier)
            name = f"tactizen_company_{category}_q{tier}"

            print(f"Uploading {name}...")
            cid = upload_to_pinata(metadata, name)

            if cid:
                metadata_cids['company'][category][tier] = cid
                print(f"  -> ipfs://{cid}")
            else:
                print(f"  -> FAILED!")

    print("\n" + "=" * 60)
    print("NFT Metadata CIDs (copy to nft_config.py):")
    print("=" * 60)

    # Output Python dict format for easy copy-paste
    print("\nNFT_METADATA_URIS = {")
    for nft_type in ['player', 'company']:
        print(f"    '{nft_type}': {{")
        categories = player_categories if nft_type == 'player' else company_categories
        for category in categories:
            print(f"        '{category}': {{")
            for tier in range(1, 6):
                cid = metadata_cids[nft_type].get(category, {}).get(tier, '')
                uri = f"ipfs://{cid}" if cid else ''
                print(f"            {tier}: '{uri}',")
            print("        },")
        print("    },")
    print("}")

    print("\n" + "=" * 60)
    print("Done! Copy the NFT_METADATA_URIS dict to nft_config.py")


if __name__ == '__main__':
    main()
