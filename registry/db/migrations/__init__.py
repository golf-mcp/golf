"""
Database migrations package.
This package contains scripts to update the database schema.
"""

from registry.db.migrations.add_claimed_to_providers import run_migration as add_claimed_to_providers

__all__ = ['add_claimed_to_providers'] 