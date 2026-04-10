@echo off
REM 代码质量检查脚本 (Windows)

echo ==========================================
echo 运行代码格式化检查 (Black)
echo ==========================================

REM 检查 Black 是否安装
where black >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] Black 未安装，正在安装...
    pip install black
)

REM 运行 Black 检查（不修改文件）
echo [INFO] 检查代码格式...
black --check --diff src/

REM 如果检查失败，提示用户
if %ERRORLEVEL% neq 0 (
    echo.
    echo [WARNING] 代码格式不符合规范！
    echo 运行以下命令自动修复：
    echo   black src/
    echo.
    exit /b 1
)

echo [OK] 代码格式检查通过！
echo.

REM 可选：运行 isort 检查导入顺序
where isort >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] 检查导入顺序...
    isort --check-only --diff src/
    if %ERRORLEVEL% neq 0 (
        echo [WARNING] 导入顺序不符合规范！
        echo 运行以下命令自动修复：
        echo   isort src/
        exit /b 1
    )
    echo [OK] 导入顺序检查通过！
)

echo.
echo [SUCCESS] 所有检查通过！
