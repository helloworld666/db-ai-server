"""
db-ai-server MCP Server 安装脚本
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: str, description: str):
    """运行命令"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"执行: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ 成功")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"✗ 失败")
        if result.stderr:
            print(result.stderr)
        return False
    
    return True


def check_python_version():
    """检查Python版本"""
    print(f"{'='*60}")
    print("检查Python版本")
    print(f"{'='*60}")
    
    version = sys.version_info
    print(f"当前Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("✗ Python版本过低，需要Python 3.10或更高版本")
        return False
    
    print("✓ Python版本符合要求")
    return True


def check_ollama():
    """检查Ollama是否安装"""
    print(f"\n{'='*60}")
    print("检查Ollama")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run("ollama --version", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Ollama已安装: {result.stdout.strip()}")
            
            # 检查服务是否运行
            try:
                result = subprocess.run("ollama list", shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    print("✓ Ollama服务正在运行")
                    return True
                else:
                    print("⚠ Ollama服务未运行，请执行: ollama serve")
                    return False
            except:
                print("⚠ 无法连接到Ollama服务")
                return False
        else:
            print("✗ Ollama未安装")
            print("\n请访问 https://ollama.com/ 下载安装Ollama")
            return False
    except:
        print("✗ Ollama未安装")
        return False


def create_directories():
    """创建必要的目录"""
    print(f"\n{'='*60}")
    print("创建目录结构")
    print(f"{'='*60}")
    
    directories = [
        "logs",
        "config/examples"
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True)
            print(f"✓ 创建目录: {directory}")
        else:
            print(f"- 目录已存在: {directory}")


def install_dependencies():
    """安装Python依赖"""
    print(f"\n{'='*60}")
    print("安装Python依赖")
    print(f"{'='*60}")
    
    if not run_command("pip install -r requirements.txt", "安装依赖包"):
        print("\n⚠ 部分依赖安装失败，请手动检查")
        return False
    
    return True


def pull_model(model: str = "gemma-4-e4b-it"):
    """拉取Ollama模型"""
    print(f"\n{'='*60}")
    print(f"拉取Ollama模型: {model}")
    print(f"{'='*60}")
    
    # 检查模型是否已存在
    result = subprocess.run(f"ollama list", shell=True, capture_output=True, text=True)
    if model in result.stdout:
        print(f"✓ 模型 {model} 已存在")
        return True
    
    # 拉取模型
    if run_command(f"ollama pull {model}", f"拉取模型 {model}"):
        print(f"\n✓ 模型 {model} 拉取成功")
        return True
    else:
        print(f"\n✗ 模型 {model} 拉取失败")
        return False


def create_example_configs():
    """创建示例配置文件"""
    print(f"\n{'='*60}")
    print("创建示例配置文件")
    print(f"{'='*60}")
    
    # MySQL Schema示例
    mysql_example = """{
  "database_name": "example_mysql_db",
  "database_type": "mysql",
  "description": "MySQL数据库示例",
  "tables": [
    {
      "name": "customers",
      "description": "客户信息表",
      "columns": [
        {
          "name": "id",
          "type": "bigint",
          "primary_key": true,
          "auto_increment": true
        },
        {
          "name": "name",
          "type": "varchar(100)",
          "required": true
        },
        {
          "name": "email",
          "type": "varchar(100)",
          "unique": true
        }
      ]
    }
  ]
}"""
    
    # SQL Server Schema示例
    sqlserver_example = """{
  "database_name": "example_sqlserver_db",
  "database_type": "sqlserver",
  "description": "SQL Server数据库示例",
  "tables": [
    {
      "name": "Employees",
      "description": "员工信息表",
      "columns": [
        {
          "name": "EmployeeID",
          "type": "INT IDENTITY(1,1)",
          "primary_key": true
        },
        {
          "name": "Name",
          "type": "NVARCHAR(100)",
          "required": true
        },
        {
          "name": "Department",
          "type": "NVARCHAR(50)"
        }
      ]
    }
  ]
}"""
    
    try:
        with open("config/examples/mysql_schema_example.json", "w", encoding="utf-8") as f:
            f.write(mysql_example)
        print("✓ 创建 MySQL Schema 示例")
        
        with open("config/examples/sqlserver_schema_example.json", "w", encoding="utf-8") as f:
            f.write(sqlserver_example)
        print("✓ 创建 SQL Server Schema 示例")
        
    except Exception as e:
        print(f"✗ 创建示例配置失败: {e}")
        return False
    
    return True


def print_next_steps():
    """打印后续步骤"""
    print(f"\n{'='*60}")
    print("安装完成！")
    print(f"{'='*60}")
    print("\n后续步骤:")
    print("\n1. 配置数据库Schema")
    print("   编辑 config/database_schema.json，添加您的数据库表结构")
    print("\n2. 启动Ollama服务（如果未启动）")
    print("   ollama serve")
    print("\n3. 启动MCP Server")
    print("   python src/mcp_server.py")
    print("\n4. 测试连接")
    print("   python tests/test_client.py")
    print("\n5. 查看文档")
    print("   - docs/API.md - API文档")
    print("   - docs/CONFIGURATION.md - 配置说明")
    print("   - docs/DEPLOYMENT.md - 部署指南")
    print(f"\n{'='*60}")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("  db-ai-server MCP Server 安装向导")
    print("="*60)
    
    # 检查Python版本
    if not check_python_version():
        print("\n安装失败：Python版本不符合要求")
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 安装依赖
    if not install_dependencies():
        print("\n警告：依赖安装失败，但可以继续")
    
    # 检查Ollama
    ollama_installed = check_ollama()
    
    if ollama_installed:
        # 拉取模型
        print("\n是否需要下载推荐模型 gemma-4-e4b-it ? (y/n): ", end="")
        response = input().strip().lower()
        if response == 'y':
            pull_model("gemma-4-e4b-it")
    
    # 创建示例配置
    create_example_configs()
    
    # 打印后续步骤
    print_next_steps()
    
    print("\n安装向导完成！")


if __name__ == "__main__":
    main()
