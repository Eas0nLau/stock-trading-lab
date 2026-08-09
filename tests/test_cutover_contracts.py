import ast
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_ROOT = ROOT / "src" / "stock_lab"

LEGACY_IMPORT_ROOTS = {"task", "utils", "实时监控", "游资溢价分析"}
LEGACY_TABLES = {
    "akshare_sh000001",
    "t_指数情绪周期_市场宽度",
    "t_指数情绪周期_每日分析",
    "t_热门板块情绪_每日分析",
    "stock_basic",
    "stock_daily",
    "stock_kdj",
    "t_stock_5_min_k",
    "t_韭研公社异动解析",
    "t_龙虎榜",
    "t_龙虎榜_营业部_上榜历史数据",
    "t_龙虎榜_营业部_上榜次数最多",
    "t_龙虎榜_营业部_全部",
    "t_同花顺板块列表",
    "t_同花顺板块成分股",
    "t_同花顺股票板块概念对应关系",
}
LEGACY_REDIS_PATTERNS = (
    re.compile(r"(?<!v1:)fund_flow:history:"),
    re.compile(r"fund_flow_概念"),
    re.compile(r"策略选股:"),
)
LEGACY_STORAGE_MIGRATION_FILES = {
    "src/stock_lab/jobs/redis_fact_migration.py",
}
LEGACY_STORAGE_TABLE_ALLOWLIST = {}
WRAPPER_LIMITS = {
    "task/data_sources.py": 80,
    "task/_5_韭研公社异动.py": 80,
    "utils/热门板块情绪算法.py": 100,
}
FORBIDDEN_WRAPPER_IMPORTS = {
    "fastapi",
    "requests",
    "sqlalchemy",
    "DrissionPage",
    "akshare",
    "tushare",
    "urllib",
    "utils",
}
FORBIDDEN_WRAPPER_CALL_NAMES = {
    "create_database_client",
    "create_redis_client",
    "DragonTigerHttpSource",
    "RedisPageCache",
}
FORBIDDEN_WRAPPER_ATTRIBUTES = {
    "commit",
    "cursor",
    "execute",
    "mysql_localhost",
    "pipeline",
    "redis_con_localhost",
    "rollback",
}
NON_FORWARDING_NODES = (
    ast.Assign,
    ast.AugAssign,
    ast.AnnAssign,
    ast.For,
    ast.While,
    ast.If,
    ast.Try,
    ast.With,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.Global,
    ast.Nonlocal,
)


def _python_files(root):
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _import_roots(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
            and node.func.attr == "import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            roots.add(node.args[0].value.split(".", 1)[0])
    return roots


def _defined_identifiers(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    yield argument.arg
                if node.args.vararg:
                    yield node.args.vararg.arg
                if node.args.kwarg:
                    yield node.args.kwarg.arg
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            yield node.id
        elif isinstance(node, ast.alias) and node.asname:
            yield node.asname


def _string_literals(tree):
    return "\n".join(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def _wrapper_behavior(tree):
    behavior = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in FORBIDDEN_WRAPPER_CALL_NAMES or name.endswith("Repository"):
                    behavior.add(f"dependency:{name}")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_WRAPPER_ATTRIBUTES:
                    behavior.add(f"persistence:{node.func.attr}")
                if (
                    node.func.attr in {"get", "post", "put", "delete", "request"}
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in {"client", "driver", "http", "page", "requests", "session"}
                ):
                    behavior.add(f"network:{node.func.attr}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body[1:] if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) else node.body
            if len(body) != 1 or not isinstance(body[0], ast.Return) or not isinstance(body[0].value, ast.Call):
                behavior.add(f"non_forwarder:{node.name}")
            if any(isinstance(child, NON_FORWARDING_NODES) for statement in body for child in ast.walk(statement)):
                behavior.add(f"algorithm:{node.name}")
            if node.decorator_list:
                behavior.add(f"route:{node.name}")
    literals = _string_literals(tree)
    if re.search(r"https?://", literals):
        behavior.add("network:url")
    if re.search(r"\b(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b", literals, re.IGNORECASE):
        behavior.add("persistence:sql")
    if re.search(r"/(?:api|v1)/", literals):
        behavior.add("route:path")
    return sorted(behavior)


def test_official_code_has_no_reverse_imports_or_chinese_identifiers():
    violations = []
    for path in _python_files(OFFICIAL_ROOT):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        legacy_roots = _import_roots(tree) & LEGACY_IMPORT_ROOTS
        chinese_identifiers = sorted({name for name in _defined_identifiers(tree) if re.search(r"[\u4e00-\u9fff]", name)})
        if legacy_roots or chinese_identifiers:
            violations.append(
                f"{path.relative_to(ROOT)} imports={sorted(legacy_roots)} identifiers={chinese_identifiers}"
            )
    assert violations == []


def test_active_python_has_no_legacy_storage_references():
    violations = []
    active_roots = [OFFICIAL_ROOT, ROOT / "task", ROOT / "实时监控", ROOT / "游资溢价分析", ROOT / "strategy", ROOT / "utils"]
    for active_root in active_roots:
        for path in _python_files(active_root):
            if path.relative_to(ROOT).as_posix() in LEGACY_STORAGE_MIGRATION_FILES:
                continue
            text = path.read_text(encoding="utf-8")
            literals = _string_literals(ast.parse(text, filename=str(path)))
            tables = sorted(
                table
                for table in LEGACY_TABLES
                if re.search(rf"(?<![0-9A-Za-z_]){re.escape(table)}(?![0-9A-Za-z_])", literals)
                and table not in LEGACY_STORAGE_TABLE_ALLOWLIST.get(path.relative_to(ROOT).as_posix(), set())
            )
            redis_patterns = sorted(pattern.pattern for pattern in LEGACY_REDIS_PATTERNS if pattern.search(literals))
            if tables or redis_patterns:
                violations.append(
                    f"{path.relative_to(ROOT)} tables={tables} redis={redis_patterns}"
                )
    assert violations == []


def test_final_cutover_has_no_runtime_legacy_migration_exception():
    reconciliation_path = ROOT / "src" / "stock_lab" / "jobs" / "jiuyan_reconciliation.py"

    assert not reconciliation_path.exists()
    assert "src/stock_lab/jobs/jiuyan_reconciliation.py" not in LEGACY_STORAGE_TABLE_ALLOWLIST


def test_legacy_implementation_files_are_thin_wrappers():
    violations = []
    for relative_path, line_limit in WRAPPER_LIMITS.items():
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        imported = _import_roots(tree) & FORBIDDEN_WRAPPER_IMPORTS
        behavior = _wrapper_behavior(tree)
        line_count = len(text.splitlines())
        if line_count > line_limit or imported or behavior:
            violations.append(
                f"{relative_path} lines={line_count}/{line_limit} forbidden_imports={sorted(imported)} behavior={behavior}"
            )
    assert violations == []


def test_wrapper_behavior_detector_covers_io_routes_and_algorithms():
    tree = ast.parse("""
@app.get('/api/example')
def route_handler(rows):
    database.cursor()
    redis.pipeline()
    requests.get('https://example.test')
    for row in rows:
        cache[row] = row
""")

    behavior = _wrapper_behavior(tree)

    assert "persistence:cursor" in behavior
    assert "persistence:pipeline" in behavior
    assert "network:get" in behavior
    assert "network:url" in behavior
    assert "route:route_handler" in behavior
    assert "route:path" in behavior
    assert "algorithm:route_handler" in behavior


def test_frontend_has_no_empty_analysis_entry():
    assert not (ROOT / "front" / "src" / "views" / "Analysis.vue").exists()
    assert "Analysis" not in (ROOT / "front" / "src" / "App.vue").read_text(encoding="utf-8")
    assert "数据分析" not in (ROOT / "front" / "src" / "components" / "AppHeader.vue").read_text(encoding="utf-8")


def test_retired_python_utilities_are_absent():
    retired = (
        "utils/api.py",
        "utils/model_util.py",
        "utils/tdx_util.py",
        "utils/driver_chrome.py",
        "tests/test_driver_chrome.py",
    )
    assert [path for path in retired if (ROOT / path).exists()] == []


def test_frontend_template_residue_is_absent():
    retired = (
        "front/src/assets/hero.png",
        "front/src/assets/vite.svg",
        "front/src/assets/vue.svg",
        "front/public/icons.svg",
        "front/README.md",
    )
    assert [path for path in retired if (ROOT / path).exists()] == []
    assert "@tailwindcss/postcss" not in (ROOT / "front" / "package.json").read_text(encoding="utf-8")
    style = (ROOT / "front" / "src" / "style.css").read_text(encoding="utf-8")
    assert ".card" not in style
    assert ".tab-active" not in style
    assert "defineProps" not in (ROOT / "front" / "src" / "views" / "StrategyPickMonitor.vue").read_text(encoding="utf-8")


def test_output_directory_tracks_only_ignore_policy():
    tracked = subprocess.run(
        ["git", "ls-files", "output"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert tracked == ["output/.gitignore"]
    assert (ROOT / "output" / ".gitignore").read_text(encoding="utf-8") == "*\n!.gitignore\n"


def test_dragon_tiger_legacy_wrappers_are_retired():
    legacy_root = ROOT / "游资溢价分析"
    assert not legacy_root.exists()
    assert "游资溢价分析" not in (ROOT / "README.md").read_text(encoding="utf-8")


def test_realtime_monitor_legacy_directory_is_retired():
    assert not (ROOT / "实时监控").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "实时监控/tdx_全局监控.py" not in readme
    assert "实时监控/tdx_竞价监控.py" not in readme
