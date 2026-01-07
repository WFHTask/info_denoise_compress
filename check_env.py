#!/usr/bin/env python
"""
TrendRadar 开发环境验证脚本
验证所有依赖是否正确安装
"""

import sys
import subprocess

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"✓ Python 版本: {version.major}.{version.minor}.{version.micro}")
    return version.major >= 3 and version.minor >= 10

def check_dependencies():
    """检查核心依赖"""
    dependencies = [
        ("requests", "HTTP 请求库"),
        ("pytz", "时区处理"),
        ("yaml", "YAML 配置解析"),
        ("fastmcp", "MCP 服务器框架"),
        ("websockets", "WebSocket 支持"),
        ("boto3", "AWS S3 兼容存储"),
        ("feedparser", "RSS 解析"),
    ]
    
    all_ok = True
    for module, desc in dependencies:
        try:
            __import__(module)
            print(f"✓ {module}: {desc}")
        except ImportError as e:
            print(f"✗ {module}: {desc} - 未安装")
            all_ok = False
    
    return all_ok

def check_trendradar():
    """检查 TrendRadar 模块"""
    try:
        sys.path.insert(0, 'TrendRadar')
        from trendradar import context
        print("✓ TrendRadar 模块可正常导入")
        return True
    except ImportError as e:
        print(f"✗ TrendRadar 模块导入失败: {e}")
        return False

def check_docker():
    """检查 Docker 环境"""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✓ Docker: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("✗ Docker 未安装或不可用")
    return False

def main():
    print("=" * 50)
    print("TrendRadar 开发环境验证")
    print("=" * 50)
    print()
    
    results = []
    
    print("1. Python 环境检查")
    print("-" * 30)
    results.append(check_python_version())
    print()
    
    print("2. 依赖包检查")
    print("-" * 30)
    results.append(check_dependencies())
    print()
    
    print("3. TrendRadar 模块检查")
    print("-" * 30)
    results.append(check_trendradar())
    print()
    
    print("4. Docker 环境检查")
    print("-" * 30)
    results.append(check_docker())
    print()
    
    print("=" * 50)
    if all(results):
        print("✓ 所有检查通过！开发环境配置完成。")
        return 0
    else:
        print("✗ 部分检查未通过，请检查上述错误信息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
