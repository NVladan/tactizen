-- NFT System Database Schema
-- CyberRepublik GamePlay NFT System

-- NFT ownership tracking
CREATE TABLE IF NOT EXISTS nft_inventory (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nft_type VARCHAR(50) NOT NULL, -- 'player' or 'company'
    category VARCHAR(50) NOT NULL, -- 'combat_boost', 'energy_regen', 'production_boost', etc.
    tier INTEGER NOT NULL CHECK (tier >= 1 AND tier <= 5), -- 1-5 (Q1-Q5)
    bonus_value INTEGER NOT NULL, -- Bonus percentage or value (e.g., 25 = 25%)
    token_id BIGINT NOT NULL UNIQUE, -- On-chain token ID
    contract_address VARCHAR(42) NOT NULL,
    is_equipped BOOLEAN DEFAULT FALSE,
    equipped_to_profile BOOLEAN DEFAULT FALSE, -- For player NFTs
    equipped_to_company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL, -- For company NFTs
    acquired_via VARCHAR(20) NOT NULL, -- 'purchase', 'drop', 'upgrade'
    acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_uri TEXT, -- IPFS or HTTP URI for metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_nft_inventory_user_id ON nft_inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_nft_inventory_token_id ON nft_inventory(token_id);
CREATE INDEX IF NOT EXISTS idx_nft_inventory_tier ON nft_inventory(tier);
CREATE INDEX IF NOT EXISTS idx_nft_inventory_equipped ON nft_inventory(is_equipped);
CREATE INDEX IF NOT EXISTS idx_nft_inventory_company ON nft_inventory(equipped_to_company_id);

-- Track player's equipped NFT slots (max 3)
CREATE TABLE IF NOT EXISTS player_nft_slots (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    slot_1_nft_id INTEGER REFERENCES nft_inventory(id) ON DELETE SET NULL,
    slot_2_nft_id INTEGER REFERENCES nft_inventory(id) ON DELETE SET NULL,
    slot_3_nft_id INTEGER REFERENCES nft_inventory(id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Track company's equipped NFT slots (1-3 based on quality)
CREATE TABLE IF NOT EXISTS company_nft_slots (
    company_id INTEGER PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    slot_1_nft_id INTEGER REFERENCES nft_inventory(id) ON DELETE SET NULL,
    slot_2_nft_id INTEGER REFERENCES nft_inventory(id) ON DELETE SET NULL,
    slot_3_nft_id INTEGER REFERENCES nft_inventory(id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NFT burn/upgrade history
CREATE TABLE IF NOT EXISTS nft_burn_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    burned_nft_ids BIGINT[] NOT NULL, -- Array of token IDs burned (3 for upgrade)
    minted_nft_id BIGINT, -- New higher-tier NFT (NULL if just burning)
    tier_from INTEGER NOT NULL CHECK (tier_from >= 1 AND tier_from <= 5),
    tier_to INTEGER CHECK (tier_to >= 1 AND tier_to <= 5), -- NULL if just burning
    transaction_hash VARCHAR(66),
    burned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for burn history
CREATE INDEX IF NOT EXISTS idx_nft_burn_history_user_id ON nft_burn_history(user_id);
CREATE INDEX IF NOT EXISTS idx_nft_burn_history_minted_nft_id ON nft_burn_history(minted_nft_id);

-- NFT drop history (for analytics)
CREATE TABLE IF NOT EXISTS nft_drop_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nft_id INTEGER NOT NULL REFERENCES nft_inventory(id) ON DELETE CASCADE,
    drop_source VARCHAR(50) NOT NULL, -- 'work', 'training', 'study', 'battle', 'daily_login'
    tier INTEGER NOT NULL CHECK (tier >= 1 AND tier <= 3), -- Only Q1-Q3 can drop
    category VARCHAR(50) NOT NULL,
    dropped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for drop history
CREATE INDEX IF NOT EXISTS idx_nft_drop_history_user_id ON nft_drop_history(user_id);
CREATE INDEX IF NOT EXISTS idx_nft_drop_history_drop_source ON nft_drop_history(drop_source);
CREATE INDEX IF NOT EXISTS idx_nft_drop_history_tier ON nft_drop_history(tier);
CREATE INDEX IF NOT EXISTS idx_nft_drop_history_dropped_at ON nft_drop_history(dropped_at);

-- NFT marketplace listings (for future P2P trading)
CREATE TABLE IF NOT EXISTS nft_marketplace (
    id SERIAL PRIMARY KEY,
    nft_id INTEGER NOT NULL REFERENCES nft_inventory(id) ON DELETE CASCADE,
    seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    price_zen DECIMAL(18, 8) NOT NULL CHECK (price_zen > 0),
    price_gold DECIMAL(18, 2), -- Optional: allow gold payment too
    listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP, -- Optional expiry
    is_active BOOLEAN DEFAULT TRUE,
    sold_at TIMESTAMP,
    buyer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT unique_active_listing UNIQUE (nft_id, is_active)
);

-- Index for marketplace
CREATE INDEX IF NOT EXISTS idx_nft_marketplace_seller_id ON nft_marketplace(seller_id);
CREATE INDEX IF NOT EXISTS idx_nft_marketplace_is_active ON nft_marketplace(is_active);
CREATE INDEX IF NOT EXISTS idx_nft_marketplace_tier ON nft_marketplace(nft_id);

-- NFT trade history
CREATE TABLE IF NOT EXISTS nft_trade_history (
    id SERIAL PRIMARY KEY,
    nft_id INTEGER NOT NULL REFERENCES nft_inventory(id) ON DELETE CASCADE,
    from_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    price_zen DECIMAL(18, 8),
    price_gold DECIMAL(18, 2),
    trade_type VARCHAR(20) NOT NULL, -- 'sale', 'gift', 'transfer'
    transaction_hash VARCHAR(66), -- On-chain transaction
    traded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for trade history
CREATE INDEX IF NOT EXISTS idx_nft_trade_history_from_user_id ON nft_trade_history(from_user_id);
CREATE INDEX IF NOT EXISTS idx_nft_trade_history_to_user_id ON nft_trade_history(to_user_id);
CREATE INDEX IF NOT EXISTS idx_nft_trade_history_nft_id ON nft_trade_history(nft_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_nft_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER nft_inventory_updated_at
    BEFORE UPDATE ON nft_inventory
    FOR EACH ROW
    EXECUTE FUNCTION update_nft_updated_at();

CREATE TRIGGER player_nft_slots_updated_at
    BEFORE UPDATE ON player_nft_slots
    FOR EACH ROW
    EXECUTE FUNCTION update_nft_updated_at();

CREATE TRIGGER company_nft_slots_updated_at
    BEFORE UPDATE ON company_nft_slots
    FOR EACH ROW
    EXECUTE FUNCTION update_nft_updated_at();

-- Constraint: Ensure NFTs equipped to player profiles are player type
CREATE OR REPLACE FUNCTION check_player_nft_type()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.equipped_to_profile = TRUE THEN
        IF (SELECT nft_type FROM nft_inventory WHERE id = NEW.id) != 'player' THEN
            RAISE EXCEPTION 'Only player NFTs can be equipped to profiles';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_player_nft_type_trigger
    BEFORE UPDATE ON nft_inventory
    FOR EACH ROW
    WHEN (NEW.equipped_to_profile = TRUE)
    EXECUTE FUNCTION check_player_nft_type();

-- Constraint: Ensure NFTs equipped to companies are company type
CREATE OR REPLACE FUNCTION check_company_nft_type()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.equipped_to_company_id IS NOT NULL THEN
        IF (SELECT nft_type FROM nft_inventory WHERE id = NEW.id) != 'company' THEN
            RAISE EXCEPTION 'Only company NFTs can be equipped to companies';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_company_nft_type_trigger
    BEFORE UPDATE ON nft_inventory
    FOR EACH ROW
    WHEN (NEW.equipped_to_company_id IS NOT NULL)
    EXECUTE FUNCTION check_company_nft_type();

-- View: Get player's total bonuses from equipped NFTs
CREATE OR REPLACE VIEW player_nft_bonuses AS
SELECT
    pns.user_id,
    SUM(CASE WHEN ni.category = 'combat_boost' THEN ni.bonus_value ELSE 0 END) as combat_boost,
    SUM(CASE WHEN ni.category = 'energy_regen' THEN ni.bonus_value ELSE 0 END) as energy_regen,
    SUM(CASE WHEN ni.category = 'wellness_regen' THEN ni.bonus_value ELSE 0 END) as wellness_regen,
    SUM(CASE WHEN ni.category = 'energy_efficiency' THEN ni.bonus_value ELSE 0 END) as energy_efficiency,
    SUM(CASE WHEN ni.category = 'wellness_efficiency' THEN ni.bonus_value ELSE 0 END) as wellness_efficiency
FROM player_nft_slots pns
LEFT JOIN nft_inventory ni ON ni.id IN (pns.slot_1_nft_id, pns.slot_2_nft_id, pns.slot_3_nft_id)
WHERE ni.nft_type = 'player'
GROUP BY pns.user_id;

-- View: Get company's total bonuses from equipped NFTs
CREATE OR REPLACE VIEW company_nft_bonuses AS
SELECT
    cns.company_id,
    SUM(CASE WHEN ni.category = 'production_boost' THEN ni.bonus_value ELSE 0 END) as production_boost,
    SUM(CASE WHEN ni.category = 'material_efficiency' THEN ni.bonus_value ELSE 0 END) as material_efficiency,
    SUM(CASE WHEN ni.category = 'upgrade_discount' THEN ni.bonus_value ELSE 0 END) as upgrade_discount,
    SUM(CASE WHEN ni.category = 'speed_boost' THEN ni.bonus_value ELSE 0 END) as speed_boost
FROM company_nft_slots cns
LEFT JOIN nft_inventory ni ON ni.id IN (cns.slot_1_nft_id, cns.slot_2_nft_id, cns.slot_3_nft_id)
WHERE ni.nft_type = 'company'
GROUP BY cns.company_id;

-- View: NFT statistics by tier
CREATE OR REPLACE VIEW nft_tier_stats AS
SELECT
    tier,
    COUNT(*) as total_count,
    COUNT(CASE WHEN nft_type = 'player' THEN 1 END) as player_count,
    COUNT(CASE WHEN nft_type = 'company' THEN 1 END) as company_count,
    COUNT(CASE WHEN is_equipped = TRUE THEN 1 END) as equipped_count,
    COUNT(CASE WHEN acquired_via = 'purchase' THEN 1 END) as purchased_count,
    COUNT(CASE WHEN acquired_via = 'drop' THEN 1 END) as dropped_count,
    COUNT(CASE WHEN acquired_via = 'upgrade' THEN 1 END) as upgraded_count
FROM nft_inventory
GROUP BY tier
ORDER BY tier;

COMMENT ON TABLE nft_inventory IS 'Stores all NFTs owned by players';
COMMENT ON TABLE player_nft_slots IS 'Tracks which NFTs are equipped to player profiles (max 3)';
COMMENT ON TABLE company_nft_slots IS 'Tracks which NFTs are equipped to companies (1-3 based on quality)';
COMMENT ON TABLE nft_burn_history IS 'History of all NFT burns and upgrades';
COMMENT ON TABLE nft_drop_history IS 'History of NFT loot drops for analytics';
COMMENT ON TABLE nft_marketplace IS 'P2P marketplace listings (future feature)';
COMMENT ON TABLE nft_trade_history IS 'History of all NFT trades between players';
