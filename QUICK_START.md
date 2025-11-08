# Quick Start Guide

## Fixed Issues

✅ **Database connection error fixed**: The app no longer tries to connect to the database on startup. Database connections are now lazy (only when needed).

## Starting the Server

### Option 1: Using the PowerShell script
```powershell
cd backend
.\run_server.ps1
```

### Option 2: Manual start
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Direct Python command
```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Important Notes

1. **No `.env` file needed to start**: The server will start even without database credentials. Database connections will only be attempted when you make API calls that require them.

2. **Set up `.env` for full functionality**: 
   - Create `.env` file in `backend/` directory
   - Add your Supabase, Clerk, and OpenAI credentials
   - See `.env.example` for required variables

3. **Run migrations before using database features**:
   ```powershell
   python run_migration.py
   ```
   Or use Supabase Dashboard SQL Editor

## Testing

Once the server is running:
- **Health check**: http://localhost:8000/health
- **API docs**: http://localhost:8000/docs
- **Root endpoint**: http://localhost:8000/

## Troubleshooting

### "Module not found" errors
- Make sure virtual environment is activated: `.\venv\Scripts\Activate.ps1`
- Verify dependencies: `pip list`

### Database connection errors (when making API calls)
- Check `.env` file has correct `DATABASE_URL` or Supabase credentials
- Verify Supabase database is accessible
- Run migrations: `python run_migration.py`

### Port already in use
- Change port: `uvicorn main:app --reload --port 8001`
- Or stop the process using port 8000

