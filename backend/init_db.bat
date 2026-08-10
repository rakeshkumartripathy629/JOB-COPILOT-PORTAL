@echo off
cd /d %~dp0
call .venv\Scripts\activate.bat
python -c "from app.db.session import engine; from app.db.base import Base; Base.metadata.create_all(bind=engine); print('Database initialized')"
pause
