"""Verify database tables were created successfully."""

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Set DATABASE_URL environment variable")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    ))
    tables = [row[0] for row in result]
    
    print("Tables in database:")
    for table in tables:
        print(f"  - {table}")
    
    expected_tables = [
        "pdf_document",
        "pdf_chunk",
        "team",
        "team_member",
        "subscription",
        "usage_personal",
        "usage_team"
    ]
    
    print("\nExpected tables:")
    for table in expected_tables:
        status = "[OK]" if table in tables else "[MISSING]"
        print(f"  {status} {table}")
    
    # Check for pgvector extension
    result = conn.execute(text(
        "SELECT extname FROM pg_extension WHERE extname = 'vector'"
    ))
    has_vector = result.fetchone() is not None
    print(f"\npgvector extension: {'[OK] Installed' if has_vector else '[MISSING] Not installed'}")

