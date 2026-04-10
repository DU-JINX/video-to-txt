@echo off
cd /d "%~dp0"
uvicorn server:app --host 0.0.0.0 --port %TRANSCRIBE_PORT% --timeout-keep-alive 600
