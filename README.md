# Backend - Chat with PDF

FastAPI backend for the Chat with PDF application.

## Quick Start

### Windows (PowerShell)

1. **Create and activate virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Copy `.env.example` to `.env`
   - Fill in your Clerk, Supabase, and OpenAI credentials

4. **Run database migration:**
   ```powershell
   python run_migration.py
   ```
   Or use the Supabase Dashboard SQL Editor (see SETUP.md)

5. **Start the server:**
   ```powershell
   .\run_server.ps1
   ```
   Or manually:
   ```powershell
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Linux/Mac

1. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Run database migration:**
   ```bash
   python run_migration.py
   # Or: psql $DATABASE_URL -f migrations/001_initial_schema.sql
   ```

5. **Start the server:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Documentation

Once running, visit:
- **API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app
│   ├── auth.py              # Clerk JWT verification
│   ├── db.py                # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── routes/              # API routes
│   ├── services/            # Business logic
│   └── workers/             # Celery tasks
├── migrations/              # SQL migrations
├── alembic/                 # Alembic migrations
└── requirements.txt         # Python dependencies
```

## Detailed Setup

See [SETUP.md](SETUP.md) for detailed setup instructions, troubleshooting, and environment variable configuration.

## Data Model

See [DATA_MODEL_SUMMARY.md](DATA_MODEL_SUMMARY.md) for complete documentation of data relationships, authentication scopes, and access patterns.

