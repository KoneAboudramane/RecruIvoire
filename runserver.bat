@echo off
REM Lance le serveur de dev avec le bon Python (3.13, venv .venv313).
REM Le simple "python manage.py runserver" resout vers l'ancien Python 3.14
REM du poste, incompatible avec Django 5.1 (admin Django plante).
cd /d "%~dp0"
".venv313\Scripts\python.exe" manage.py runserver %*
