-- Add profile_photos column if it doesn't exist
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='providers' AND column_name='profile_photos') THEN
        ALTER TABLE providers ADD COLUMN profile_photos JSONB;
    END IF;
END $$;
