@echo off
title CS2 Skin Pricer Bot
setlocal
cd /d "%~dp0"

if not defined DISCORD_BOT_TOKEN (
  echo [ERROR] DISCORD_BOT_TOKEN is not set.
  echo Create your bot at https://discord.com/developers/applications
  echo Then set the token once:
  echo   setx DISCORD_BOT_TOKEN "your-bot-token"
  echo Restart this file after that.
  pause
  exit /b 1
)

"C:\Users\vlads\AppData\Local\Programs\Python\Python312\python.exe" discord_bot.py
pause