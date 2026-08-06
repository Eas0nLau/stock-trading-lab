import ast
import re
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
WRAPPER_LIMITS = {
    "task/data_sources.py": 80,
    "task/_5_韭研公社异动.py": 80,
    "实时监控/资金流向.py": 100,
    "实时监控/策略选股.py": 120,
    "实时监控/情绪周期.py": 120,
    "实时监控/热门板块情绪.py": 80,
    "utils/热门板块情绪算法.py": 100,
    "游资溢价分析/采集/龙虎榜数据采集.py": 80,
    "游资溢价分析/采集/营业部数据采集.py": 80,
    "游资溢价分析/采集/游资数据采集.py": 80,
    "游资溢价分析/溢价分析.py": 80,
}
FORBIDDEN_WRAPPER_IMPORTS = {
    "fastapi",
    "requests",
    "sqlalchemy",
    "DrissionPage",
    "akshare",
    "tushare",
}


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
            text = path.read_text(encoding="utf-8")
            literals = _string_literals(ast.parse(text, filename=str(path)))
            tables = sorted(
                table
                for table in LEGACY_TABLES
                if re.search(rf"(?<![0-9A-Za-z_]){re.escape(table)}(?![0-9A-Za-z_])", literals)
            )
            redis_patterns = sorted(pattern.pattern for pattern in LEGACY_REDIS_PATTERNS if pattern.search(literals))
            if tables or redis_patterns:
                violations.append(
                    f"{path.relative_to(ROOT)} tables={tables} redis={redis_patterns}"
                )
    assert violations == []


def test_legacy_implementation_files_are_thin_wrappers():
    violations = []
    for relative_path, line_limit in WRAPPER_LIMITS.items():
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        imported = _import_roots(tree) & FORBIDDEN_WRAPPER_IMPORTS
        line_count = len(text.splitlines())
        if line_count > line_limit or imported:
            violations.append(
                f"{relative_path} lines={line_count}/{line_limit} forbidden_imports={sorted(imported)}"
            )
    assert violations == []
