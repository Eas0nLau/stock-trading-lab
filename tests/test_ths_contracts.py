from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_THS_TABLES = (
    "t_同花顺板块列表",
    "t_同花顺板块成分股",
    "t_同花顺股票板块概念对应关系",
)
SOURCE_SUFFIXES = {".js", ".py", ".sql", ".ts", ".vue"}
EXCLUDED_PATH_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "data",
    "db",
    "dist",
    "docs",
    "init",
    "node_modules",
    "output",
    "tests",
}


def test_active_runtime_has_no_legacy_ths_table_references():
    references = []
    for path in ROOT.rglob("*"):
        relative_path = path.relative_to(ROOT)
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in EXCLUDED_PATH_PARTS for part in relative_path.parts):
            continue
        content = path.read_text(encoding="utf-8")
        for table in LEGACY_THS_TABLES:
            if table in content:
                references.append(f"{relative_path}: {table}")

    assert references == []
