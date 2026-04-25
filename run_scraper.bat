@echo off
:: BU Reddit Safety Monitor — Auto-run script
:: This file is used by Windows Task Scheduler to run the scraper automatically.
:: Do not move or rename this file.

:: Change this path to wherever you saved the bu-reddit-monitor folder
cd /d "C:\Users\morga\Desktop\CPO-Reddit-Monitor"

:: Run the script using Python
python scraper.py

:: Keep the window open for 10 seconds so you can see if it worked
timeout /t 10
