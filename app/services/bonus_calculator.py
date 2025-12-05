"""
Bonus Calculator Service
Applies NFT bonuses to gameplay mechanics
"""
from typing import Dict, Tuple, Optional
from app.services.nft_service import NFTService


class BonusCalculator:
    """Calculate and apply NFT bonuses to game actions"""

    @staticmethod
    def get_player_combat_damage(user_id: int, base_damage: float) -> float:
        """
        Calculate combat damage with NFT bonuses

        Args:
            user_id: ID of the user
            base_damage: Base damage before bonuses

        Returns:
            Final damage after bonuses
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        combat_boost = bonuses.get('combat_boost', 0)

        # Apply percentage boost
        final_damage = base_damage * (1 + combat_boost / 100)

        return final_damage

    @staticmethod
    def get_energy_cost(user_id: int, base_cost: int) -> int:
        """
        Calculate energy cost with efficiency bonuses

        Args:
            user_id: ID of the user
            base_cost: Base energy cost

        Returns:
            Final energy cost after bonuses
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        efficiency = bonuses.get('energy_efficiency', 0)

        # Apply percentage reduction
        final_cost = int(base_cost * (1 - efficiency / 100))

        # Ensure at least 1 energy
        return max(1, final_cost)

    @staticmethod
    def get_wellness_cost(user_id: int, base_cost: int) -> int:
        """
        Calculate wellness cost with efficiency bonuses

        Args:
            user_id: ID of the user
            base_cost: Base wellness cost

        Returns:
            Final wellness cost after bonuses
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        efficiency = bonuses.get('wellness_efficiency', 0)

        # Apply percentage reduction
        final_cost = int(base_cost * (1 - efficiency / 100))

        # Ensure at least 1 wellness
        return max(1, final_cost)

    @staticmethod
    def get_energy_regen_rate(user_id: int) -> int:
        """
        Get energy regeneration rate per hour

        Args:
            user_id: ID of the user

        Returns:
            Energy regen per hour
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        return bonuses.get('energy_regen', 0)

    @staticmethod
    def get_wellness_regen_rate(user_id: int) -> int:
        """
        Get wellness regeneration rate per hour

        Args:
            user_id: ID of the user

        Returns:
            Wellness regen per hour
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        return bonuses.get('wellness_regen', 0)

    @staticmethod
    def apply_work_costs(user_id: int, base_energy: int, base_wellness: int) -> Tuple[int, int]:
        """
        Apply efficiency bonuses to work costs

        Args:
            user_id: ID of the user
            base_energy: Base energy cost
            base_wellness: Base wellness cost

        Returns:
            (final_energy_cost, final_wellness_cost)
        """
        energy_cost = BonusCalculator.get_energy_cost(user_id, base_energy)
        wellness_cost = BonusCalculator.get_wellness_cost(user_id, base_wellness)

        return energy_cost, wellness_cost

    @staticmethod
    def apply_training_costs(user_id: int, base_energy: int, base_wellness: int) -> Tuple[int, int]:
        """
        Apply efficiency bonuses to training costs

        Args:
            user_id: ID of the user
            base_energy: Base energy cost
            base_wellness: Base wellness cost

        Returns:
            (final_energy_cost, final_wellness_cost)
        """
        energy_cost = BonusCalculator.get_energy_cost(user_id, base_energy)
        wellness_cost = BonusCalculator.get_wellness_cost(user_id, base_wellness)

        return energy_cost, wellness_cost

    @staticmethod
    def apply_study_costs(user_id: int, base_energy: int, base_wellness: int) -> Tuple[int, int]:
        """
        Apply efficiency bonuses to study costs

        Args:
            user_id: ID of the user
            base_energy: Base energy cost
            base_wellness: Base wellness cost

        Returns:
            (final_energy_cost, final_wellness_cost)
        """
        energy_cost = BonusCalculator.get_energy_cost(user_id, base_energy)
        wellness_cost = BonusCalculator.get_wellness_cost(user_id, base_wellness)

        return energy_cost, wellness_cost

    @staticmethod
    def get_company_production_output(company_id: int, base_output: float) -> float:
        """
        Calculate production output with bonuses

        Args:
            company_id: ID of the company
            base_output: Base production output

        Returns:
            Final production output after bonuses
        """
        bonuses = NFTService.get_company_bonuses(company_id)
        production_boost = bonuses.get('production_boost', 0)

        # Apply percentage boost
        final_output = base_output * (1 + production_boost / 100)

        return final_output

    @staticmethod
    def get_company_material_cost(company_id: int, base_materials: Dict[str, int]) -> Dict[str, int]:
        """
        Calculate material costs with efficiency bonuses

        Args:
            company_id: ID of the company
            base_materials: Dictionary of material requirements {material_id: quantity}

        Returns:
            Final material requirements after bonuses
        """
        bonuses = NFTService.get_company_bonuses(company_id)
        efficiency = bonuses.get('material_efficiency', 0)

        # Apply percentage reduction to all materials
        final_materials = {}
        for material_id, quantity in base_materials.items():
            reduced_quantity = int(quantity * (1 - efficiency / 100))
            final_materials[material_id] = max(1, reduced_quantity)  # At least 1

        return final_materials

    @staticmethod
    def get_company_upgrade_cost(company_id: int, base_cost: float) -> float:
        """
        Calculate upgrade cost with discount bonuses

        Args:
            company_id: ID of the company
            base_cost: Base upgrade cost

        Returns:
            Final upgrade cost after bonuses
        """
        bonuses = NFTService.get_company_bonuses(company_id)
        discount = bonuses.get('upgrade_discount', 0)

        # Apply percentage reduction
        final_cost = base_cost * (1 - discount / 100)

        return max(1, final_cost)  # At least 1

    @staticmethod
    def get_company_production_speed(company_id: int, base_pp_required: int) -> int:
        """
        Calculate production points required with speed bonuses

        Args:
            company_id: ID of the company
            base_pp_required: Base production points required

        Returns:
            Final PP required after bonuses
        """
        bonuses = NFTService.get_company_bonuses(company_id)
        speed_boost = bonuses.get('speed_boost', 0)

        # Apply percentage reduction
        final_pp = int(base_pp_required * (1 - speed_boost / 100))

        return max(1, final_pp)  # At least 1 PP

    @staticmethod
    def get_player_bonus_summary(user_id: int) -> Dict[str, any]:
        """
        Get summary of all player bonuses for display

        Args:
            user_id: ID of the user

        Returns:
            Dictionary with bonus summary
        """
        bonuses = NFTService.get_player_bonuses(user_id)

        return {
            'combat': {
                'boost_percent': bonuses.get('combat_boost', 0),
                'description': f"+{bonuses.get('combat_boost', 0)}% damage in battles"
            },
            'energy_regen': {
                'value': bonuses.get('energy_regen', 0),
                'description': f"+{bonuses.get('energy_regen', 0)} energy per hour"
            },
            'wellness_regen': {
                'value': bonuses.get('wellness_regen', 0),
                'description': f"+{bonuses.get('wellness_regen', 0)} wellness per hour"
            },
            'military_tutor': {
                'boost_percent': bonuses.get('military_tutor', 0),
                'description': f"+{bonuses.get('military_tutor', 0)}% military rank XP"
            },
            'travel_discount': {
                'boost_percent': bonuses.get('travel_discount', 0),
                'description': f"-{bonuses.get('travel_discount', 0)}% travel costs"
            },
            'storage_increase': {
                'value': bonuses.get('storage_increase', 0),
                'description': f"+{bonuses.get('storage_increase', 0)} storage capacity"
            }
        }

    @staticmethod
    def get_company_bonus_summary(company_id: int) -> Dict[str, any]:
        """
        Get summary of all company bonuses for display

        Args:
            company_id: ID of the company

        Returns:
            Dictionary with bonus summary
        """
        bonuses = NFTService.get_company_bonuses(company_id)

        return {
            'production': {
                'boost_percent': bonuses.get('production_boost', 0),
                'description': f"+{bonuses.get('production_boost', 0)}% production output"
            },
            'materials': {
                'boost_percent': bonuses.get('material_efficiency', 0),
                'description': f"-{bonuses.get('material_efficiency', 0)}% material costs"
            },
            'upgrades': {
                'boost_percent': bonuses.get('upgrade_discount', 0),
                'description': f"-{bonuses.get('upgrade_discount', 0)}% upgrade costs"
            },
            'speed': {
                'boost_percent': bonuses.get('speed_boost', 0),
                'description': f"-{bonuses.get('speed_boost', 0)}% production time"
            }
        }

    @staticmethod
    def regenerate_energy_wellness(user_id: int, hours_elapsed: float) -> Tuple[int, int]:
        """
        Calculate energy and wellness regeneration over time

        Args:
            user_id: ID of the user
            hours_elapsed: Number of hours elapsed

        Returns:
            (energy_regen, wellness_regen)
        """
        bonuses = NFTService.get_player_bonuses(user_id)

        energy_regen_per_hour = bonuses.get('energy_regen', 0)
        wellness_regen_per_hour = bonuses.get('wellness_regen', 0)

        energy_regen = int(energy_regen_per_hour * hours_elapsed)
        wellness_regen = int(wellness_regen_per_hour * hours_elapsed)

        return energy_regen, wellness_regen

    @staticmethod
    def get_military_xp_multiplier(user_id: int) -> float:
        """
        Get Military Rank XP multiplier from Military Tutor NFT

        Args:
            user_id: ID of the user

        Returns:
            XP multiplier (1.0 = no bonus, 2.0 = +100% XP)
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        military_tutor_bonus = bonuses.get('military_tutor', 0)

        # Convert percentage to multiplier (e.g., 20% -> 1.2)
        return 1.0 + (military_tutor_bonus / 100)

    @staticmethod
    def get_travel_costs(user_id: int, base_gold: float, base_energy: int) -> Tuple[float, int]:
        """
        Calculate travel costs with Travel Discount NFT bonus

        Args:
            user_id: ID of the user
            base_gold: Base gold cost (1.0 Gold normally)
            base_energy: Base energy cost (50 Energy normally)

        Returns:
            (final_gold_cost, final_energy_cost)
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        travel_discount = bonuses.get('travel_discount', 0)

        # Apply percentage discount
        final_gold = base_gold * (1 - travel_discount / 100)
        final_energy = int(base_energy * (1 - travel_discount / 100))

        # Q5 (100% discount) = free travel
        if travel_discount >= 100:
            return 0.0, 0

        return round(final_gold, 2), max(0, final_energy)

    @staticmethod
    def get_storage_capacity(user_id: int, base_capacity: int = 1000) -> int:
        """
        Calculate total storage capacity with Storage Increase NFT bonus

        Args:
            user_id: ID of the user
            base_capacity: Base storage capacity (default 1000)

        Returns:
            Total storage capacity
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        storage_increase = bonuses.get('storage_increase', 0)

        # Add flat bonus to base capacity
        return base_capacity + storage_increase

    @staticmethod
    def get_android_worker_skill(company_id: int) -> int:
        """
        Get Android Worker skill level from equipped NFT

        Args:
            company_id: ID of the company

        Returns:
            Skill level (0-5, 0 means no android worker equipped)
        """
        bonuses = NFTService.get_company_bonuses(company_id)
        return bonuses.get('android_worker', 0)

    @staticmethod
    def get_tax_reduction(company_id: int) -> float:
        """
        Get tax reduction percentage from Tax Breaks NFT

        Args:
            company_id: ID of the company

        Returns:
            Tax reduction percentage (0-100)
        """
        bonuses = NFTService.get_company_bonuses(company_id)
        return bonuses.get('tax_breaks', 0)

    @staticmethod
    def apply_company_tax(company_id: int, base_tax: float) -> float:
        """
        Calculate actual tax after Tax Breaks NFT reduction

        Args:
            company_id: ID of the company
            base_tax: Base tax amount

        Returns:
            Final tax after reduction
        """
        tax_reduction = BonusCalculator.get_tax_reduction(company_id)

        # Apply percentage reduction (Q5 = 100% reduction = no tax)
        final_tax = base_tax * (1 - tax_reduction / 100)

        return max(0.0, final_tax)

    @staticmethod
    def get_extraction_resource_bonus(company_id: int, resource_id: int) -> float:
        """
        Check if the company's country has the resource in its regions.
        If yes, return 100% bonus (2.0 multiplier).

        This only applies to extraction companies (Mining, Resource Extraction, Farming).

        Args:
            company_id: ID of the company
            resource_id: ID of the resource being extracted

        Returns:
            1.0 if no bonus, 2.0 if country has the resource (+100% bonus)
        """
        from app.extensions import db
        from app.models import Company, RegionalResource

        company = db.session.get(Company, company_id)
        if not company or not company.country_id:
            return 1.0

        # Check if company's country has this resource in any of its regions
        if RegionalResource.country_has_resource(company.country_id, resource_id):
            return 2.0  # +100% bonus

        return 1.0  # No bonus

    @staticmethod
    def deduct_regional_resource(company_id: int, resource_id: int, amount: int) -> int:
        """
        Deduct resource from regional deposits when extraction company produces.

        The deduction is spread across all regions with this resource owned by the company's country.

        Args:
            company_id: ID of the company
            resource_id: ID of the resource being extracted
            amount: Amount to deduct

        Returns:
            Amount actually deducted (may be less if deposits run out)
        """
        from app.extensions import db
        from app.models import Company, Region, RegionalResource, country_regions

        company = db.session.get(Company, company_id)
        if not company or not company.country_id:
            return 0

        # Get all regional resources of this type owned by the company's country
        deposits = db.session.scalars(
            db.select(RegionalResource)
            .join(Region)
            .join(country_regions, Region.id == country_regions.c.region_id)
            .filter(
                country_regions.c.country_id == company.country_id,
                RegionalResource.resource_id == resource_id,
                RegionalResource.amount > 0
            )
            .order_by(RegionalResource.amount)  # Deplete smaller deposits first
        ).all()

        if not deposits:
            return 0

        remaining_to_deduct = amount
        total_deducted = 0

        for deposit in deposits:
            if remaining_to_deduct <= 0:
                break

            deducted = deposit.deplete(remaining_to_deduct)
            remaining_to_deduct -= deducted
            total_deducted += deducted

        return total_deducted
