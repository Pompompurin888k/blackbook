from database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
print("Connected to DB for migration.")

add_columns_query = """
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='age') THEN
        ALTER TABLE providers ADD COLUMN age INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='height_cm') THEN
        ALTER TABLE providers ADD COLUMN height_cm INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='weight_kg') THEN
        ALTER TABLE providers ADD COLUMN weight_kg INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='build') THEN
        ALTER TABLE providers ADD COLUMN build VARCHAR(50);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='services') THEN
        ALTER TABLE providers ADD COLUMN services VARCHAR(255); -- Simplified for now
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='bio') THEN
        ALTER TABLE providers ADD COLUMN bio TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='nearby_places') THEN
        ALTER TABLE providers ADD COLUMN nearby_places TEXT;
    END IF;
END $$;
"""

try:
    with db.conn.cursor() as cur:
        cur.execute(add_columns_query)
        db.conn.commit()
        print("✅ Schema migration completed (Columns added).")
except Exception as e:
    print(f"❌ Migration failed: {e}")
    db.conn.rollback()

print("Retrying seeding...")
try:
    db.seed_test_providers()
    print("✅ Seeding invoked.")
except Exception as e:
    print(f"❌ Re-seeding failed: {e}")
