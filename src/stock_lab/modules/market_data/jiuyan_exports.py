from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from stock_lab.shared.errors import DataValidationError


SPECIAL_BOARDS = {"公告": 0, "其他": 1, "新股": 2}
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
STREAK_PATTERN = re.compile(r"^(\d+)天(\d+)板$")
PARENTHETICAL_PATTERN = re.compile(r"[（(][^）)]*[）)]")


def _default_repository():
    from .collectors import create_default_repository

    return create_default_repository()


def _complete_rows(repository, trade_date):
    manifest = repository.jiuyan_collection_day(trade_date)
    if not manifest or manifest.get("status") != "complete":
        raise DataValidationError(f"Jiuyan date {trade_date} is not complete")
    rows = repository.jiuyan_actions_for_date(trade_date)
    if int(manifest.get("accepted_stock_count", -1)) != len(rows):
        raise DataValidationError(f"Jiuyan date {trade_date} has an incomplete row count")
    return rows


def _board_sort(item):
    board_name, rows = item
    if board_name in SPECIAL_BOARDS:
        return (1, SPECIAL_BOARDS[board_name], board_name)
    reported_count = max(int(row.get("board_stock_count") or 0) for row in rows)
    return (0, -reported_count, board_name)


def _stock_sort(row):
    match = STREAK_PATTERN.fullmatch(str(row.get("board_streak") or "").strip())
    days = int(match.group(1)) if match else 0
    boards = int(match.group(2)) if match else 0
    consecutive = bool(match and days == boards)
    return (
        not consecutive,
        -boards,
        str(row.get("limit_up_at") or ""),
        str(row.get("stock_code") or ""),
    )


def _safe_name(value):
    return INVALID_FILENAME_CHARS.sub("_", str(value)).strip() or "unnamed"


def _unique_board_filename(board_name, stock_count, used_names):
    stem = f"{stock_count}_{_safe_name(board_name)}"
    name = f"{stem}.ini"
    if name in used_names:
        digest = hashlib.sha256(str(board_name).encode("utf-8")).hexdigest()[:8]
        name = f"{stem}_{digest}.ini"
    suffix = 2
    while name in used_names:
        name = f"{stem}_{suffix}.ini"
        suffix += 1
    used_names.add(name)
    return name


def _write_ini(path, rows):
    content = "\n".join(
        f"{index} = {row['stock_code']},{row.get('stock_name') or ''}"
        for index, row in enumerate(rows, start=1)
    )
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def export_jiuyan_actions(trade_date, repository=None, output_root=Path("output")):
    trade_date = int(trade_date)
    repository = repository or _default_repository()
    rows = _complete_rows(repository, trade_date)
    grouped = defaultdict(list)
    for row in rows:
        board_name = str(row.get("board_name") or "").strip()
        if not board_name or board_name == "ST板块":
            continue
        grouped[board_name].append(dict(row))

    output_parent = Path(output_root) / "韭研公社异动板块"
    output_parent.mkdir(parents=True, exist_ok=True)
    target_directory = output_parent / str(trade_date)
    temporary_directory = Path(
        tempfile.mkdtemp(prefix=f".{trade_date}-", dir=output_parent)
    )
    board_outputs = []
    all_rows = []
    assigned_codes = set()
    try:
        for board_name, board_rows in sorted(grouped.items(), key=_board_sort):
            unique_rows = []
            for row in sorted(board_rows, key=_stock_sort):
                stock_code = str(row.get("stock_code") or "").zfill(6)
                if not stock_code or stock_code in assigned_codes:
                    continue
                row["stock_code"] = stock_code
                assigned_codes.add(stock_code)
                unique_rows.append(row)
            if not unique_rows:
                continue
            board_outputs.append((board_name, unique_rows))
            all_rows.extend(unique_rows)

        all_name = f"{len(all_rows)}_全部.ini"
        used_names = {all_name}
        generated_names = []
        for board_name, unique_rows in board_outputs:
            name = _unique_board_filename(
                board_name, len(unique_rows), used_names
            )
            _write_ini(temporary_directory / name, unique_rows)
            generated_names.append(name)
        _write_ini(temporary_directory / all_name, all_rows)
        generated_names.append(all_name)

        if target_directory.exists():
            for existing in target_directory.iterdir():
                if existing.suffix.lower() == ".ini":
                    continue
                destination = temporary_directory / existing.name
                if existing.is_dir():
                    shutil.copytree(existing, destination)
                else:
                    shutil.copy2(existing, destination)
        _promote_directory(temporary_directory, target_directory)
        return [target_directory / name for name in generated_names]
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def _promote_directory(temporary_directory, target_directory):
    backup_directory = target_directory.with_name(
        f".{target_directory.name}-backup"
    )
    if backup_directory.exists():
        shutil.rmtree(backup_directory)
    if target_directory.exists():
        target_directory.replace(backup_directory)
    try:
        temporary_directory.replace(target_directory)
    except Exception:
        if backup_directory.exists() and not target_directory.exists():
            backup_directory.replace(target_directory)
        raise
    else:
        shutil.rmtree(backup_directory, ignore_errors=True)


def front_rank_summary(trade_date=None, repository=None):
    repository = repository or _default_repository()
    if trade_date is None:
        trade_date = repository.latest_complete_jiuyan_date()
    if trade_date is None:
        raise DataValidationError("No complete Jiuyan date is available")
    trade_date = int(trade_date)
    rows = _complete_rows(repository, trade_date)
    board_codes = defaultdict(set)
    reason_codes = defaultdict(set)
    for row in rows:
        board_name = str(row.get("board_name") or "").strip()
        if not board_name or board_name == "ST板块":
            continue
        stock_code = str(row.get("stock_code") or "").zfill(6)
        board_codes[board_name].add(stock_code)
        reason_text = PARENTHETICAL_PATTERN.sub(
            "", str(row.get("limit_up_reason") or "")
        )
        for reason in reason_text.split("+"):
            reason = reason.strip()
            if reason:
                reason_codes[reason].add(stock_code)
    boards = [
        {"board_name": name, "stock_count": len(codes)}
        for name, codes in board_codes.items()
    ]
    reasons = [
        {"reason": reason, "stock_count": len(codes)}
        for reason, codes in reason_codes.items()
    ]
    boards.sort(key=lambda row: (-row["stock_count"], row["board_name"]))
    reasons.sort(key=lambda row: (-row["stock_count"], row["reason"]))
    return {"trade_date": trade_date, "boards": boards, "reasons": reasons}
