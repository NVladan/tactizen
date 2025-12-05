import logging
from logging.config import fileConfig
import os
import sys
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# --- Flask Integration ---
# Get the Flask app object from the Alembic configuration context
# This is set up by Flask-Migrate when running 'flask db' commands
from flask import current_app

# Add project root to Python path if needed, though often not necessary
# when run via 'flask db' as the app context is already established.
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from the Flask app's config
# current_app should be available here when run via 'flask db'
config.set_main_option('sqlalchemy.url',
                       current_app.config['SQLALCHEMY_DATABASE_URI'].replace('%', '%%'))

# --- CORRECTED LINE ---
# Get the SQLAlchemy database object directly from the extensions dict
# The key 'sqlalchemy' holds the SQLAlchemy() instance itself.
db_instance = current_app.extensions['sqlalchemy']
# --- END CORRECTION ---

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = db_instance.metadata # Use the metadata from the retrieved instance

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Add render_as_batch for SQLite compatibility if needed later
        render_as_batch=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get the engine from the Flask-SQLAlchemy db object within current_app
    connectable = db_instance.engine # Use the engine from the retrieved instance

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
             # Add render_as_batch for SQLite compatibility if needed later
            render_as_batch=True,
            # Include compare_type=True for better type comparison during autogenerate
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
