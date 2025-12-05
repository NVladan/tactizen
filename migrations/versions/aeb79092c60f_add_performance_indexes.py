"""Add performance indexes

Revision ID: aeb79092c60f
Revises: e41dc688ed79
Create Date: 2025-12-05 01:42:54.235690

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'aeb79092c60f'
down_revision = 'e41dc688ed79'
branch_labels = None
depends_on = None


def table_exists(connection, table_name):
    """Check if a table exists."""
    result = connection.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = :table_name"
    ), {"table_name": table_name})
    return result.fetchone()[0] > 0


def index_exists(connection, table_name, index_name):
    """Check if an index exists on a table."""
    if not table_exists(connection, table_name):
        return False
    result = connection.execute(text(
        f"SHOW INDEX FROM {table_name} WHERE Key_name = :index_name"
    ), {"index_name": index_name})
    return result.fetchone() is not None


def create_index_if_not_exists(connection, index_name, table_name, columns):
    """Create an index only if it doesn't already exist."""
    if not table_exists(connection, table_name):
        print(f"  Skipped {index_name}: table {table_name} doesn't exist")
        return

    if not index_exists(connection, table_name, index_name):
        if isinstance(columns, list):
            cols = ", ".join(columns)
        else:
            cols = columns
        try:
            connection.execute(text(f"CREATE INDEX {index_name} ON {table_name}({cols})"))
            print(f"  Created index: {index_name}")
        except Exception as e:
            print(f"  Skipped {index_name}: {e}")
    else:
        print(f"  Index exists: {index_name}")


def upgrade():
    connection = op.get_bind()

    print("Adding performance indexes...")

    # User table indexes
    create_index_if_not_exists(connection, "idx_user_wallet", "user", "base_wallet_address")
    create_index_if_not_exists(connection, "idx_user_citizenship", "user", "citizenship_id")
    create_index_if_not_exists(connection, "idx_user_region", "user", "current_region_id")
    create_index_if_not_exists(connection, "idx_user_party", "user", "party_id")

    # Company table indexes
    create_index_if_not_exists(connection, "idx_company_owner", "company", "owner_id")
    create_index_if_not_exists(connection, "idx_company_country", "company", "country_id")
    create_index_if_not_exists(connection, "idx_company_type", "company", "company_type")

    # Market indexes
    create_index_if_not_exists(connection, "idx_market_item_country_resource", "country_market_item", ["country_id", "resource_id"])
    create_index_if_not_exists(connection, "idx_gold_market_country", "gold_market", "country_id")

    # NFT indexes
    create_index_if_not_exists(connection, "idx_nft_user", "nft_inventory", "user_id")
    create_index_if_not_exists(connection, "idx_nft_user_equipped", "nft_inventory", ["user_id", "is_equipped"])
    create_index_if_not_exists(connection, "idx_nft_token", "nft_inventory", "token_id")

    # Employment indexes
    create_index_if_not_exists(connection, "idx_employment_company", "employment", "company_id")
    create_index_if_not_exists(connection, "idx_employment_user", "employment", "user_id")

    # Inventory indexes
    create_index_if_not_exists(connection, "idx_inventory_user", "inventory_item", "user_id")
    create_index_if_not_exists(connection, "idx_inventory_user_resource", "inventory_item", ["user_id", "resource_id"])

    # Currency indexes
    create_index_if_not_exists(connection, "idx_user_currency_user", "user_currency", "user_id")
    create_index_if_not_exists(connection, "idx_user_currency_user_country", "user_currency", ["user_id", "country_id"])

    # Region indexes
    create_index_if_not_exists(connection, "idx_region_owner", "region", "original_owner_id")

    # Battle indexes (table may be named 'battles')
    create_index_if_not_exists(connection, "idx_battle_war", "battles", "war_id")
    create_index_if_not_exists(connection, "idx_battle_region", "battles", "region_id")
    create_index_if_not_exists(connection, "idx_battle_status", "battles", "status")

    # War indexes
    create_index_if_not_exists(connection, "idx_war_attacker", "wars", "attacker_country_id")
    create_index_if_not_exists(connection, "idx_war_defender", "wars", "defender_country_id")
    create_index_if_not_exists(connection, "idx_war_status", "wars", "status")

    # Message indexes
    create_index_if_not_exists(connection, "idx_message_recipient", "message", "recipient_id")
    create_index_if_not_exists(connection, "idx_message_sender", "message", "sender_id")

    # Political party indexes
    create_index_if_not_exists(connection, "idx_party_country", "political_party", "country_id")
    create_index_if_not_exists(connection, "idx_party_president", "political_party", "president_id")

    # Country regions (for country page queries)
    create_index_if_not_exists(connection, "idx_country_region", "country_regions", ["country_id", "region_id"])

    print("Performance indexes added successfully!")


def drop_index_if_exists(connection, index_name, table_name):
    """Drop an index only if it exists."""
    if not table_exists(connection, table_name):
        return
    if index_exists(connection, table_name, index_name):
        connection.execute(text(f"DROP INDEX {index_name} ON {table_name}"))
        print(f"  Dropped index: {index_name}")


def downgrade():
    connection = op.get_bind()

    print("Removing performance indexes...")

    drop_index_if_exists(connection, "idx_user_wallet", "user")
    drop_index_if_exists(connection, "idx_user_citizenship", "user")
    drop_index_if_exists(connection, "idx_user_region", "user")
    drop_index_if_exists(connection, "idx_user_party", "user")

    drop_index_if_exists(connection, "idx_company_owner", "company")
    drop_index_if_exists(connection, "idx_company_country", "company")
    drop_index_if_exists(connection, "idx_company_type", "company")

    drop_index_if_exists(connection, "idx_market_item_country_resource", "country_market_item")
    drop_index_if_exists(connection, "idx_gold_market_country", "gold_market")

    drop_index_if_exists(connection, "idx_nft_user", "nft_inventory")
    drop_index_if_exists(connection, "idx_nft_user_equipped", "nft_inventory")
    drop_index_if_exists(connection, "idx_nft_token", "nft_inventory")

    drop_index_if_exists(connection, "idx_employment_company", "employment")
    drop_index_if_exists(connection, "idx_employment_user", "employment")

    drop_index_if_exists(connection, "idx_inventory_user", "inventory_item")
    drop_index_if_exists(connection, "idx_inventory_user_resource", "inventory_item")

    drop_index_if_exists(connection, "idx_user_currency_user", "user_currency")
    drop_index_if_exists(connection, "idx_user_currency_user_country", "user_currency")

    drop_index_if_exists(connection, "idx_region_owner", "region")

    drop_index_if_exists(connection, "idx_battle_war", "battles")
    drop_index_if_exists(connection, "idx_battle_region", "battles")
    drop_index_if_exists(connection, "idx_battle_status", "battles")

    drop_index_if_exists(connection, "idx_war_attacker", "wars")
    drop_index_if_exists(connection, "idx_war_defender", "wars")
    drop_index_if_exists(connection, "idx_war_status", "wars")

    drop_index_if_exists(connection, "idx_message_recipient", "message")
    drop_index_if_exists(connection, "idx_message_sender", "message")

    drop_index_if_exists(connection, "idx_party_country", "political_party")
    drop_index_if_exists(connection, "idx_party_president", "political_party")

    drop_index_if_exists(connection, "idx_country_region", "country_regions")

    print("Performance indexes removed!")
