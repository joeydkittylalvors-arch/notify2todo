@echo off
chcp 65001 >nul
echo ============================================
echo   notify2todo - Windows 定时任务注册
echo ============================================
echo.

set "PROJECT_DIR=C:\Users\Lenovo\notify2todo"

REM 删除已有任务
schtasks /Delete /TN "notify2todo" /F 2>nul

REM 创建新任务 - 每天上午9点运行
schtasks /Create /TN "notify2todo" ^
  /TR "powershell -ExecutionPolicy Bypass -File \"%PROJECT_DIR%\run_auto.ps1\"" ^
  /SC DAILY ^
  /ST 09:00 ^
  /F ^
  /RL HIGHEST

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   定时任务注册成功！
    echo   任务名称: notify2todo
    echo   执行时间: 每天上午 9:00
    echo   运行脚本: %PROJECT_DIR%\run_auto.bat
    echo ============================================
    echo.
    echo 你现在可以先双击 run_auto.bat 手动测试一次
) else (
    echo.
    echo [错误] 任务注册失败，请以管理员身份运行此脚本。
)

pause
