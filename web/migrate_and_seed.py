from database import Database


def main():
    """
    Manual helper:
    1) Connects and auto-runs startup migrations
    2) Seeds development providers
    """
    db = Database()
    print("Connected. Startup migrations already applied.")
    db.seed_test_providers()
    print("Seed complete.")


if __name__ == "__main__":
    main()
