@echo off
chcp 936 >nul
title 电影分镜提取工具（公网分享模式）
cd /d "F:\AIProjects\movie-storyboard-ai"
echo.
echo  ============================================
echo    正在尝试生成公网临时链接...
echo  ============================================
echo.
echo   若成功，终端会出现一个 https://...gradio.live 链接，
echo   把它发给任何人即可在浏览器使用；关闭本窗口即失效。
echo.
echo   若提示 "Could not create share link"，说明当前网络
echo   不支持 Gradio 官方隧道（常见）。请改用：
echo     1) 同一 WiFi 下用局域网 IP 访问；
echo     2) 部署到 Hugging Face Spaces 获得永久在线链接。
echo.
set GRADIO_SHARE=1
"D:\python\python.exe" app.py
echo.
echo  服务已停止，按任意键关闭窗口。
pause >nul
