from database import Database
import logging

logging.basicConfig(level=logging.INFO)
db = Database()

print("Fixing missing phones...")
try:
    with db.conn.cursor() as cur:
        # Update all providers with a dummy phone if they don't have one
        cur.execute("UPDATE providers SET phone = '254700000000' WHERE phone IS NULL")
        count = cur.rowcount
        db.conn.commit()
        print(f"✅ Updated {count} providers with dummy phones.")
except Exception as e:
    print(f"❌ Error: {e}")
