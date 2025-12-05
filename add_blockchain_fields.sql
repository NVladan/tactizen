-- Add blockchain fields to user table
ALTER TABLE user ADD COLUMN base_wallet_address VARCHAR(42) NULL;
ALTER TABLE user ADD COLUMN citizenship_nft_token_id INT NULL;
ALTER TABLE user ADD COLUMN government_nft_token_id INT NULL;

-- Add index
CREATE INDEX ix_user_base_wallet_address ON user(base_wallet_address);
