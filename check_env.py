"""Check if environment variables are set correctly."""

import os
from dotenv import load_dotenv

load_dotenv()

print("=== Environment Variables Check ===\n")

# Check OpenAI API Key
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key and len(openai_key) > 10 and not openai_key.startswith("sk-your"):
    print(f"[OK] OPENAI_API_KEY: SET (length: {len(openai_key)})")
else:
    print("[MISSING] OPENAI_API_KEY: NOT SET or INVALID")
    print("  Please add your OpenAI API key to .env file")
    print("  Get it from: https://platform.openai.com/api-keys")

# Check Database URL
db_url = os.getenv("DATABASE_URL")
if db_url and "neondb" in db_url:
    print(f"[OK] DATABASE_URL: SET")
else:
    print("[MISSING] DATABASE_URL: NOT SET")

# Check Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if supabase_url and supabase_key:
    print(f"[OK] SUPABASE_URL: SET")
    print(f"[OK] SUPABASE_SERVICE_ROLE_KEY: SET")
else:
    print("[MISSING] SUPABASE credentials: NOT SET (needed for PDF storage)")

# Check Clerk
clerk_api = os.getenv("CLERK_FRONTEND_API")
clerk_jwks = os.getenv("CLERK_JWKS_URL")
clerk_issuer = os.getenv("CLERK_ISSUER")
clerk_instance = os.getenv("CLERK_INSTANCE")

if clerk_jwks and clerk_issuer:
    print(f"[OK] CLERK_JWKS_URL: SET")
    print(f"[OK] CLERK_ISSUER: SET")
elif clerk_instance:
    print(f"[OK] CLERK_INSTANCE: SET (will auto-generate URLs)")
else:
    print("[MISSING] Clerk configuration: NOT SET")
    print("  Set CLERK_JWKS_URL and CLERK_ISSUER, or CLERK_INSTANCE")
    print("  Get from: Clerk Dashboard > API Keys > JWT Template")

if clerk_api:
    print(f"[OK] CLERK_FRONTEND_API: SET")
else:
    print("[INFO] CLERK_FRONTEND_API: NOT SET (optional, for frontend)")

# Check Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
print(f"[OK] REDIS_URL: {redis_url}")

print("\n=== Summary ===")
if openai_key and len(openai_key) > 10:
    print("[OK] Ready to start server (OpenAI key is set)")
else:
    print("[ERROR] Please set OPENAI_API_KEY in .env file before starting server")

