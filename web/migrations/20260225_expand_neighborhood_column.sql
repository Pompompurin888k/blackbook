-- Allow storing multiple neighborhoods (comma-separated canonical list).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'providers'
          AND column_name = 'neighborhood'
          AND data_type <> 'text'
    ) THEN
        ALTER TABLE providers
        ALTER COLUMN neighborhood TYPE TEXT;
    END IF;
END $$;
