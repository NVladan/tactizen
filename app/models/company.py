# app/models/company.py

import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Numeric, CheckConstraint

from . import db
from app.mixins import SoftDeleteMixin


# --- Company Type Enum ---
class CompanyType(enum.Enum):
    # Resource Extraction
    MINING = 'Mining'  # Coal, Iron Ore, Stone
    RESOURCE_EXTRACTION = 'Resource Extraction'  # Clay, Oil, Sand
    FARMING = 'Farming'  # Wheat, Grape

    # Weapon Manufacturing (split by product)
    RIFLE_MANUFACTURING = 'Rifle Company'  # Rifle (requires Iron Bar + Coal)
    TANK_MANUFACTURING = 'Tank Company'  # Tank (requires Steel + Oil)
    HELICOPTER_MANUFACTURING = 'Helicopter Company'  # Helicopter (requires Steel + Oil)

    # Consumer Goods (split by product)
    BREAD_MANUFACTURING = 'Bakery'  # Bread (requires Wheat)
    BEER_MANUFACTURING = 'Brewery'  # Beer (requires Wheat)
    WINE_MANUFACTURING = 'Winery'  # Wine (requires Grape)

    # Semi-Products
    SEMI_PRODUCT = 'Semi-Product'  # Steel, Bricks, Concrete (Iron+Coal, Clay+Coal, Stone+Sand)

    # Construction
    CONSTRUCTION = 'Construction'  # House, Fort, Hospital (requires Bricks + Concrete)


# --- Transaction Type Enum ---
class CompanyTransactionType(enum.Enum):
    # Money In
    OWNER_DEPOSIT_GOLD = 'Owner Deposit (Gold)'
    OWNER_DEPOSIT_CURRENCY = 'Owner Deposit (Currency)'
    PRODUCT_SALE = 'Product Sale'
    CURRENCY_EXCHANGE = 'Currency Exchange (Buy)'
    INVENTORY_SALE = 'Inventory Sale'

    # Money Out
    OWNER_WITHDRAWAL_GOLD = 'Owner Withdrawal (Gold)'
    OWNER_WITHDRAWAL_CURRENCY = 'Owner Withdrawal (Currency)'
    WAGE_PAYMENT = 'Wage Payment'
    RESOURCE_PURCHASE = 'Resource Purchase'
    UPGRADE = 'Company Upgrade'
    EXPORT_LICENSE = 'Export License'
    RELOCATION = 'Company Relocation'
    CURRENCY_EXCHANGE_SELL = 'Currency Exchange (Sell)'
    INVENTORY_PURCHASE = 'Inventory Purchase'


# --- Company Model ---
class Company(SoftDeleteMixin, db.Model):
    """Represents a player-owned company."""
    __tablename__ = 'company'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    company_type = db.Column(db.Enum(CompanyType), nullable=False, index=True)
    quality_level = db.Column(db.Integer, default=1, nullable=False)  # Q1-Q5

    # Company Profile
    avatar = db.Column(db.Boolean, default=False, nullable=False)  # Whether company has uploaded an avatar
    description = db.Column(db.Text, nullable=True)  # Company description/bio

    # Owner & Location
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Company Finances
    gold_balance = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    currency_balance = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)

    # Production State - tracks what the company is currently producing
    current_production_resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    production_progress = db.Column(db.Integer, default=0, nullable=False)  # Progress toward next unit

    # Electricity Usage Preference
    use_electricity = db.Column(db.Boolean, default=True, nullable=False)  # Whether to use electricity for +30% boost

    # Android Worker tracking (NFT-based worker)
    android_last_worked = db.Column(db.Date, nullable=True)  # Last game day the Android worked

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = db.relationship('User', back_populates='companies')
    country = db.relationship('Country')
    current_production_resource = db.relationship('Resource', foreign_keys=[current_production_resource_id])

    employees = db.relationship('Employment', back_populates='company', lazy='dynamic', cascade='all, delete-orphan')
    job_offers = db.relationship('JobOffer', back_populates='company', lazy='dynamic', cascade='all, delete-orphan')
    inventory = db.relationship('CompanyInventory', back_populates='company', lazy='dynamic', cascade='all, delete-orphan')
    transactions = db.relationship('CompanyTransaction', back_populates='company', lazy='dynamic', cascade='all, delete-orphan')
    export_licenses = db.relationship('ExportLicense', back_populates='company', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('quality_level >= 1 AND quality_level <= 5', name='check_quality_level'),
        CheckConstraint('gold_balance >= 0', name='check_gold_balance_positive'),
        CheckConstraint('currency_balance >= 0', name='check_currency_balance_positive'),
    )

    @property
    def max_employees(self):
        """Maximum number of employees based on quality level."""
        return self.quality_level * 2  # Q1=2, Q2=4, Q3=6, Q4=8, Q5=10

    @property
    def has_android_worker(self):
        """Check if company has an Android Worker NFT equipped."""
        from app.services.bonus_calculator import BonusCalculator
        return BonusCalculator.get_android_worker_skill(self.id) > 0

    @property
    def current_employee_count(self):
        """Current number of active employees (including Android Worker if equipped)."""
        human_employees = self.employees.count()
        android_slot = 1 if self.has_android_worker else 0
        return human_employees + android_slot

    @property
    def available_positions(self):
        """Number of available employee positions."""
        return self.max_employees - self.current_employee_count

    @property
    def upgrade_cost(self):
        """Cost to upgrade to next quality level in Gold."""
        upgrade_costs = {
            1: 20,   # Q1 -> Q2
            2: 80,   # Q2 -> Q3
            3: 160,  # Q3 -> Q4
            4: 320,  # Q4 -> Q5
        }
        return upgrade_costs.get(self.quality_level, 0)

    @property
    def quality_production_bonus(self):
        """Production bonus multiplier based on quality level (for resource extraction)."""
        bonuses = {
            1: 1.0,    # Q1: +0%
            2: 1.25,   # Q2: +25%
            3: 1.50,   # Q3: +50%
            4: 1.75,   # Q4: +75%
            5: 2.0,    # Q5: +100%
        }
        return bonuses.get(self.quality_level, 1.0)

    @property
    def required_pp_for_current_product(self):
        """Required production points to complete current product based on quality."""
        if not self.current_production_resource_id:
            return 0
        pp_requirements = {
            1: 5,   # Q1
            2: 10,  # Q2
            3: 15,  # Q3
            4: 20,  # Q4
            5: 25,  # Q5
        }
        return pp_requirements.get(self.quality_level, 5)

    @property
    def raw_materials_required(self):
        """Raw materials needed per product based on quality (linear scaling)."""
        materials_needed = {
            1: 5,   # Q1
            2: 10,  # Q2
            3: 15,  # Q3
            4: 20,  # Q4
            5: 25,  # Q5
        }
        return materials_needed.get(self.quality_level, 5)

    @property
    def is_extraction_company(self):
        """Check if this is a resource extraction company."""
        return self.company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING]

    @property
    def production_progress_percentage(self):
        """Current production progress as percentage."""
        if self.is_extraction_company:
            # Extraction: progress is stored ×100, required is always 100 (1.00 PP)
            required = 100
            if required == 0:
                return 0
            return min(100, (self.production_progress / required) * 100)
        else:
            # Manufacturing: progress is stored ×100, required PP also ×100
            required = self.required_pp_for_current_product * 100
            if required == 0:
                return 0
            return min(100, (self.production_progress / required) * 100)

    @property
    def production_progress_display(self):
        """Display production progress (handles different scales for extraction vs manufacturing)."""
        # Both extraction and manufacturing now use scale of 100 (PP × 100 stored)
        return self.production_progress / 100.0

    @property
    def required_pp_display(self):
        """Display required PP (handles different scales for extraction vs manufacturing)."""
        if self.is_extraction_company:
            # Extraction requires 1.00 PP (stored as 100)
            return 1.0
        else:
            # Manufacturing has variable requirements
            return float(self.required_pp_for_current_product)

    def get_required_skill_type(self):
        """Get the skill type required for this company type."""
        skill_mapping = {
            # Resource extraction
            CompanyType.MINING: 'resource_extraction',
            CompanyType.RESOURCE_EXTRACTION: 'resource_extraction',
            CompanyType.FARMING: 'resource_extraction',
            # Weapon manufacturing (split)
            CompanyType.RIFLE_MANUFACTURING: 'manufacture',
            CompanyType.TANK_MANUFACTURING: 'manufacture',
            CompanyType.HELICOPTER_MANUFACTURING: 'manufacture',
            # Consumer goods (split)
            CompanyType.BREAD_MANUFACTURING: 'manufacture',
            CompanyType.BEER_MANUFACTURING: 'manufacture',
            CompanyType.WINE_MANUFACTURING: 'manufacture',
            # Semi-products
            CompanyType.SEMI_PRODUCT: 'manufacture',
            # Construction
            CompanyType.CONSTRUCTION: 'construction',
        }
        return skill_mapping.get(self.company_type, 'resource_extraction')

    def __repr__(self):
        return f'<Company {self.name} Q{self.quality_level} ({self.company_type.value})>'


# --- Job Offer Model ---
class JobOffer(db.Model):
    """Represents a job offer posted by a company."""
    __tablename__ = 'job_offer'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)

    # Job Details
    wage_per_pp = db.Column(Numeric(10, 4), nullable=False)  # Wage per production point in local currency
    daily_wage_currency = db.Column(Numeric(10, 4), nullable=True)  # DEPRECATED: Keep for migration compatibility
    minimum_skill_level = db.Column(db.Float, default=0.0, nullable=False)  # Required skill level
    positions = db.Column(db.Integer, default=1, nullable=False)  # Number of positions available

    # Job offer can be filled or open
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = db.relationship('Company', back_populates='job_offers')

    __table_args__ = (
        CheckConstraint('wage_per_pp > 0', name='check_wage_pp_positive'),
        CheckConstraint('minimum_skill_level >= 0', name='check_min_skill_positive'),
        CheckConstraint('positions > 0', name='check_positions_positive'),
    )

    @property
    def positions_filled(self):
        """Count how many employees were hired through this job offer (approximation based on recent hires)."""
        from datetime import timedelta
        # Count employments created after this job offer with matching wage
        recent_hires = Employment.query.filter(
            Employment.company_id == self.company_id,
            Employment.wage_per_pp == self.wage_per_pp,
            Employment.hired_at >= self.created_at
        ).count()
        return min(recent_hires, self.positions)

    @property
    def positions_available(self):
        """Remaining positions for this job offer."""
        return max(0, self.positions - self.positions_filled)

    def __repr__(self):
        return f'<JobOffer Company:{self.company_id} Wage:{self.wage_per_pp}/PP Positions:{self.positions_filled}/{self.positions}>'


# --- Employment Model ---
class Employment(db.Model):
    """Represents an active employment relationship between a user and a company."""
    __tablename__ = 'employment'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Employment Terms
    wage_per_pp = db.Column(Numeric(10, 4), nullable=False)  # Wage per production point in local currency
    daily_wage_currency = db.Column(Numeric(10, 4), nullable=True)  # DEPRECATED: Keep for migration compatibility

    # Work Tracking
    last_worked = db.Column(db.Date, nullable=True)  # Last date they worked
    has_worked_today = db.Column(db.Boolean, default=False, nullable=False)  # DEPRECATED: Use TimeAllocation instead
    total_days_worked = db.Column(db.Integer, default=0, nullable=False)
    total_hours_worked = db.Column(db.Integer, default=0, nullable=False)  # Total hours worked lifetime

    # Timestamps
    hired_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = db.relationship('Company', back_populates='employees')
    user = db.relationship('User', back_populates='employments')

    __table_args__ = (
        CheckConstraint('wage_per_pp > 0', name='check_employment_wage_pp_positive'),
        # Ensure a user can only work at one position per company
        db.UniqueConstraint('company_id', 'user_id', name='unique_company_user_employment'),
    )

    def __repr__(self):
        return f'<Employment User:{self.user_id} Company:{self.company_id} Wage:{self.wage_per_pp}/PP>'


# --- Company Inventory Model ---
class CompanyInventory(db.Model):
    """Represents a company's holding of a specific resource."""
    __tablename__ = 'company_inventory'

    # Composite primary key (company_id, resource_id, quality)
    # Quality is part of PK to allow different quality items of the same resource
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), primary_key=True)
    quality = db.Column(db.Integer, primary_key=True, default=0)  # Quality 0 for raw materials, 1-5 for manufactured items

    quantity = db.Column(db.Integer, default=0, nullable=False)

    # Timestamps
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = db.relationship('Company', back_populates='inventory')
    resource = db.relationship('Resource')

    __table_args__ = (
        CheckConstraint('quantity >= 0', name='check_company_inventory_quantity_positive'),
        CheckConstraint('quality >= 0 AND quality <= 5', name='check_quality_range'),
    )

    def __repr__(self):
        quality_str = f'Q{self.quality}' if self.quality else 'Raw'
        return f'<CompanyInventory Company:{self.company_id} Resource:{self.resource_id} Qty:{self.quantity} {quality_str}>'


# --- Company Transaction Model ---
class CompanyTransaction(db.Model):
    """Records all financial transactions for a company."""
    __tablename__ = 'company_transaction'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False, index=True)

    transaction_type = db.Column(db.Enum(CompanyTransactionType), nullable=False, index=True)
    amount_gold = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    amount_currency = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)

    description = db.Column(db.String(255), nullable=True)
    related_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # For wages, deposits, etc.

    # Balances after transaction
    balance_gold_after = db.Column(Numeric(20, 8), nullable=False)
    balance_currency_after = db.Column(Numeric(20, 8), nullable=False)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    company = db.relationship('Company', back_populates='transactions')
    related_user = db.relationship('User')

    def __repr__(self):
        return f'<CompanyTransaction {self.transaction_type.value} Company:{self.company_id}>'


# --- Export License Model ---
class ExportLicense(db.Model):
    """Represents a company's license to sell in a specific country's market."""
    __tablename__ = 'export_license'

    # Composite primary key
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), primary_key=True)

    # Purchase details
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    cost_gold = db.Column(Numeric(20, 8), nullable=False, default=Decimal('20.0'))  # How much gold was paid

    # Relationships
    company = db.relationship('Company', back_populates='export_licenses')
    country = db.relationship('Country')

    def __repr__(self):
        return f'<ExportLicense Company:{self.company_id} Country:{self.country_id}>'


# --- Company Production Progress Model ---
class CompanyProductionProgress(db.Model):
    """Tracks production progress per resource for each company."""
    __tablename__ = 'company_production_progress'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id', ondelete='CASCADE'), nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = db.relationship('Company')
    resource = db.relationship('Resource')

    def __repr__(self):
        return f'<CompanyProductionProgress Company:{self.company_id} Resource:{self.resource_id} Progress:{self.progress}>'
