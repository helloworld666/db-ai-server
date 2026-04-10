#!/bin/bash
# 代码质量检查脚本

echo "=========================================="
echo "运行代码格式化检查 (Black)"
echo "=========================================="

# 检查 Black 是否安装
if ! command -v black &> /dev/null; then
    echo "❌ Black 未安装，正在安装..."
    pip install black
fi

# 运行 Black 检查（不修改文件）
echo "🔍 检查代码格式..."
black --check --diff src/

# 如果检查失败，提示用户
if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  代码格式不符合规范！"
    echo "运行以下命令自动修复："
    echo "  black src/"
    echo ""
    exit 1
fi

echo "✅ 代码格式检查通过！"
echo ""

# 可选：运行 isort 检查导入顺序
if command -v isort &> /dev/null; then
    echo "🔍 检查导入顺序..."
    isort --check-only --diff src/
    if [ $? -ne 0 ]; then
        echo "⚠️  导入顺序不符合规范！"
        echo "运行以下命令自动修复："
        echo "  isort src/"
        exit 1
    fi
    echo "✅ 导入顺序检查通过！"
fi

echo ""
echo "🎉 所有检查通过！"
