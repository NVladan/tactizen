"""
SQLAlchemy models for NFT system
"""
import json
from datetime import datetime
from app import db


class NFTInventory(db.Model):
    """NFT ownership and metadata"""
    __tablename__ = 'nft_inventory'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    nft_type = db.Column(db.String(50), nullable=False)  # 'player' or 'company'
    category = db.Column(db.String(50), nullable=False)  # 'combat_boost', etc.
    tier = db.Column(db.Integer, nullable=False)  # 1-5
    bonus_value = db.Column(db.Integer, nullable=False)
    token_id = db.Column(db.BigInteger, unique=True, nullable=False)
    contract_address = db.Column(db.String(42), nullable=False)
    is_equipped = db.Column(db.Boolean, default=False)
    equipped_to_profile = db.Column(db.Boolean, default=False)
    equipped_to_company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='SET NULL'), nullable=True)
    acquired_via = db.Column(db.String(20), nullable=False)  # 'purchase', 'drop', 'upgrade'
    acquired_at = db.Column(db.DateTime, default=datetime.utcnow)
    metadata_uri = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = db.relationship('User', backref=db.backref('nfts', lazy='dynamic'))
    equipped_company = db.relationship('Company', backref=db.backref('equipped_nfts', lazy='dynamic'))

    def __repr__(self):
        return f'<NFTInventory {self.id}: {self.nft_type} {self.category} Q{self.tier}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        from app.blockchain.nft_config import get_nft_name, get_nft_description, get_nft_image_url

        return {
            'id': self.id,
            'user_id': self.user_id,
            'nft_type': self.nft_type,
            'category': self.category,
            'tier': self.tier,
            'bonus_value': self.bonus_value,
            'token_id': self.token_id,
            'contract_address': self.contract_address,
            'is_equipped': self.is_equipped,
            'equipped_to_profile': self.equipped_to_profile,
            'equipped_to_company_id': self.equipped_to_company_id,
            'acquired_via': self.acquired_via,
            'acquired_at': self.acquired_at.isoformat() if self.acquired_at else None,
            'metadata_uri': self.metadata_uri,
            'name': get_nft_name(self.nft_type, self.category, self.tier),
            'description': get_nft_description(self.nft_type, self.category, self.tier),
            'image_url': get_nft_image_url(self.nft_type, self.category, self.tier)
        }


class PlayerNFTSlots(db.Model):
    """Player's equipped NFT slots"""
    __tablename__ = 'player_nft_slots'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    slot_1_nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='SET NULL'), nullable=True)
    slot_2_nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='SET NULL'), nullable=True)
    slot_3_nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='SET NULL'), nullable=True)
    slot_1_last_modified = db.Column(db.DateTime, nullable=True)
    slot_2_last_modified = db.Column(db.DateTime, nullable=True)
    slot_3_last_modified = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('nft_slots', uselist=False))
    slot_1_nft = db.relationship('NFTInventory', foreign_keys=[slot_1_nft_id], backref='slot_1_users')
    slot_2_nft = db.relationship('NFTInventory', foreign_keys=[slot_2_nft_id], backref='slot_2_users')
    slot_3_nft = db.relationship('NFTInventory', foreign_keys=[slot_3_nft_id], backref='slot_3_users')

    def __repr__(self):
        return f'<PlayerNFTSlots user_id={self.user_id}>'

    def get_equipped_nfts(self):
        """Get list of equipped NFT objects"""
        nfts = []
        if self.slot_1_nft:
            nfts.append(self.slot_1_nft)
        if self.slot_2_nft:
            nfts.append(self.slot_2_nft)
        if self.slot_3_nft:
            nfts.append(self.slot_3_nft)
        return nfts

    def get_slot_ids(self):
        """Get list of equipped NFT IDs"""
        return [
            self.slot_1_nft_id,
            self.slot_2_nft_id,
            self.slot_3_nft_id
        ]

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'slot_1_nft_id': self.slot_1_nft_id,
            'slot_2_nft_id': self.slot_2_nft_id,
            'slot_3_nft_id': self.slot_3_nft_id,
            'slot_1_nft': self.slot_1_nft.to_dict() if self.slot_1_nft else None,
            'slot_2_nft': self.slot_2_nft.to_dict() if self.slot_2_nft else None,
            'slot_3_nft': self.slot_3_nft.to_dict() if self.slot_3_nft else None
        }


class CompanyNFTSlots(db.Model):
    """Company's equipped NFT slots"""
    __tablename__ = 'company_nft_slots'

    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), primary_key=True)
    slot_1_nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='SET NULL'), nullable=True)
    slot_2_nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='SET NULL'), nullable=True)
    slot_3_nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='SET NULL'), nullable=True)
    slot_1_last_modified = db.Column(db.DateTime, nullable=True)
    slot_2_last_modified = db.Column(db.DateTime, nullable=True)
    slot_3_last_modified = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = db.relationship('Company', backref=db.backref('nft_slots', uselist=False))
    slot_1_nft = db.relationship('NFTInventory', foreign_keys=[slot_1_nft_id], backref='company_slot_1')
    slot_2_nft = db.relationship('NFTInventory', foreign_keys=[slot_2_nft_id], backref='company_slot_2')
    slot_3_nft = db.relationship('NFTInventory', foreign_keys=[slot_3_nft_id], backref='company_slot_3')

    def __repr__(self):
        return f'<CompanyNFTSlots company_id={self.company_id}>'

    def get_equipped_nfts(self):
        """Get list of equipped NFT objects"""
        nfts = []
        if self.slot_1_nft:
            nfts.append(self.slot_1_nft)
        if self.slot_2_nft:
            nfts.append(self.slot_2_nft)
        if self.slot_3_nft:
            nfts.append(self.slot_3_nft)
        return nfts

    def get_slot_ids(self):
        """Get list of equipped NFT IDs"""
        return [
            self.slot_1_nft_id,
            self.slot_2_nft_id,
            self.slot_3_nft_id
        ]

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'company_id': self.company_id,
            'slot_1_nft_id': self.slot_1_nft_id,
            'slot_2_nft_id': self.slot_2_nft_id,
            'slot_3_nft_id': self.slot_3_nft_id,
            'slot_1_nft': self.slot_1_nft.to_dict() if self.slot_1_nft else None,
            'slot_2_nft': self.slot_2_nft.to_dict() if self.slot_2_nft else None,
            'slot_3_nft': self.slot_3_nft.to_dict() if self.slot_3_nft else None
        }


class NFTBurnHistory(db.Model):
    """History of NFT burns and upgrades"""
    __tablename__ = 'nft_burn_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    _burned_nft_ids = db.Column('burned_nft_ids', db.Text, nullable=False)  # Store as JSON string
    minted_nft_id = db.Column(db.BigInteger, nullable=True)
    tier_from = db.Column(db.Integer, nullable=False)
    tier_to = db.Column(db.Integer, nullable=True)
    transaction_hash = db.Column(db.String(66), nullable=True)
    burned_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('nft_burns', lazy='dynamic'))

    @property
    def burned_nft_ids(self):
        """Deserialize JSON to list"""
        if self._burned_nft_ids:
            return json.loads(self._burned_nft_ids)
        return []

    @burned_nft_ids.setter
    def burned_nft_ids(self, value):
        """Serialize list to JSON"""
        self._burned_nft_ids = json.dumps(value)

    def __repr__(self):
        return f'<NFTBurnHistory {self.id}: {len(self.burned_nft_ids)} NFTs Q{self.tier_from}→Q{self.tier_to}>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'burned_nft_ids': self.burned_nft_ids,
            'minted_nft_id': self.minted_nft_id,
            'tier_from': self.tier_from,
            'tier_to': self.tier_to,
            'transaction_hash': self.transaction_hash,
            'burned_at': self.burned_at.isoformat() if self.burned_at else None
        }


class NFTDropHistory(db.Model):
    """History of NFT loot drops"""
    __tablename__ = 'nft_drop_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='CASCADE'), nullable=False)
    drop_source = db.Column(db.String(50), nullable=False)
    tier = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    dropped_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('nft_drops', lazy='dynamic'))
    nft = db.relationship('NFTInventory', backref=db.backref('drop_record', uselist=False))

    def __repr__(self):
        return f'<NFTDropHistory {self.id}: {self.drop_source} Q{self.tier}>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'nft_id': self.nft_id,
            'drop_source': self.drop_source,
            'tier': self.tier,
            'category': self.category,
            'dropped_at': self.dropped_at.isoformat() if self.dropped_at else None
        }


class NFTMarketplace(db.Model):
    """NFT marketplace listings for P2P trading"""
    __tablename__ = 'nft_marketplace'

    id = db.Column(db.Integer, primary_key=True)
    nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='CASCADE'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    price_zen = db.Column(db.Numeric(18, 8), nullable=False)
    price_gold = db.Column(db.Numeric(18, 2), nullable=True)
    listed_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    sold_at = db.Column(db.DateTime, nullable=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)

    # Relationships
    nft = db.relationship('NFTInventory', backref=db.backref('marketplace_listing', uselist=False))
    seller = db.relationship('User', foreign_keys=[seller_id], backref=db.backref('nft_sales', lazy='dynamic'))
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref=db.backref('nft_purchases', lazy='dynamic'))

    def __repr__(self):
        return f'<NFTMarketplace {self.id}: NFT#{self.nft_id} {self.price_zen} ZEN>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'nft_id': self.nft_id,
            'nft': self.nft.to_dict() if self.nft else None,
            'seller_id': self.seller_id,
            'seller_username': self.seller.username if self.seller else None,
            'price_zen': float(self.price_zen) if self.price_zen else None,
            'price_gold': float(self.price_gold) if self.price_gold else None,
            'listed_at': self.listed_at.isoformat() if self.listed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'sold_at': self.sold_at.isoformat() if self.sold_at else None,
            'buyer_id': self.buyer_id
        }


class NFTTradeHistory(db.Model):
    """History of all NFT trades"""
    __tablename__ = 'nft_trade_history'

    id = db.Column(db.Integer, primary_key=True)
    nft_id = db.Column(db.Integer, db.ForeignKey('nft_inventory.id', ondelete='CASCADE'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    price_zen = db.Column(db.Numeric(18, 8), nullable=True)
    price_gold = db.Column(db.Numeric(18, 2), nullable=True)
    trade_type = db.Column(db.String(20), nullable=False)  # 'sale', 'gift', 'transfer'
    transaction_hash = db.Column(db.String(66), nullable=True)
    traded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    nft = db.relationship('NFTInventory', backref=db.backref('trade_history', lazy='dynamic'))
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref=db.backref('nft_trades_sent', lazy='dynamic'))
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref=db.backref('nft_trades_received', lazy='dynamic'))

    def __repr__(self):
        return f'<NFTTradeHistory {self.id}: {self.trade_type} NFT#{self.nft_id}>'

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'nft_id': self.nft_id,
            'from_user_id': self.from_user_id,
            'from_username': self.from_user.username if self.from_user else None,
            'to_user_id': self.to_user_id,
            'to_username': self.to_user.username if self.to_user else None,
            'price_zen': float(self.price_zen) if self.price_zen else None,
            'price_gold': float(self.price_gold) if self.price_gold else None,
            'trade_type': self.trade_type,
            'transaction_hash': self.transaction_hash,
            'traded_at': self.traded_at.isoformat() if self.traded_at else None
        }
