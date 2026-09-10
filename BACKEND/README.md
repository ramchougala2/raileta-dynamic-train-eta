# RAILETA Backend

## Environment
Set the RailRadar key before starting FastAPI.

PowerShell:

```powershell
$env:RAILRADAR_API_KEY="PASTE_YOUR_KEY_HERE"
```

Do not put the key in React/frontend code.

## Install

```powershell
cd "C:\Users\ramch\OneDrive\Attachments\Desktop\RAILETA\BACKEND"
pip install -r requirements.txt
```

## Run

```powershell
uvicorn main:app --reload
```

Swagger: http://127.0.0.1:8000/docs
