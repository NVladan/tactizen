"""Create ZEN market tables directly"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv('DATABASE_HOST'),
    user=os.getenv('DATABASE_USER'),
    password=os.getenv('DATABASE_PASSWORD'),
    database=os.getenv('DATABASE_NAME')
)

cursor = conn.cursor()

# Create zen_market table
cursor.execute("""
CREATE TABLE IF NOT EXISTS zen_market (
    id INT AUTO_INCREMENT PRIMARY KEY,
    initial_exchange_rate DECIMAL(10, 4) NOT NULL DEFAULT 50.00,
    price_level INT NOT NULL DEFAULT 0,
    progress_within_level INT NOT NULL DEFAULT 0,
    volume_per_level INT NOT NULL DEFAULT 100,
    price_adjustment_per_level DECIMAL(10, 4) NOT NULL DEFAULT 0.50,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_zen_market_price_level (price_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")

# Create zen_price_history table
cursor.execute("""
CREATE TABLE IF NOT EXISTS zen_price_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    market_id INT NOT NULL,
    rate_open DECIMAL(10, 4) NOT NULL,
    rate_high DECIMAL(10, 4) NOT NULL,
    rate_low DECIMAL(10, 4) NOT NULL,
    rate_close DECIMAL(10, 4) NOT NULL,
    recorded_date DATE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES zen_market(id),
    UNIQUE KEY unique_daily_zen_rate (market_id, recorded_date),
    INDEX idx_zen_history_lookup (market_id, recorded_date),
    INDEX ix_zen_price_history_market_id (market_id),
    INDEX ix_zen_price_history_recorded_date (recorded_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")

# Create zen_transaction table
cursor.execute("""
CREATE TABLE IF NOT EXISTS zen_transaction (
    id INT AUTO_INCREMENT PRIMARY KEY,
    market_id INT NOT NULL,
    user_id INT NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,
    zen_amount DECIMAL(18, 8) NOT NULL,
    gold_amount DECIMAL(20, 8) NOT NULL,
    exchange_rate DECIMAL(10, 4) NOT NULL,
    blockchain_tx_hash VARCHAR(66) NULL,
    blockchain_status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (market_id) REFERENCES zen_market(id),
    FOREIGN KEY (user_id) REFERENCES user(id),
    INDEX ix_zen_transaction_blockchain_tx_hash (blockchain_tx_hash),
    INDEX ix_zen_transaction_created_at (created_at),
    INDEX ix_zen_transaction_market_id (market_id),
    INDEX ix_zen_transaction_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")

# Insert default ZEN market
cursor.execute("""
    INSERT IGNORE INTO zen_market (id, initial_exchange_rate, price_level, progress_within_level, volume_per_level, price_adjustment_per_level, created_at, updated_at)
    VALUES (1, 50.00, 0, 0, 100, 0.50, NOW(), NOW())
""")

# Mark migration as applied
cursor.execute('INSERT INTO alembic_version (version_num) VALUES ("a1b2c3d4e5f6")')

conn.commit()
print("ZEN market tables created successfully!")
conn.close()
