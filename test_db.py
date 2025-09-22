import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env file
load_dotenv()

# Print to confirm .env values loaded
print("DATABASE_URL =", os.getenv("DATABASE_URL"))
print("DIRECT_URL   =", os.getenv("DIRECT_URL"))

# Create engine using DIRECT_URL for migration/testing
engine = create_engine(os.getenv("DIRECT_URL"))

# Test connection and query version
try:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
        print("✅ Connected to Supabase PostgreSQL")
        print("🔍 Version:", version)
except Exception as e:
    print("❌ Connection failed:", e)