"""
测试 Web 应用基本功能

验证：
1. 模板文件是否存在
2. 静态文件目录是否存在
3. 应用能否正常导入
"""
import sys
from pathlib import Path

# Windows 编码问题
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_templates_exist():
    """测试模板文件是否存在"""
    print("\n[测试1] 检查模板文件...")

    templates_dir = Path("templates")
    if not templates_dir.exists():
        print("✗ 模板目录不存在")
        return False

    required_templates = [
        "base.html",
        "login.html",
        "dashboard.html",
        "ups.html",
        "videos.html",
        "config.html",
        "bilibili_login.html"
    ]

    for template in required_templates:
        template_path = templates_dir / template
        if template_path.exists():
            print(f"  ✓ {template}")
        else:
            print(f"  ✗ {template} 不存在")
            return False

    return True


def test_static_dirs_exist():
    """测试静态文件目录是否存在"""
    print("\n[测试2] 检查静态文件目录...")

    static_dir = Path("static")
    if not static_dir.exists():
        print("✗ static 目录不存在")
        return False

    js_dir = static_dir / "js"
    css_dir = static_dir / "css"

    if js_dir.exists():
        print(f"  ✓ static/js/")
    else:
        print(f"  ✗ static/js/ 不存在")
        return False

    if css_dir.exists():
        print(f"  ✓ static/css/")
    else:
        print(f"  ✗ static/css/ 不存在")
        return False

    # 检查 main.js
    main_js = js_dir / "main.js"
    if main_js.exists():
        print(f"  ✓ static/js/main.js")
    else:
        print(f"  ✗ static/js/main.js 不存在")
        return False

    return True


def test_app_import():
    """测试应用能否正常导入"""
    print("\n[测试3] 测试应用导入...")

    try:
        from src.web import app
        print("  ✓ src.web 导入成功")
        print(f"  ✓ 应用标题: {app.title}")
        print(f"  ✓ 应用版本: {app.version}")
        return True
    except Exception as e:
        print(f"  ✗ 导入失败: {e}")
        return False


def test_routes():
    """测试路由是否注册"""
    print("\n[测试4] 检查路由...")

    try:
        from src.web import app

        # 检查关键路由
        routes = [route.path for route in app.routes]

        required_routes = [
            "/auth/login",
            "/",
            "/ups",
            "/videos",
            "/config",
            "/bilibili-login"
        ]

        for route in required_routes:
            if route in routes:
                print(f"  ✓ {route}")
            else:
                print(f"  ✗ {route} 未注册")
                return False

        return True
    except Exception as e:
        print(f"  ✗ 检查路由失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 50)
    print("Web 应用基本功能测试")
    print("=" * 50)

    results = []

    results.append(("模板文件", test_templates_exist()))
    results.append(("静态文件目录", test_static_dirs_exist()))
    results.append(("应用导入", test_app_import()))
    results.append(("路由注册", test_routes()))

    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n✓ 所有测试通过！")
        print("\n启动命令: python main.py --web")
        print("访问地址: http://localhost:8000")
        print("默认密码: 123456")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())