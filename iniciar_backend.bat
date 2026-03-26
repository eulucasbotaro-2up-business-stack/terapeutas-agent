@echo off
title Terapeutas Agent Backend
cd /d C:\Users\VENDATECH01\Desktop\terapeutas-agent

:loop
echo [%date% %time%] Iniciando backend...
C:\Users\VENDATECH01\AppData\Local\Python\pythoncore-3.14-64\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 3000
echo [%date% %time%] Backend parou. Reiniciando em 3 segundos...
timeout /t 3 /nobreak >nul
goto loop
