# Backend Setup Guide

## Prerequisites

- Python 3.11+ (you have 3.13.6 ✓)
- Supabase account with Postgres database
- Redis (for Celery) - can use local or cloud Redis
- Clerk account for authentication

## Installation Steps

### 1. Virtual Environment (Already Done ✓)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development

# Clerk
CLERK_FRONTEND_API=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://your-instance.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://your-instance.clerk.accounts.dev

# Supabase Database
DATABASE_URL=postgresql://postgres:password@db.project.supabase.co:5432/postgres

# Or use individual components:
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_HOST=db.project.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres

# Supabase API
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...

# OpenAI
OPENAI_API_KEY=sk-...

# Redis
REDIS_URL=redis://localhost:6379/0
```

### 3. Database Migration

#### Option A: Using Supabase Dashboard (Recommended)

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Copy the contents of `migrations/001_initial_schema.sql`
4. Paste and run it in the SQL Editor

#### Option B: Using Python Script

Create a file `run_migration.py`:

```python
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not set in .env")
    exit(1)

engine = create_engine(DATABASE_URL)

with open("migrations/001_initial_schema.sql", "r") as f:
    sql = f.read()

with engine.connect() as conn:
    conn.execute(text(sql))
    conn.commit()

print("Migration completed successfully!")
```

Then run:
```powershell
.\venv\Scripts\Activate.ps1
python run_migration.py
```

#### Option C: Using psql (if installed)

```powershell
$env:DATABASE_URL = "postgresql://..."
psql $env:DATABASE_URL -f migrations/001_initial_schema.sql
```

### 4. Run the API Server

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Local: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

### 5. Run Celery Worker (Optional, for background tasks)

In a separate terminal:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
celery -A app.workers.celery_app worker --loglevel=info
```

## Testing the Setup

1. **Health Check**:
   ```powershell
   curl http://localhost:8000/health
   ```

2. **API Documentation**:
   Open http://localhost:8000/docs in your browser

3. **Test Authentication** (requires valid Clerk token):
   ```powershell
   $token = "your_clerk_jwt_token"
   curl -H "Authorization: Bearer $token" http://localhost:8000/api/auth/me
   ```

## Troubleshooting

### "psql is not recognized"
- Use Option A (Supabase Dashboard) or Option B (Python script) for migrations
- Or install PostgreSQL client tools

### "uvicorn is not recognized"
- Make sure virtual environment is activated: `.\venv\Scripts\Activate.ps1`
- Verify installation: `pip list | Select-String uvicorn`

### Database Connection Issues
- Verify `DATABASE_URL` is correct
- Check Supabase project settings for connection string
- Ensure database is accessible from your IP (Supabase allows all by default)

### Clerk JWT Verification Fails
- Verify `CLERK_FRONTEND_API` matches your Clerk instance
- Check that `CLERK_JWKS_URL` and `CLERK_ISSUER` are correct
- Ensure token is not expired

## Next Steps

- Implement PDF upload endpoint
- Set up Celery tasks for PDF processing
- Connect frontend to backend API
- Implement vector search for chat

