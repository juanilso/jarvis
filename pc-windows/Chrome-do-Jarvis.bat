@echo off
rem Abre o Chrome do Jarvis (perfil separado) e libera o acesso so pela sua rede Tailscale.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Chrome-do-Jarvis.ps1"
