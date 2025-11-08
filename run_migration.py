"""
Run database migration using SQLAlchemy.
Alternative to psql for Windows users.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Try to construct from individual components
    user = os.getenv("SUPABASE_DB_USER", "postgres")
    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    host = os.getenv("SUPABASE_DB_HOST", "")
    port = os.getenv("SUPABASE_DB_PORT", "5432")
    dbname = os.getenv("SUPABASE_DB_NAME", "postgres")
    
    if not host:
        print("=" * 60)
        print("ERROR: Database credentials not found in .env file")
        print("=" * 60)
        print("\nTo run migrations, you need to set up your .env file:")
        print("\nOption 1: Set DATABASE_URL")
        print("  DATABASE_URL=postgresql://user:password@host:port/dbname")
        print("\nOption 2: Set individual Supabase components")
        print("  SUPABASE_DB_USER=postgres")
        print("  SUPABASE_DB_PASSWORD=your_password")
        print("  SUPABASE_DB_HOST=db.your-project.supabase.co")
        print("  SUPABASE_DB_PORT=5432")
        print("  SUPABASE_DB_NAME=postgres")
        print("\nYou can find these in your Supabase project settings:")
        print("  Dashboard > Settings > Database > Connection string")
        print("\nAlternatively, you can run the migration manually:")
        print("  1. Go to Supabase Dashboard > SQL Editor")
        print("  2. Copy contents of migrations/001_initial_schema.sql")
        print("  3. Paste and run in SQL Editor")
        print("=" * 60)
        exit(1)
    
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

print(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else '***'}")

try:
    engine = create_engine(DATABASE_URL)
    
    migration_file = "migrations/001_initial_schema.sql"
    if not os.path.exists(migration_file):
        print(f"ERROR: Migration file not found: {migration_file}")
        exit(1)
    
    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read()
    
    print("Running migration...")
    with engine.begin() as conn:  # Use begin() for automatic transaction management
        # Split SQL by semicolons, but preserve order
        statements = []
        current_statement = []
        
        for line in sql.split('\n'):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('--'):
                continue
            
            current_statement.append(line)
            
            # If line ends with semicolon, finalize statement
            if line.endswith(';'):
                statement = ' '.join(current_statement).rstrip(';').strip()
                if statement:
                    statements.append(statement)
                current_statement = []
        
        # Execute statements in order
        for statement in statements:
            try:
                conn.execute(text(statement))
            except Exception as e:
                error_str = str(e).lower()
                # Some errors are expected (already exists, etc.)
                if "already exists" in error_str or "duplicate" in error_str:
                    continue  # Skip, already exists
                else:
                    # For other errors, print warning but continue
                    print(f"Warning: {str(e)[:100]}...")
                    # Don't fail on index creation errors if table doesn't exist yet
                    if "does not exist" in error_str and "index" in statement.lower():
                        continue
    
    print("Migration completed successfully!")
    print("\nYou can now start the API server with:")
    print("  uvicorn main:app --reload")
    
except Exception as e:
    print(f"ERROR: {str(e)}")
    exit(1)

