@echo off
REM 代码格式化脚本 (Windows)

echo ==========================================
echo 自动格式化代码
echo ==========================================

REM 检查 Black 是否安装
where black >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [INFO] 正在安装 Black...
    pip install black
)

REM 运行 Black 格式化
echo [INFO] 正在格式化代码...
black src/

REM 格式化导入顺序
where isort >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] 正在格式化导入顺序...
    isort src/
)

echo.
echo [SUCCESS] 代码格式化完成！
echo.
echo [TIP] 查看修改内容：
echo   git diff src/
