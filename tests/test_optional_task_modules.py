import importlib
import sys


def test_compatibility_task_modules_import_without_ambient_io(monkeypatch):
    class FailingUtils:
        def __getattr__(self, name):
            raise AssertionError(f"task import attempted ambient I/O dependency: {name}")

    monkeypatch.setitem(sys.modules, "utils", FailingUtils())
    for name in ("task.每日更新", "task.盘前纪要", "task.emotion_analysis"):
        sys.modules.pop(name, None)

    daily = importlib.import_module("task.每日更新")
    premarket = importlib.import_module("task.盘前纪要")
    emotion = importlib.import_module("task.emotion_analysis")

    assert callable(daily.tasks)
    assert callable(premarket.韭研公社盘前纪要采集)
    assert callable(emotion.落库指数周期)


def test_premarket_wrapper_reports_disabled_without_source():
    premarket = importlib.import_module("task.盘前纪要")

    assert premarket.韭研公社盘前纪要采集(20260805, source=None)["status"] == "disabled"
