@echo off
chcp 936 >nul
title 电影分镜提取工具
cd /d "F:\AIProjects\movie-storyboard-ai"
echo.
echo  ============================================
echo    电影分镜提取工具正在启动，请稍候...
echo  ============================================
echo.
echo   启动后浏览器会自动打开工具页面。
echo   使用期间请不要关闭本窗口；关闭窗口即停止工具。
echo.
"D:\python\python.exe" app.py
echo.
echo  工具已停止，按任意键关闭窗口。
pause >nul
