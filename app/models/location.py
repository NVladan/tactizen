# tactizen/app/models/location.py

from datetime import datetime
from decimal import Decimal
from slugify import slugify
from sqlalchemy.types import Numeric
from . import db # Use relative import
from app.mixins import SoftDeleteMixin

# --- Import GoldMarket for the relationship definition ---
try:
    from .currency_market import GoldMarket
except ImportError:
    # This might happen during initial migration generation before GoldMarket exists
    # In that case, the relationship definition might need temporary commenting out
    # or careful handling in the migration script itself.
    pass
# --- End Import ---


# --- Association Tables ---
country_regions = db.Table('country_regions',
    db.Column('country_id', db.Integer, db.ForeignKey('country.id'), primary_key=True),
    db.Column('region_id', db.Integer, db.ForeignKey('region.id'), primary_key=True)
)

region_neighbors = db.Table('region_neighbors',
    db.Column('region_id', db.Integer, db.ForeignKey('region.id'), primary_key=True),
    db.Column('neighbor_id', db.Integer, db.ForeignKey('region.id'), primary_key=True)
)


# --- Models ---

class Country(SoftDeleteMixin, db.Model):
    """Represents a nation in the game."""
    __tablename__ = 'country' # Explicit table name is good practice

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    slug = db.Column(db.String(60), unique=True, index=True, nullable=False)
    flag_code = db.Column(db.String(2), nullable=True)
    currency_name = db.Column(db.String(50), nullable=True)
    currency_code = db.Column(db.String(3), nullable=True)

    # GeoJSON geometry for map display (stores polygon/multipolygon data)
    geometry = db.Column(db.Text, nullable=True)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)  # Hide country from map

    # Treasury
    treasury_gold = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    treasury_currency = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    reserved_gold = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)  # Gold reserved by pending laws
    reserved_currency = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)  # Currency reserved by pending laws

    # Military Budget
    military_budget_gold = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    military_budget_currency = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)

    # Tax Rates (stored as percentages, e.g., 5.0 = 5%)
    vat_tax_rate = db.Column(Numeric(5, 2), default=Decimal('5.0'), nullable=False)  # Default 5%
    import_tax_rate = db.Column(Numeric(5, 2), default=Decimal('10.0'), nullable=False)  # Default 10%
    work_tax_rate = db.Column(Numeric(5, 2), default=Decimal('10.0'), nullable=False)  # Default 10%

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Conquest Status
    is_conquered = db.Column(db.Boolean, default=False, nullable=False, index=True)
    conquered_by_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True)
    conquered_at = db.Column(db.DateTime, nullable=True)

    # --- Relationships ---
    # Relationship to Users (Citizens)
    citizens = db.relationship('User', back_populates='citizenship', lazy='dynamic', foreign_keys='User.citizenship_id')

    # Relationship to Regions it originally owned
    original_regions = db.relationship('Region', back_populates='original_owner', lazy='dynamic', foreign_keys='Region.original_owner_id')

    # Relationship to Regions it currently owns (Many-to-Many)
    current_regions = db.relationship(
        'Region',
        secondary=country_regions,
        lazy='dynamic',
        back_populates='current_owners' # Note: Changed from current_owner in Region model for clarity
    )

    # Relationship to its market items (Resource Market)
    market_items = db.relationship('CountryMarketItem', back_populates='country', lazy='dynamic', cascade="all, delete-orphan")

    # --- ADDED Gold Market Relationship HERE ---
    gold_market = db.relationship('GoldMarket', back_populates='country', uselist=False, cascade="all, delete-orphan")
    # --- END ADDED Relationship ---

    # Relationship to UserCurrency (multi-currency support)
    user_holdings = db.relationship('UserCurrency', back_populates='country', lazy='dynamic')

    # Relationship to Military Inventory (Hospitals, Forts, etc.)
    military_inventory = db.relationship('MilitaryInventory', back_populates='country', lazy='dynamic', cascade="all, delete-orphan")

    # Conquest relationship (self-referential)
    conquered_by = db.relationship('Country', foreign_keys=[conquered_by_id], remote_side='Country.id')

    def __init__(self, name, flag_code=None, currency_name=None, currency_code=None):
        """Initializes a new Country."""
        self.name = name
        self.slug = slugify(name)
        self.flag_code = flag_code
        self.currency_name = currency_name
        self.currency_code = currency_code

    def __repr__(self):
        """String representation of the Country object."""
        return f'<Country {self.name}>'

    @property
    def region_count(self):
        """Get the number of regions this country currently controls."""
        return self.current_regions.count()

    @property
    def has_starter_protection(self):
        """
        Check if country has starter protection.
        Countries with only 1 region cannot be attacked.
        This protection is temporary until admin disables it globally.
        """
        from app.models.game_settings import GameSettings
        # Check if starter protection is enabled globally (checks DB then config)
        if not GameSettings.is_starter_protection_enabled():
            return False
        # Country has protection if it has 1 or fewer regions
        return self.region_count <= 1


class Region(SoftDeleteMixin, db.Model):
    """Represents a geographical region within the game."""
    __tablename__ = 'region' # Explicit table name

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    slug = db.Column(db.String(60), unique=True, index=True, nullable=False)
    original_owner_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False)

    # GeoJSON geometry for map display (stores polygon/multipolygon data)
    geometry = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), nullable=True)  # Hex color for region display

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # --- Relationships ---
    # Relationship to its original owner (One-to-Many backref)
    original_owner = db.relationship('Country', back_populates='original_regions', foreign_keys=[original_owner_id])

    # Relationship to Users residing in this region
    residents = db.relationship('User', back_populates='current_region', lazy='dynamic', foreign_keys='User.current_region_id')

    # Relationship to Countries currently owning this region (Many-to-Many backref)
    # A region could theoretically be co-owned or disputed, hence Many-to-Many is flexible.
    # If a region can ONLY have one owner, this could be simplified, but M-M handles edge cases.
    current_owners = db.relationship(
        'Country',
        secondary=country_regions,
        lazy='dynamic', # Keep lazy=dynamic for potential multiple owners
        # uselist=False, # Removed - Allow list in case of co-ownership models later
        back_populates='current_regions' # Matches back_populates in Country
    )

    # Relationship to neighboring Regions (Many-to-Many self-referential)
    neighbors = db.relationship(
        'Region',
        secondary=region_neighbors,
        primaryjoin=(region_neighbors.c.region_id == id),
        secondaryjoin=(region_neighbors.c.neighbor_id == id),
        back_populates='neighbor_of', # Use back_populates for symmetrical relationship
        lazy='dynamic'
    )
    # Symmetrical relationship backref (needed if using back_populates on 'neighbors')
    neighbor_of = db.relationship(
        'Region',
        secondary=region_neighbors,
        primaryjoin=(region_neighbors.c.neighbor_id == id),
        secondaryjoin=(region_neighbors.c.region_id == id),
        back_populates='neighbors', # Link back to the 'neighbors' relationship
        lazy='dynamic'
    )

    # --- Convenience property for single owner (most common case) ---
    @property
    def current_owner(self):
        # Access the relationship (which is dynamic) and return the first owner, or None
        # This assumes the common case of a single owner.
        # Use .first() on the dynamic loader query.
        return self.current_owners.first()


    def __init__(self, name, original_owner_id):
        """Initializes a new Region."""
        self.name = name
        self.slug = slugify(name)
        self.original_owner_id = original_owner_id

    def __repr__(self):
        """String representation of the Region object."""
        return f'<Region {self.name}>'


class MilitaryInventory(db.Model):
    """Represents a country's military inventory (Hospitals, Forts, etc.)."""
    __tablename__ = 'military_inventory'

    # Composite primary key
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), primary_key=True)
    quality = db.Column(db.Integer, primary_key=True, default=1, nullable=False)  # Q1-Q5

    # Quantity held
    quantity = db.Column(db.Integer, default=0, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    country = db.relationship('Country', back_populates='military_inventory')
    resource = db.relationship('Resource')

    def __repr__(self):
        return f'<MilitaryInventory Country:{self.country_id} Resource:{self.resource_id} Q{self.quality} Qty:{self.quantity}>'


class ConstructionType(db.Enum):
    """Types of regional constructions."""
    HOSPITAL = "hospital"
    FORTRESS = "fortress"


class RegionalConstruction(db.Model):
    """
    Represents a construction (Hospital or Fortress) placed in a region.

    Hospitals: Provide wellness recovery bonus to fighters in battles in this region
    Fortresses: Provide defense bonus to the defending side in battles in this region

    Rules:
    - Only one construction of each type per region (can have both hospital AND fortress)
    - Can only be placed in regions controlled by the country
    - Cannot be placed if there's an active battle in the region
    - Uses resources from military inventory
    """
    __tablename__ = 'regional_constructions'

    id = db.Column(db.Integer, primary_key=True)

    # The region where the construction is placed
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False, index=True)

    # The country that owns this construction
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Type of construction (hospital or fortress)
    construction_type = db.Column(db.String(20), nullable=False, index=True)  # 'hospital' or 'fortress'

    # Quality of the construction (Q1-Q5, determines bonus strength)
    quality = db.Column(db.Integer, nullable=False, default=1)

    # Who placed the construction
    placed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Timestamps
    placed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    region = db.relationship('Region', backref=db.backref('constructions', lazy='dynamic'))
    country = db.relationship('Country', backref=db.backref('regional_constructions', lazy='dynamic'))
    placed_by = db.relationship('User', foreign_keys=[placed_by_user_id])

    # Unique constraint: only one of each type per region
    __table_args__ = (
        db.UniqueConstraint('region_id', 'construction_type', name='uq_region_construction_type'),
    )

    def __repr__(self):
        return f'<RegionalConstruction {self.construction_type} Q{self.quality} in Region:{self.region_id}>'

    @property
    def bonus_percentage(self):
        """Calculate the bonus percentage based on quality."""
        # Q1: 5%, Q2: 10%, Q3: 15%, Q4: 20%, Q5: 25%
        return self.quality * 5

    @property
    def display_name(self):
        """Return a display-friendly name."""
        return self.construction_type.title()

    @property
    def icon_class(self):
        """Return the FontAwesome icon class for this construction type."""
        if self.construction_type == 'hospital':
            return 'fa-hospital'
        elif self.construction_type == 'fortress':
            return 'fa-chess-rook'
        return 'fa-building'

    @property
    def icon_color(self):
        """Return the color for this construction type."""
        if self.construction_type == 'hospital':
            return '#ef4444'  # Red
        elif self.construction_type == 'fortress':
            return '#8b5cf6'  # Purple
        return '#22c55e'  # Green

    @staticmethod
    def get_region_hospital(region_id):
        """Get the hospital in a region, if any."""
        return RegionalConstruction.query.filter_by(
            region_id=region_id,
            construction_type='hospital'
        ).first()

    @staticmethod
    def get_region_fortress(region_id):
        """Get the fortress in a region, if any."""
        return RegionalConstruction.query.filter_by(
            region_id=region_id,
            construction_type='fortress'
        ).first()

    @staticmethod
    def can_place_construction(region_id, country_id, construction_type):
        """
        Check if a construction can be placed in a region.
        Returns (can_place: bool, error_message: str or None)
        """
        from app.models import Region, Battle, BattleStatus

        # Get the region
        region = db.session.get(Region, region_id)
        if not region:
            return False, "Region not found."

        # Check if country owns this region
        owner = region.current_owner
        if not owner or owner.id != country_id:
            return False, "Your country does not control this region."

        # Check for active battles in this region
        active_battle = Battle.query.filter_by(
            region_id=region_id,
            status=BattleStatus.ACTIVE
        ).first()
        if active_battle:
            return False, "Cannot place construction while there is an active battle in this region."

        # Check if construction of this type already exists
        existing = RegionalConstruction.query.filter_by(
            region_id=region_id,
            construction_type=construction_type
        ).first()
        if existing:
            return False, f"A {construction_type} already exists in this region (Q{existing.quality})."

        return True, None


class RegionalResource(db.Model):
    """
    Represents a natural resource deposit in a region.

    Resources are added by admins and deplete when extraction companies produce.
    Countries with these resources get +100% production bonus for extraction companies.

    Extractable resources: wheat, grape, clay, coal, iron_ore, oil, sand, stone
    """
    __tablename__ = 'regional_resources'

    id = db.Column(db.Integer, primary_key=True)

    # The region where the resource is located
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False, index=True)

    # The resource type (wheat, coal, iron_ore, etc.)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=False, index=True)

    # Amount of resource remaining (depletes as companies extract)
    amount = db.Column(db.Integer, nullable=False, default=0)

    # Initial amount when added (for tracking/display)
    initial_amount = db.Column(db.Integer, nullable=False, default=0)

    # Admin who added this resource
    added_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    region = db.relationship('Region', backref=db.backref('resources', lazy='dynamic'))
    resource = db.relationship('Resource')
    added_by = db.relationship('User', foreign_keys=[added_by_id])

    # Unique constraint: only one deposit of each resource type per region
    __table_args__ = (
        db.UniqueConstraint('region_id', 'resource_id', name='uq_region_resource'),
        db.Index('idx_regional_resource_lookup', 'region_id', 'resource_id'),
    )

    def __repr__(self):
        return f'<RegionalResource Region:{self.region_id} Resource:{self.resource_id} Amount:{self.amount}/{self.initial_amount}>'

    @property
    def is_depleted(self):
        """Check if the resource is fully depleted."""
        return self.amount <= 0

    @property
    def depletion_percentage(self):
        """Calculate how much of the resource has been used (0-100%)."""
        if self.initial_amount <= 0:
            return 100
        used = self.initial_amount - self.amount
        return min(100, max(0, (used / self.initial_amount) * 100))

    @property
    def remaining_percentage(self):
        """Calculate how much of the resource remains (0-100%)."""
        return 100 - self.depletion_percentage

    def deplete(self, amount):
        """
        Reduce the resource amount by the specified quantity.
        Returns the actual amount depleted (may be less if resource runs out).
        """
        if amount <= 0:
            return 0

        actual_depletion = min(amount, self.amount)
        self.amount -= actual_depletion
        return actual_depletion

    def replenish(self, amount):
        """
        Add more resource to this deposit (admin action).
        """
        if amount <= 0:
            return

        self.amount += amount
        self.initial_amount = max(self.initial_amount, self.amount)

    @staticmethod
    def get_country_resources(country_id):
        """
        Get all resources available in regions owned by a country.
        Returns a dict mapping resource_id to total amount available.
        """
        from sqlalchemy import func

        # Get all regions owned by this country
        country = db.session.get(Country, country_id)
        if not country:
            return {}

        # Sum up resources across all owned regions
        results = db.session.query(
            RegionalResource.resource_id,
            func.sum(RegionalResource.amount).label('total_amount')
        ).join(Region).join(
            country_regions,
            Region.id == country_regions.c.region_id
        ).filter(
            country_regions.c.country_id == country_id,
            RegionalResource.amount > 0
        ).group_by(RegionalResource.resource_id).all()

        return {r.resource_id: r.total_amount for r in results}

    @staticmethod
    def country_has_resource(country_id, resource_id):
        """
        Check if a country has any amount of the specified resource in its regions.
        Returns True if the country has at least 1 unit of the resource.
        """
        resources = RegionalResource.get_country_resources(country_id)
        return resources.get(resource_id, 0) > 0

    @staticmethod
    def get_extractable_resources():
        """
        Get the list of resource slugs that can be added as regional deposits.
        These are raw materials that require extraction skill.
        """
        return ['wheat', 'grape', 'clay', 'coal', 'iron-ore', 'oil', 'sand', 'stone']