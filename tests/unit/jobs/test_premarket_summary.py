from pathlib import Path

import pytest

from stock_lab.jobs.premarket_summary import (
    PREMARKET_LOCK_KEY,
    PremarketSummaryDocument,
    SecurityMention,
    extract_security_mentions,
    premarket_completion_key,
    run_premarket_summary,
    write_premarket_ini,
)
from stock_lab.shared.errors import JobExecutionError


SECURITIES = [
    {"stock_code": "000001", "stock_name": "平安银行"},
    {"stock_code": "300024", "stock_name": "机器人"},
    {"stock_code": "603259", "stock_name": "药明康德"},
]


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    def exists(self, key):
        return key in self.values

    def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.expiries[key] = ex
        return True

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        self.values.pop(key)
        return 1


def test_extraction_preserves_first_body_mention_and_deduplicates_codes():
    text = "机器人率先异动，随后提到药明康德；300024重复出现，最后是000001。"

    assert extract_security_mentions(text, SECURITIES) == [
        SecurityMention("300024", "机器人"),
        SecurityMention("603259", "药明康德"),
        SecurityMention("000001", "平安银行"),
    ]


def test_extraction_normalizes_codes_and_ignores_unrelated_text():
    securities = [
        {"stock_code": 1, "stock_name": "平安银行"},
        {"stock_code": "600000.SH", "stock_name": "浦发银行"},
    ]

    assert extract_security_mentions("关注000001，其他内容无关。", securities) == [
        SecurityMention("000001", "平安银行")
    ]
    assert extract_security_mentions("没有证券名称或代码", securities) == []


def test_extraction_prefers_longest_overlapping_name_at_same_position():
    securities = [
        {"stock_code": "000001", "stock_name": "平安"},
        {"stock_code": "000002", "stock_name": "平安银行"},
    ]

    assert extract_security_mentions("平安银行发布公告", securities) == [
        SecurityMention("000002", "平安银行")
    ]


def test_extraction_rejects_empty_summary_text():
    with pytest.raises(ValueError, match="empty"):
        extract_security_mentions("  ", SECURITIES)


def test_ini_writer_uses_established_path_name_and_numbered_lines(tmp_path):
    mentions = [
        SecurityMention("603259", "药明康德"),
        SecurityMention("000001", "平安银行"),
    ]

    path = write_premarket_ini(mentions, tmp_path, 20260805)

    assert path == tmp_path / "韭研公社盘前纪要" / "20260805" / "2_盘前纪要提及股票.ini"
    assert path.read_text(encoding="utf-8") == "1 = 603259,药明康德\n2 = 000001,平安银行\n"


def test_job_is_explicitly_disabled_without_source_and_does_not_touch_state():
    class FailingState:
        def __getattr__(self, name):
            raise AssertionError(f"state must not be used: {name}")

    assert run_premarket_summary(20260805, source=None, state=FailingState()) == {
        "status": "disabled",
        "trade_date": 20260805,
        "reason": "premarket source is not configured",
    }


def test_job_writes_mentions_then_marks_date_complete(tmp_path):
    redis = FakeRedis()
    document = PremarketSummaryDocument("机器人和药明康德", SECURITIES)

    result = run_premarket_summary(
        "2026-08-05",
        source=lambda trade_date: document,
        state=redis,
        output_root=tmp_path,
    )

    assert result["status"] == "success"
    assert result["trade_date"] == 20260805
    assert result["mention_count"] == 2
    assert Path(result["output_path"]).exists()
    completion_key = premarket_completion_key(20260805)
    assert redis.expiries[completion_key] == 7 * 86400
    assert PREMARKET_LOCK_KEY not in redis.values


def test_job_skips_completed_date_without_calling_source(tmp_path):
    redis = FakeRedis()
    redis.values[premarket_completion_key(20260805)] = "complete"

    def source(_trade_date):
        raise AssertionError("completed job must not call source")

    result = run_premarket_summary(20260805, source=source, state=redis, output_root=tmp_path)

    assert result == {"status": "skipped", "trade_date": 20260805, "reason": "already completed"}


def test_job_rejects_concurrent_run():
    redis = FakeRedis()
    redis.values[PREMARKET_LOCK_KEY] = "another-owner"

    with pytest.raises(JobExecutionError, match="already running"):
        run_premarket_summary(20260805, source=lambda _date: None, state=redis)

    assert redis.values[PREMARKET_LOCK_KEY] == "another-owner"


@pytest.mark.parametrize("failure_stage", ["source", "writer"])
def test_job_failure_releases_lock_without_completion(tmp_path, failure_stage):
    redis = FakeRedis()

    def source(_trade_date):
        if failure_stage == "source":
            raise RuntimeError("source failed")
        return PremarketSummaryDocument("机器人", SECURITIES)

    def writer(mentions, output_root, trade_date):
        assert mentions == [SecurityMention("300024", "机器人")]
        if failure_stage == "writer":
            raise RuntimeError("writer failed")
        return write_premarket_ini(mentions, output_root, trade_date)

    with pytest.raises(RuntimeError, match="failed"):
        run_premarket_summary(
            20260805,
            source=source,
            state=redis,
            writer=writer,
            output_root=tmp_path,
        )

    assert PREMARKET_LOCK_KEY not in redis.values
    assert premarket_completion_key(20260805) not in redis.values


def test_job_rejects_summary_without_security_mentions(tmp_path):
    redis = FakeRedis()
    document = PremarketSummaryDocument("没有匹配项", SECURITIES)

    with pytest.raises(JobExecutionError, match="no security mentions"):
        run_premarket_summary(20260805, source=lambda _date: document, state=redis, output_root=tmp_path)

    assert PREMARKET_LOCK_KEY not in redis.values
