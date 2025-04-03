"""
Migration script to add the claimed column to the providers table.
This script should be run once to update the database schema.
"""

from sqlalchemy import text
from ..session import engine, SessionLocal

def run_migration():
    """Run the migration to add the claimed column to the providers table"""
    print("Starting migration: Add claimed column to providers table")
    
    db = SessionLocal()
    try:
        # Check if the column already exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'providers' AND column_name = 'claimed'
        """))
        
        if result.fetchone():
            print("Column 'claimed' already exists in the providers table. Skipping migration.")
            return
        
        # Add the claimed column with a default value of False
        db.execute(text("""
            ALTER TABLE providers 
            ADD COLUMN claimed BOOLEAN NOT NULL DEFAULT FALSE
        """))
        
        db.commit()
        print("Successfully added 'claimed' column to providers table")
        
    except Exception as e:
        db.rollback()
        print(f"Error running migration: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migration() 