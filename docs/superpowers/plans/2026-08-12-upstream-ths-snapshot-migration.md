# Upstream THS Snapshot Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded, complete THS concept/industry snapshot collector that validates one coherent source snapshot and atomically replaces `ths_boards`, `ths_board_constituents`, and `ths_stock_relations` through canonical English modules and a thin `_6` compatibility CLI.

**Architecture:** A lazy `ThsHttpSource` owns Cookie generation, requests, retries, and global pacing. Pure THS parsers and snapshot functions normalize source data, collect every board with bounded concurrency, prove completeness, and build deterministic stock relations in memory. A separate `ThsSnapshotWriter` replaces all three existing tables in one transaction; the existing `ThsRepository` remains read-only.

**Tech Stack:** Python 3.12, requests, BeautifulSoup/lxml, mini-racer, AkShare dataset files, concurrent futures, SQLAlchemy 2, MySQL 8, pytest.

## Global Constraints

- Use upstream commit `8e1a3f8348bd9b10af9174b55fd94b0dca9494fb` only as the behavior reference; do not copy its Chinese SQL, CSV cache, 60 retries, swallowed failures, or partial completeness checks.
- Keep `ThsRepository` read-only and engine-free. All runtime writes belong to `ThsSnapshotWriter`.
- Do not add a schema migration; the three canonical tables already exist in `001_create_english_schema.sql` and `init/stock_trading_lab_v2.sql`.
- Do not write Redis, `task_runs`, CSV files, or daily-update completion state in this subproject.
- Do not add THS to the close-of-day critical chain.
- Default source parameters are four workers, one global request every 0.5 seconds, 20-second timeout, and three attempts with waits of 1 and 2 seconds.
- `401` and `403` refresh the THS `v` Cookie before retry.
- Concept boards require a valid six-digit `clid`; missing `clid` is a snapshot failure.
- Accept blockrank only when unique valid rows equal `subcodeCount`; otherwise use strict HTML pagination fallback.
- Allow a zero-constituent board only when blockrank declares zero or page one explicitly contains `暂无成份股数据`.
- Fail rather than truncate when declared pagination exceeds 300 pages.
- Persist nothing unless every board is complete or source-proven empty.
- Every task module remains an import-safe one-return forwarding wrapper with no direct source or SQL behavior.
- All source tests use fixed fixtures and perform no network requests.
- Continue ignoring only the user-approved `output/.gitignore` contract failure.

---

## File Structure

### New runtime files

- `src/stock_lab/modules/ths/contracts.py`: immutable source/snapshot result types.
- `src/stock_lab/modules/ths/parsing.py`: pure board, `clid`, JSONP, page-count, and constituent parsers.
- `src/stock_lab/infrastructure/market_data/ths.py`: lazy Cookie factory, global pacing, bounded HTTP retrieval, and URL helpers.
- `src/stock_lab/modules/ths/collection.py`: board discovery, source fallback, concurrent board collection, validation, and relation aggregation.
- `src/stock_lab/modules/ths/writer.py`: one-transaction canonical snapshot replacement.
- `src/stock_lab/jobs/ths_snapshot.py`: validation, default dependency composition, structured job result, and CLI implementation.
- `task/_6_同花顺行业和概念.py`: thin compatibility forwards.

### Modified runtime files

- `src/stock_lab/infrastructure/market_data/__init__.py`: export `ThsHttpSource` without constructing it.
- `src/stock_lab/modules/ths/__init__.py`: export canonical contracts, collection entry point, and writer while preserving existing model/repository exports.

### New tests

- `tests/unit/modules/ths/test_ths_parsing.py`
- `tests/unit/infrastructure/market_data/test_ths_source.py`
- `tests/unit/modules/ths/test_ths_collection.py`
- `tests/unit/modules/ths/test_ths_writer.py`
- `tests/unit/jobs/test_ths_snapshot.py`
- `tests/unit/compatibility/test_ths_task.py`

### Modified tests and docs

- `tests/unit/modules/ths/test_ths_repository.py`: retain the no-write repository contract.
- `tests/test_cutover_contracts.py`: add `_6` wrapper limit and import-safety checks.
- `tests/test_ths_contracts.py`: continue rejecting legacy Chinese THS table names from active runtime code.
- `README.md`
- `docs/architecture.md`
- `docs/migration.md`
- `docs/database-migrations.md`
- `db/migrations/README.md`
- `docs/historical-data-source-matrix.md`
- `docs/historical-data-backfill-runbook.md`

---

### Task 1: Immutable THS Contracts And Pure Parsers

**Files:**
- Create: `src/stock_lab/modules/ths/contracts.py`
- Create: `src/stock_lab/modules/ths/parsing.py`
- Modify: `src/stock_lab/modules/ths/__init__.py`
- Create: `tests/unit/modules/ths/test_ths_parsing.py`

**Interfaces:**
- Consumes: fixed HTML/JSONP strings and raw source values.
- Produces:
  - `ThsBoardSeed(board_code, board_type, board_name, page_code, detail_path)`
  - `ThsConstituent(board_code, stock_code, board_type, board_name, page_code, stock_name)`
  - `ThsBlockrankResult(declared_count, constituents)`
  - `ThsPageResult(constituents, explicitly_empty)`
  - `ThsBoardCollection(board, constituents, explicitly_empty, source)`
  - `ThsBoardFailure(board, error)`
  - `ThsSnapshot(boards, constituents, stock_relations, empty_board_count)`
  - `ThsCollectionResult(snapshot, failed_boards, errors, observed_board_count, observed_constituent_count)`
  - `normalize_ths_code(value) -> str`
  - `parse_board_directory(html, board_type, detail_path) -> tuple[ThsBoardSeed, ...]`
  - `parse_concept_import_code(html) -> str`
  - `parse_blockrank_jsonp(text, board) -> ThsBlockrankResult`
  - `parse_page_count(html, max_pages=300) -> int`
  - `parse_constituent_page(html, board) -> ThsPageResult`

- [ ] **Step 1: Add failing normalization and directory tests**

Create tests that prove canonical English values and deterministic deduplication:

```python
def test_parse_board_directory_normalizes_and_deduplicates_links():
    html = """
    <div class="cate_inner">
      <a href="/gn/detail/code/301558/">Robotics</a>
      <a href="/gn/detail/code/301558/">Robotics</a>
      <a href="/gn/detail/code/9/">AI</a>
    </div>
    """

    rows = parse_board_directory(html, "concept", "gn")

    assert [(row.board_type, row.board_name, row.page_code) for row in rows] == [
        ("concept", "AI", "000009"),
        ("concept", "Robotics", "301558"),
    ]
    assert all(row.board_code == "" for row in rows)
```

Add parameterized `normalize_ths_code` tests for `1`, `000001`, integer-like
strings, invalid alpha values, empty values, and values longer than six digits.

- [ ] **Step 2: Add failing `clid`, JSONP, and pagination tests**

Use exact fixture fragments and assertions:

```python
def test_parse_concept_import_code_requires_valid_clid():
    assert parse_concept_import_code('<input id="clid" value="885001">') == "885001"
    with pytest.raises(DataValidationError, match="clid"):
        parse_concept_import_code("<html></html>")


def test_parse_blockrank_jsonp_preserves_declared_count_and_unique_rows(board):
    payload = 'callback({"block":{"subcodeCount":"2"},"items":[{"5":"1","55":"One"},{"5":"000001","55":"One"},{"5":"600000","55":"Two"}]})'

    result = parse_blockrank_jsonp(payload, board)

    assert result.declared_count == 2
    assert [row.stock_code for row in result.constituents] == ["000001", "600000"]


def test_parse_page_count_fails_above_safety_limit():
    with pytest.raises(DataValidationError, match="300"):
        parse_page_count('<span class="page_info">1 / 301</span>')
```

Also test malformed JSONP, negative/non-numeric `subcodeCount`, missing `items`, a
missing page indicator returning one, and exact page count `300` succeeding.

- [ ] **Step 3: Add failing constituent-page tests**

Cover a normal table, duplicate stock codes, placeholder empty proof, generic
missing table, blank names, and malformed codes:

```python
def test_parse_constituent_page_distinguishes_explicit_empty_from_parse_failure(board):
    empty = parse_constituent_page(
        "<table><tr><td>暂无成份股数据</td></tr></table>", board
    )
    assert empty.explicitly_empty is True
    assert empty.constituents == ()

    with pytest.raises(DataValidationError, match="constituent table"):
        parse_constituent_page("<html></html>", board)
```

- [ ] **Step 4: Run parser tests and verify failure**

Run:

```powershell
uv run --frozen pytest -q tests/unit/modules/ths/test_ths_parsing.py --import-mode=importlib
```

Expected: collection FAIL because the contracts and parsing module do not exist.

- [ ] **Step 5: Implement immutable contracts**

Create frozen dataclasses using tuple fields, not mutable lists:

```python
@dataclass(frozen=True)
class ThsBoardSeed:
    board_code: str
    board_type: str
    board_name: str
    page_code: str
    detail_path: str


@dataclass(frozen=True)
class ThsConstituent:
    board_code: str
    stock_code: str
    board_type: str
    board_name: str
    page_code: str
    stock_name: str


@dataclass(frozen=True)
class ThsBlockrankResult:
    declared_count: int
    constituents: tuple[ThsConstituent, ...]


@dataclass(frozen=True)
class ThsPageResult:
    constituents: tuple[ThsConstituent, ...]
    explicitly_empty: bool = False
```

Define `ThsBoardCollection.source` as `"blockrank"`, `"html"`, or
`"explicit_empty"`. Define `ThsBoardFailure.error` as a bounded string. Define
`ThsSnapshot.stock_relations` as a tuple of canonical dictionaries because the
relation fields are persistence projections rather than source entities. Define
`ThsCollectionResult.snapshot` as `ThsSnapshot | None`, and make its failure and
error fields tuples so Task 4 can return an immutable coordination result without
changing the Task 1 contract.

- [ ] **Step 6: Implement pure parsers**

Use BeautifulSoup with `features="lxml"` and standard `json`, `re`, and HTML table
traversal. Do not use `pandas.read_html`; the parser should select the table whose
headers include `代码` and `名称`, then read matching cells explicitly.

Ensure parser ordering is deterministic:

```python
rows_by_key[(board_type, page_code, board_name)] = row
return tuple(rows_by_key[key] for key in sorted(rows_by_key))
```

`parse_blockrank_jsonp` extracts the object between the first `{` and the final
`}` and requires the decoded payload to be a dictionary. It drops duplicate codes
only after validating each retained code/name pair.

- [ ] **Step 7: Run parser tests**

Run the command from Step 4.

Expected: PASS.

- [ ] **Step 8: Commit parser contracts**

```powershell
git add -- "src/stock_lab/modules/ths/contracts.py" "src/stock_lab/modules/ths/parsing.py" "src/stock_lab/modules/ths/__init__.py" "tests/unit/modules/ths/test_ths_parsing.py"
git commit -m "feat: parse canonical THS source data"
```

---

### Task 2: Lazy THS HTTP Source With Global Pacing

**Files:**
- Create: `src/stock_lab/infrastructure/market_data/ths.py`
- Modify: `src/stock_lab/infrastructure/market_data/__init__.py`
- Create: `tests/unit/infrastructure/market_data/test_ths_source.py`

**Interfaces:**
- Consumes: injected requests session, `RequestRateLimiter`, Cookie factory, clock/sleep, and source URLs.
- Produces:
  - `create_ths_cookie() -> str`
  - `ThsHttpSource.get_text(url, *, referer=None, host=None) -> str`
  - `ThsHttpSource.board_directory_html(board_type) -> str`
  - `ThsHttpSource.concept_detail_html(page_code) -> str`
  - `ThsHttpSource.blockrank_text(board_code, rank_code) -> str`
  - `ThsHttpSource.constituent_page_html(board, page) -> str`

- [ ] **Step 1: Add failing lazy-import and Cookie tests**

Assert importing the module does not import `akshare.datasets` or
`py_mini_racer`, then inject fake modules only when `create_ths_cookie()` runs:

```python
def test_cookie_factory_loads_js_runtime_only_when_called(monkeypatch, tmp_path):
    observed = []
    js_path = tmp_path / "ths.js"
    js_path.write_text("function v(){ return 'token'; }", encoding="utf-8")
    monkeypatch.setitem(
        sys.modules,
        "akshare.datasets",
        SimpleNamespace(get_ths_js=lambda _name: str(js_path)),
    )
    monkeypatch.setitem(
        sys.modules,
        "py_mini_racer",
        SimpleNamespace(MiniRacer=lambda: FakeMiniRacer(observed)),
    )

    assert create_ths_cookie() == "v=token"
    assert observed == ["eval", ("call", "v")]
```

Use the installed `mini-racer==0.12.4` distribution but import its compatible
`py_mini_racer` module lazily. Do not change `pyproject.toml` or `uv.lock`.

- [ ] **Step 2: Add failing pacing/retry/header tests**

Create one fake session shared by multiple source calls and assert:

- `limiter.wait()` is called before every attempt;
- attempts are exactly three;
- sleep receives `[1, 2]` and never runs after final failure;
- `401`/`403` invokes the Cookie factory again;
- normal requests use the exact upstream User-Agent and a fresh `Cookie`;
- blockrank requests set `Host: d.10jqka.com.cn`;
- referer defaults to `https://q.10jqka.com.cn/` and can be overridden;
- final failures raise `InfrastructureError` with bounded source context.

```python
def test_get_text_refreshes_cookie_after_403():
    session = FakeSession([FakeResponse(403), FakeResponse(200, text="ok")])
    cookies = iter(["v=first", "v=second"])
    source = ThsHttpSource(
        session=session,
        limiter=RecordingLimiter(),
        cookie_factory=lambda: next(cookies),
        sleep=lambda _seconds: None,
    )

    assert source.get_text("https://example.test") == "ok"
    assert session.calls[0]["headers"]["Cookie"] == "v=first"
    assert session.calls[1]["headers"]["Cookie"] == "v=second"
```

- [ ] **Step 3: Add failing URL contract tests**

Assert the exact source routes:

```python
assert source.board_directory_url("concept") == "https://q.10jqka.com.cn/gn/"
assert source.board_directory_url("industry") == "https://q.10jqka.com.cn/thshy/"
assert source.concept_detail_url("301558") == "https://q.10jqka.com.cn/gn/detail/code/301558/"
assert source.blockrank_url("885001", "d15") == "https://d.10jqka.com.cn/v2/blockrank/885001/8/d15.js"
assert source.constituent_page_url(board, 2).endswith(
    "/detail/field/199112/order/desc/page/2/ajax/1/code/301558/"
)
```

- [ ] **Step 4: Run source tests and verify failure**

```powershell
uv run --frozen pytest -q tests/unit/infrastructure/market_data/test_ths_source.py --import-mode=importlib
```

Expected: collection FAIL because `ThsHttpSource` does not exist.

- [ ] **Step 5: Implement the lazy Cookie factory and source**

Implement `create_ths_cookie` with local imports:

```python
def create_ths_cookie():
    from akshare.datasets import get_ths_js
    from py_mini_racer import MiniRacer

    context = MiniRacer()
    with open(get_ths_js("ths.js"), encoding="utf-8") as source_file:
        context.eval(source_file.read())
    return f"v={context.call('v')}"
```

Construct one requests `Session`, one `RequestRateLimiter(0.5)`, and one Cookie
value per source instance. Copy headers per request so concurrent workers never
mutate shared dictionaries. Guard Cookie refresh with a lock.

The request loop must be exactly:

```python
for attempt in range(1, 4):
    limiter.wait()
    try:
        response = session.get(url, headers=headers, timeout=20)
        if response.status_code in {401, 403} and attempt < 3:
            refresh_cookie()
            sleep(attempt)
            continue
        response.raise_for_status()
        return response.text
    except requests.RequestException as error:
        last_error = error
        if attempt < 3:
            sleep(attempt)
raise InfrastructureError(...) from last_error
```

- [ ] **Step 6: Export the source lazily and run tests**

Add `ThsHttpSource` to `stock_lab.infrastructure.market_data.__all__`. Importing
the class is allowed; instantiating it must remain explicit.

Run the command from Step 4.

Expected: PASS.

- [ ] **Step 7: Commit source reliability**

```powershell
git add -- "src/stock_lab/infrastructure/market_data/ths.py" "src/stock_lab/infrastructure/market_data/__init__.py" "tests/unit/infrastructure/market_data/test_ths_source.py"
git commit -m "feat: add bounded THS HTTP source"
```

---

### Task 3: Board Discovery And Strict Constituent Source Fallback

**Files:**
- Create: `src/stock_lab/modules/ths/collection.py`
- Create: `tests/unit/modules/ths/test_ths_collection.py`

**Interfaces:**
- Consumes: Task 1 contracts/parsers and Task 2 `ThsHttpSource` methods.
- Produces:
  - `collect_board_seeds(source) -> tuple[ThsBoardSeed, ...]`
  - `collect_board(source, board, *, max_pages=300) -> ThsBoardCollection`
  - internal `_collect_blockrank(source, board) -> ThsBoardCollection | None`
  - internal `_collect_html_pages(source, board, max_pages) -> ThsBoardCollection`

- [ ] **Step 1: Add failing board discovery tests**

Use a fake source returning separate concept/industry HTML and concept detail
pages. Assert both types are required, all concepts receive strict `clid`, industry
codes equal page codes, and final ordering is `(board_type, board_code)`.

```python
def test_collect_board_seeds_resolves_concept_clid_and_requires_both_types():
    source = FakeSource(
        concept_html=CONCEPT_DIRECTORY,
        industry_html=INDUSTRY_DIRECTORY,
        concept_details={"301558": '<input id="clid" value="885001">'},
    )

    boards = collect_board_seeds(source)

    assert [(row.board_type, row.board_code) for row in boards] == [
        ("concept", "885001"),
        ("industry", "881001"),
    ]
```

Add failures for missing concept directory, missing industry directory, missing
`clid`, duplicate board codes across types, and duplicate `(type, page_code)`.

- [ ] **Step 2: Add failing exact blockrank acceptance tests**

Cover:

- declared zero returns `explicit_empty` without HTML requests;
- count `<3000` requests `d{ceil(count/15)*15}`;
- count `>=3000` requests `a3000` and `d3000`;
- exact unique count returns source `blockrank`;
- mismatched count falls back to HTML;
- non-`88` code skips blockrank.

```python
def test_blockrank_count_mismatch_uses_html_fallback(board):
    source = FakeSource(
        blockrank={"d15": blockrank_payload(2, [("000001", "One")])},
        pages={1: HTML_ONE, 2: HTML_TWO},
    )

    result = collect_board(source, board)

    assert result.source == "html"
    assert [row.stock_code for row in result.constituents] == ["000001", "600000"]
```

- [ ] **Step 3: Add failing strict HTML pagination tests**

Assert every declared page is requested. Page one explicit-empty succeeds; generic
empty page one fails; empty later page fails; a page adding no new code fails;
duplicate codes across pages are deduplicated only when the page also contributes
at least one new code; declared page 301 fails before requesting page two.

- [ ] **Step 4: Run collection-source tests and verify failure**

```powershell
uv run --frozen pytest -q tests/unit/modules/ths/test_ths_collection.py -k "board_seeds or blockrank or pagination" --import-mode=importlib
```

Expected: FAIL because `collection.py` does not exist.

- [ ] **Step 5: Implement board discovery**

Fetch directories sequentially through the shared source. Resolve concept `clid`
sequentially through the same global limiter. Reject empty types and duplicate
keys before any constituent worker starts.

- [ ] **Step 6: Implement blockrank and HTML collection**

Use the formulas from the design:

```python
if declared_count < 3000:
    rank_codes = [f"d{math.ceil(declared_count / 15) * 15}"]
else:
    rank_codes = ["a3000", "d3000"]
```

Do not catch `DataValidationError` from HTML fallback. Catch blockrank decode/count
errors only to select HTML fallback; preserve the blockrank reason as exception
context if HTML also fails.

- [ ] **Step 7: Run collection-source tests**

Run the command from Step 4 without `-k`.

Expected: current tests PASS.

- [ ] **Step 8: Commit source fallback**

```powershell
git add -- "src/stock_lab/modules/ths/collection.py" "tests/unit/modules/ths/test_ths_collection.py"
git commit -m "feat: collect complete THS board constituents"
```

---

### Task 4: Concurrent Snapshot Coordination And Stock Relations

**Files:**
- Modify: `src/stock_lab/modules/ths/collection.py`
- Modify: `src/stock_lab/modules/ths/__init__.py`
- Modify: `tests/unit/modules/ths/test_ths_collection.py`

**Interfaces:**
- Consumes: `collect_board_seeds`, `collect_board`, and Task 1 contracts.
- Produces:
  - `build_stock_relations(constituents) -> tuple[dict[str, object], ...]`
  - `validate_ths_snapshot(boards, board_results, stock_relations) -> None`
  - `collect_ths_snapshot(source, *, max_workers=4, max_pages=300) -> ThsCollectionResult`
  - `ThsCollectionResult(snapshot, failed_boards, errors, observed_board_count, observed_constituent_count)`

- [ ] **Step 1: Add failing stock-relation golden tests**

Use repeated stock names and memberships to assert deterministic selection and
parallel lists:

```python
def test_build_stock_relations_is_deterministic():
    rows = (
        constituent("885002", "concept", "AI", "000001", "N Bank"),
        constituent("885001", "concept", "Robotics", "000001", "Ping An Bank"),
        constituent("881100", "industry", "Banking", "000001", "Ping An Bank"),
    )

    assert build_stock_relations(rows) == ({
        "stock_code": "000001",
        "stock_name": "Ping An Bank",
        "industry_names": "Banking",
        "industry_codes": "881100",
        "concept_names": "Robotics;AI",
        "concept_codes": "885001;885002",
    },)
```

Add tie tests for non-`C`/`N`, longer names, lexical order, and `None` for a missing
membership type.

- [ ] **Step 2: Add failing snapshot validation tests**

Parameterize:

- missing board result;
- failed board result;
- constituent references unknown board;
- constituent board metadata mismatch;
- duplicate `(board_code, stock_code)`;
- relation stock set differs from constituent stock set;
- relation names/codes have different semicolon counts;
- explicit empty board with no constituent rows succeeds.

- [ ] **Step 3: Add failing concurrency and failure-order tests**

Inject a fake executor or real thread-safe fake source. Assert `max_workers=4` is
passed, all boards are submitted, successful workers are retained, errors are
truncated to 1000 characters, and failures sort by `(board_type, board_code)` rather
than completion order.

```python
def test_collect_snapshot_reports_failures_without_building_snapshot():
    result = collect_ths_snapshot(FakeSource(fail_codes={"885002", "881001"}))

    assert result.snapshot is None
    assert [failure.board_code for failure in result.failed_boards] == [
        "885002", "881001"
    ]
```

Use expected ordering consistent with the canonical string tuple ordering encoded
in the fixture; do not depend on `as_completed` order.

- [ ] **Step 4: Run snapshot tests and verify failure**

```powershell
uv run --frozen pytest -q tests/unit/modules/ths/test_ths_collection.py -k "relations or snapshot or failures" --import-mode=importlib
```

Expected: FAIL because aggregation and coordination functions are absent.

- [ ] **Step 5: Implement deterministic relation aggregation**

Group by normalized stock code. Select the name with this exact key after sorting
candidate counts descending:

```python
name_key = (
    -occurrence_count,
    name.upper().startswith(("C", "N")),
    -len(name),
    name,
)
```

For each membership type, deduplicate by board code, sort `(board_code,
board_name)`, then join names and codes independently with `;`.

- [ ] **Step 6: Implement snapshot validation and coordinator**

Validate `max_workers` in the inclusive range 1-8 before creating the executor.
Collect all submitted futures, converting exceptions to `ThsBoardFailure` without
discarding successful results. If failures remain, return a failed
`ThsCollectionResult` and do not create `ThsSnapshot`.

If complete, flatten constituents in `(board_code, stock_code)` order, build
relations, validate all invariants, count explicit empty boards, and return one
immutable snapshot.

- [ ] **Step 7: Run all collection tests**

```powershell
uv run --frozen pytest -q tests/unit/modules/ths/test_ths_collection.py --import-mode=importlib
```

Expected: PASS.

- [ ] **Step 8: Commit complete snapshot coordination**

```powershell
git add -- "src/stock_lab/modules/ths/collection.py" "src/stock_lab/modules/ths/__init__.py" "tests/unit/modules/ths/test_ths_collection.py"
git commit -m "feat: validate complete THS snapshots"
```

---

### Task 5: Atomic Three-Table Snapshot Writer

**Files:**
- Create: `src/stock_lab/modules/ths/writer.py`
- Modify: `src/stock_lab/modules/ths/__init__.py`
- Create: `tests/unit/modules/ths/test_ths_writer.py`
- Modify: `tests/unit/modules/ths/test_ths_repository.py`

**Interfaces:**
- Consumes: validated canonical board, constituent, and stock-relation dictionaries containing one `collected_date` and `updated_at` value.
- Produces: `ThsSnapshotWriter(engine).replace_snapshot(boards, constituents, stock_relations) -> {"boards": int, "constituents": int, "stock_relations": int}`.

- [ ] **Step 1: Add failing pre-transaction validation tests**

Create a fake engine recording `begin()` calls. Assert these failures happen before
opening a transaction:

- empty boards;
- invalid `collected_date`;
- different `collected_date` values across tables;
- duplicate board codes;
- duplicate constituent keys;
- unknown constituent board;
- stock relation set differs from constituent stocks;
- missing required English column;
- inconsistent `updated_at` timestamps.

```python
def test_writer_rejects_unknown_constituent_board_before_transaction():
    writer, engine = fake_writer()

    with pytest.raises(DataValidationError, match="unknown board"):
        writer.replace_snapshot(BOARDS, [constituent(board_code="999999")], RELATIONS)

    assert engine.begin_count == 0
```

- [ ] **Step 2: Add failing transaction-order and count tests**

Assert one transaction emits:

1. delete constituents;
2. delete stock relations;
3. delete boards;
4. insert boards;
5. insert constituents when nonempty;
6. insert stock relations when nonempty;
7. count boards;
8. count constituents;
9. count stock relations.

Add explicit-empty coverage where boards are nonempty but constituent/relation rows
are empty. Assert persisted count mismatch raises `DataValidationError`, allowing
the transaction context to roll back. Assert an insert exception prevents later
statements.

- [ ] **Step 3: Run writer tests and verify failure**

```powershell
uv run --frozen pytest -q tests/unit/modules/ths/test_ths_writer.py tests/unit/modules/ths/test_ths_repository.py --import-mode=importlib
```

Expected: FAIL because `ThsSnapshotWriter` does not exist.

- [ ] **Step 4: Implement writer validation**

Use the existing frozen model field sets to define exact columns:

```python
BOARD_COLUMNS = tuple(ThsBoard.__dataclass_fields__)
CONSTITUENT_COLUMNS = tuple(ThsBoardConstituent.__dataclass_fields__)
RELATION_COLUMNS = tuple(ThsStockRelation.__dataclass_fields__)
```

Require exact column sets so Chinese or extra source fields cannot reach SQL.
Validate dates with `validated_trade_date` and require one identical `datetime`
timestamp across all rows.

- [ ] **Step 5: Implement one-transaction replacement**

Use SQLAlchemy `text` and executemany dictionaries. Do not use pandas `to_sql`.
Create a private `_insert(connection, table, columns, rows)` helper with parameter
placeholders. Query counts with `SELECT COUNT(*)` and compare to input lengths
before returning.

- [ ] **Step 6: Preserve the read-only repository contract**

Keep the existing test proving `ThsRepository` has no engine and no public write
methods. Add a test proving `ThsSnapshotWriter` is exported separately rather than
attached to `ThsRepository`.

- [ ] **Step 7: Run writer/repository tests**

Run the command from Step 3.

Expected: PASS.

- [ ] **Step 8: Commit atomic persistence**

```powershell
git add -- "src/stock_lab/modules/ths/writer.py" "src/stock_lab/modules/ths/__init__.py" "tests/unit/modules/ths/test_ths_writer.py" "tests/unit/modules/ths/test_ths_repository.py"
git commit -m "feat: replace THS snapshots atomically"
```

---

### Task 6: Structured THS Snapshot Job

**Files:**
- Create: `src/stock_lab/jobs/ths_snapshot.py`
- Create: `tests/unit/jobs/test_ths_snapshot.py`

**Interfaces:**
- Consumes:
  - `collect_ths_snapshot(source, *, max_workers=4, max_pages=300) -> ThsCollectionResult`
  - `ThsSnapshotWriter.replace_snapshot(...) -> dict[str, int]`
- Produces:
  - `run_ths_snapshot(collect_date=None, max_workers=4, *, source=None, collector=collect_ths_snapshot, writer=None, now=datetime.now) -> dict`
  - `run_cli(argv=None, runner=run_ths_snapshot) -> int`

- [ ] **Step 1: Add failing success/result tests**

Assert one `updated_at` timestamp and one validated `collect_date` are projected
onto every persistence row before writer invocation:

```python
def test_job_persists_complete_snapshot_and_returns_counts():
    writer = RecordingWriter({"boards": 2, "constituents": 3, "stock_relations": 2})

    result = run_ths_snapshot(
        20260812,
        source=object(),
        collector=lambda source, max_workers: complete_result(),
        writer=writer,
        now=lambda: datetime(2026, 8, 12, 18, 0),
    )

    assert result == {
        "status": "success",
        "collected_date": 20260812,
        "boards": 2,
        "constituents": 3,
        "stock_relations": 2,
        "empty_boards": 1,
        "persisted": True,
        "failed_boards": [],
        "errors": [],
    }
```

- [ ] **Step 2: Add failing incomplete/failure tests**

Assert a failed collection returns deterministic failed board dictionaries and
never calls writer. Assert collector exceptions become one failed result with
`persisted=False`. Assert writer exceptions propagate rather than being reported
as a remote collection failure, so database rollback remains visible to operators.

The failed board output shape is:

```python
{
    "board_code": "885001",
    "board_type": "concept",
    "board_name": "Robotics",
    "error": "bounded message",
}
```

- [ ] **Step 3: Add failing input and CLI tests**

Parameterize invalid dates and workers 0/9. Test default date through an injected
`now`. CLI accepts:

```text
--collect-date YYYYMMDD
--max-workers 1..8
```

It prints JSON and returns 0 for `success`, 1 for `failed`.

- [ ] **Step 4: Run job tests and verify failure**

```powershell
uv run --frozen pytest -q tests/unit/jobs/test_ths_snapshot.py --import-mode=importlib
```

Expected: collection FAIL because `ths_snapshot.py` does not exist.

- [ ] **Step 5: Implement job projection and result handling**

Validate `collect_date` with `validated_trade_date`; default to
`now().strftime("%Y%m%d")`. Validate `max_workers` before default dependency
creation. Lazily compose:

```python
database = create_database_client()
source = ThsHttpSource()
writer = ThsSnapshotWriter(database.engine)
```

Only create dependencies that were not injected. Convert each immutable source
row to the exact canonical dictionary columns and add the same `collected_date`
and `updated_at` values.

- [ ] **Step 6: Implement CLI and run tests**

Use `argparse`, print `json.dumps(result, ensure_ascii=False, default=str)`, and
map result status to exit code.

Run the command from Step 4.

Expected: PASS.

- [ ] **Step 7: Commit structured job**

```powershell
git add -- "src/stock_lab/jobs/ths_snapshot.py" "tests/unit/jobs/test_ths_snapshot.py"
git commit -m "feat: add THS snapshot job"
```

---

### Task 7: Restore Thin `_6` Compatibility Surface

**Files:**
- Create: `task/_6_同花顺行业和概念.py`
- Create: `tests/unit/compatibility/test_ths_task.py`
- Modify: `tests/test_cutover_contracts.py`
- Modify: `tests/test_ths_contracts.py`

**Interfaces:**
- Consumes: `stock_lab.jobs.ths_snapshot.run_ths_snapshot` and `run_cli`.
- Produces:
  - `采集同花顺板块成分股(collect_date=None, max_workers=4) -> dict`
  - `每日更新同花顺板块成分股(collect_date=None, max_workers=4) -> dict`
  - `update(collect_date=None, max_workers=4) -> dict`
  - import-safe `_cli(argv=None) -> int`

- [ ] **Step 1: Add failing forwarding tests**

Monkeypatch private delegates and assert exact arguments for all three names:

```python
@pytest.mark.parametrize(
    "name",
    ["采集同花顺板块成分股", "每日更新同花顺板块成分股", "update"],
)
def test_ths_task_names_are_exact_forwards(monkeypatch, name):
    monkeypatch.setattr(
        legacy_ths,
        "_run_ths_snapshot",
        lambda collect_date=None, max_workers=4: (collect_date, max_workers),
    )

    assert getattr(legacy_ths, name)(20260812, 3) == (20260812, 3)
```

Assert no `补采同花顺缺失板块成分股` attribute exists.

- [ ] **Step 2: Add failing import-safety and CLI-forward tests**

Reload the module while database, requests, AkShare, and V8 factories are guarded
to raise if called. Assert `_cli` forwards argv unchanged.

- [ ] **Step 3: Extend cutover wrapper contracts**

Add:

```python
"task/_6_同花顺行业和概念.py": 80,
```

to `WRAPPER_LIMITS`. Keep `requests`, `sqlalchemy`, `akshare`, and `utils` forbidden.
Extend the active-runtime THS scan to continue rejecting the three legacy Chinese
table literals while allowing the Chinese task filename and function identifiers.

- [ ] **Step 4: Run compatibility tests and verify failure**

```powershell
uv run --frozen pytest -q tests/unit/compatibility/test_ths_task.py tests/test_cutover_contracts.py tests/test_ths_contracts.py -k "not output_directory_tracks_only_ignore_policy" --import-mode=importlib
```

Expected: FAIL because the `_6` wrapper is absent.

- [ ] **Step 5: Implement the pure wrapper**

Every function body must contain one return call:

```python
from stock_lab.jobs.ths_snapshot import run_cli as _run_cli
from stock_lab.jobs.ths_snapshot import run_ths_snapshot as _run_ths_snapshot


def 采集同花顺板块成分股(collect_date=None, max_workers=4):
    return _run_ths_snapshot(collect_date, max_workers)
```

Repeat the same direct delegate for the daily and English aliases. Add the standard
`if __name__ == "__main__": raise SystemExit(_cli())` block.

- [ ] **Step 6: Run compatibility/cutover tests**

Run the command from Step 4.

Expected: PASS except the explicitly deselected output contract.

- [ ] **Step 7: Commit compatibility entry point**

```powershell
git add -- "task/_6_同花顺行业和概念.py" "tests/unit/compatibility/test_ths_task.py" "tests/test_cutover_contracts.py" "tests/test_ths_contracts.py"
git commit -m "feat: restore upstream THS task"
```

---

### Task 8: Documentation, Full Verification, And Review

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/migration.md`
- Modify: `docs/database-migrations.md`
- Modify: `db/migrations/README.md`
- Modify: `docs/historical-data-source-matrix.md`
- Modify: `docs/historical-data-backfill-runbook.md`

**Interfaces:**
- Produces: accurate operator guidance and final ownership documentation.

- [ ] **Step 1: Update archival-only documentation**

Document all of these facts explicitly:

- the three tables now have a runtime full-snapshot producer;
- `ThsRepository` remains read-only while `ThsSnapshotWriter` owns replacement;
- `002`/`004` remain migration paths but are no longer the only writers;
- `_6` is an independent CLI, not part of daily update;
- no persistent CSV/cache or incremental supplementation exists;
- default 4 workers, global 0.5-second pacing, 20-second timeout, 3 attempts;
- blockrank exact count and strict HTML fallback;
- concept `clid` is mandatory;
- source-proven empty boards are retained;
- any incomplete board blocks all three table writes;
- MySQL replacement is one transaction;
- Redis and `task_runs` are not used yet.

Add an operator command:

```powershell
uv run --frozen python -m task._6_同花顺行业和概念 --collect-date 20260812 --max-workers 4
```

- [ ] **Step 2: Run import and CLI help checks**

```powershell
uv run --frozen python -c "import importlib; importlib.import_module('task._6_同花顺行业和概念'); print('UPSTREAM_THS_IMPORT_OK')"
uv run --frozen python -m task._6_同花顺行业和概念 --help
```

Expected: both commands exit zero without opening MySQL, loading V8, or making a
network request.

- [ ] **Step 3: Run focused THS verification**

```powershell
uv run --frozen pytest -q --import-mode=importlib tests/unit/modules/ths tests/unit/infrastructure/market_data/test_ths_source.py tests/unit/jobs/test_ths_snapshot.py tests/unit/compatibility/test_ths_task.py tests/test_ths_contracts.py tests/test_cutover_contracts.py -k "not output_directory_tracks_only_ignore_policy"
```

Expected: PASS.

- [ ] **Step 4: Run full verification**

```powershell
uv run --frozen pytest -q --import-mode=importlib
uv run --frozen pytest -q --import-mode=importlib -k "not output_directory_tracks_only_ignore_policy"
uv run --frozen python -m compileall src task tests
git diff --check
git status --short
```

Expected: the unfiltered suite has only the approved `output/.gitignore` failure;
the filtered suite, compilation, and diff checks pass.

- [ ] **Step 5: Request independent code review**

Review the implementation range against:

```text
docs/superpowers/specs/2026-08-12-upstream-ths-snapshot-migration-design.md
docs/superpowers/plans/2026-08-12-upstream-ths-snapshot-migration.md
```

The reviewer must inspect import-time safety, global pacing under concurrency,
retry/Cookie behavior, directory and `clid` parsing, exact blockrank count,
pagination completeness, explicit empty proof, failure aggregation, deterministic
relations, pre-transaction validation, delete/insert/count order, rollback,
wrapper purity, legacy-table scans, documentation accuracy, and missing tests.

Fix all Critical and Important findings, then rerun Step 4.

- [ ] **Step 6: Commit documentation and final consistency fixes**

Inspect `git status`, `git diff`, and recent log; stage only intended files.

```powershell
git add -- "README.md" "docs/architecture.md" "docs/migration.md" "docs/database-migrations.md" "db/migrations/README.md" "docs/historical-data-source-matrix.md" "docs/historical-data-backfill-runbook.md"
git commit -m "docs: document THS snapshot collection"
```

Do not create an empty commit if review fixes already included all documentation.
