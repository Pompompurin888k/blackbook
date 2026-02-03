from database import Database
import logging

logging.basicConfig(level=logging.INFO)

db = Database()
print("Connected to DB.")

try:
    with db.conn.cursor() as cur:
        # Check current count
        cur.execute("SELECT COUNT(*) FROM providers")
        print(f"Current count: {cur.fetchone()['count']}")
        
        # Try to insert ONE test provider manually
        cur.execute("""
            INSERT INTO providers (telegram_id, display_name, city, neighborhood, is_active, is_verified, is_online)
            VALUES (9999, 'TestUser', 'Nairobi', 'TestHood', TRUE, TRUE, TRUE)
            ON CONFLICT (telegram_id) DO NOTHING
        """)
        db.conn.commit()
        print("Inserted TestUser.")
        
        # Check count again
        cur.execute("SELECT COUNT(*) FROM providers")
        print(f"New count: {cur.fetchone()['count']}")
        
        # Run the full seeding
        print("Running full seeding...")
        db.seed_test_providers()
        
        cur.execute("SELECT COUNT(*) FROM providers")
        print(f"Final count: {cur.fetchone()['count']}")

except Exception as e:
    print(f"Error: {e}")
