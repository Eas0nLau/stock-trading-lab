import time
from dataclasses import dataclass
from pathlib import Path

from stock_lab.infrastructure.cache import RedisJobLock
from stock_lab.shared.errors import JobExecutionError

from .daily_update import normalize_trade_date


PREMARKET_LOCK_KEY = "stock_lab:jobs:v1:premarket_summary:lock"
PREMARKET_COMPLETION_PREFIX = "stock_lab:jobs:v1:premarket_summary:completed"
LOCK_TTL_SECONDS = 60 * 60
COMPLETION_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class SecurityMention:
    stock_code: str
    stock_name: str


@dataclass(frozen=True)
class PremarketSummaryDocument:
    text: str
    securities: list[dict]


def premarket_completion_key(trade_date) -> str:
    return f"{PREMARKET_COMPLETION_PREFIX}:{normalize_trade_date(trade_date)}"


def extract_security_mentions(text, securities) -> list[SecurityMention]:
    text = str(text or "")
    if not text.strip():
        raise ValueError("Premarket summary text is empty")

    candidates = []
    for universe_index, item in enumerate(securities):
        mention = _security_mention(item)
        for value in (mention.stock_name, mention.stock_code):
            if not value:
                continue
            start = text.find(value)
            while start >= 0:
                end = start + len(value)
                candidates.append((start, -len(value), universe_index, end, mention))
                start = text.find(value, start + 1)

    mentions = []
    seen_codes = set()
    occupied_spans = []
    for start, _negative_length, _universe_index, end, mention in sorted(candidates):
        if mention.stock_code in seen_codes:
            continue
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied_spans):
            continue
        mentions.append(mention)
        seen_codes.add(mention.stock_code)
        occupied_spans.append((start, end))
    return mentions


def write_premarket_ini(mentions, output_root, trade_date) -> Path:
    mentions = list(mentions)
    if not mentions:
        raise ValueError("Cannot write an empty premarket INI")
    trade_date = normalize_trade_date(trade_date)
    output_directory = Path(output_root) / "韭研公社盘前纪要" / str(trade_date)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{len(mentions)}_盘前纪要提及股票.ini"
    lines = [
        f"{index} = {mention.stock_code},{mention.stock_name}"
        for index, mention in enumerate(mentions, start=1)
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def run_premarket_summary(
    trade_date,
    *,
    source=None,
    state=None,
    writer=None,
    output_root=None,
) -> dict:
    trade_date = normalize_trade_date(trade_date)
    if source is None:
        return {
            "status": "disabled",
            "trade_date": trade_date,
            "reason": "premarket source is not configured",
        }

    if state is None:
        from utils import db

        state = db.redis_con_localhost
    writer = writer or write_premarket_ini
    output_root = output_root or Path(__file__).resolve().parents[3] / "output"
    completion_key = premarket_completion_key(trade_date)
    if state.exists(completion_key):
        return _skipped_result(trade_date)

    lock = RedisJobLock(state, PREMARKET_LOCK_KEY, LOCK_TTL_SECONDS)
    if not lock.acquire():
        raise JobExecutionError("Premarket summary is already running")

    try:
        if state.exists(completion_key):
            return _skipped_result(trade_date)
        document = _collect_document(source, trade_date)
        mentions = extract_security_mentions(document.text, document.securities)
        if not mentions:
            raise JobExecutionError(f"Premarket summary has no security mentions for {trade_date}")
        output_path = writer(mentions, output_root, trade_date)
        state.set(completion_key, str(int(time.time())), ex=COMPLETION_TTL_SECONDS)
        return {
            "status": "success",
            "trade_date": trade_date,
            "mention_count": len(mentions),
            "output_path": str(output_path),
        }
    finally:
        lock.release()


def _security_mention(item) -> SecurityMention:
    if isinstance(item, SecurityMention):
        return item
    try:
        raw_code = item["stock_code"]
        stock_name = str(item["stock_name"] or "").strip()
    except (KeyError, TypeError) as error:
        raise ValueError("Securities must provide stock_code and stock_name") from error
    stock_code = str(raw_code or "").strip().split(".", 1)[0]
    if stock_code.isdigit():
        stock_code = stock_code.zfill(6)
    if len(stock_code) != 6 or not stock_code.isdigit() or not stock_name:
        raise ValueError(f"Invalid security: {item}")
    return SecurityMention(stock_code, stock_name)


def _collect_document(source, trade_date) -> PremarketSummaryDocument:
    result = source(trade_date) if callable(source) else source.collect(trade_date)
    if isinstance(result, PremarketSummaryDocument):
        return result
    if isinstance(result, dict) and "text" in result and "securities" in result:
        return PremarketSummaryDocument(result["text"], result["securities"])
    raise ValueError("Premarket source must return a PremarketSummaryDocument")


def _skipped_result(trade_date: int) -> dict:
    return {
        "status": "skipped",
        "trade_date": trade_date,
        "reason": "already completed",
    }
