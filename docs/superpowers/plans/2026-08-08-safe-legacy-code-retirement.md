# Safe Legacy Code Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete only pre-refactor files and generated artifacts proven to have no active runtime, test, documentation, migration, or compatibility consumer.

**Architecture:** Repository contracts define the approved deletion boundary. Each deletion group first fails an absence/reference test, then removes files and verifies all surviving compatibility surfaces remain untouched. The final cutover branch merge supplies the already-tested database retirement deletions.

**Tech Stack:** Python 3.12, pytest, Vue 3, Vite 8, npm, Git.

## Global Constraints

- Delete only files listed in the approved retirement design.
- Keep documented compatibility wrappers, all strategy sources, database migrations, schema provenance, and runtime state.
- Do not combine environment-variable implementation with deletion commits.
- Do not create repository-wide line-ending normalization.
- Generated `output/` files must remain writable at runtime but untracked by Git.

---

### Task 1: Remove Unused Python Utilities

**Files:**
- Delete: `utils/api.py`
- Delete: `utils/model_util.py`
- Delete: `utils/tdx_util.py`
- Delete: `utils/driver_chrome.py`
- Delete: `tests/test_driver_chrome.py`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Produces: `test_retired_python_utilities_are_absent()` as the deletion guard.

- [ ] **Step 1: Write the failing deletion contract**

  ```python
  def test_retired_python_utilities_are_absent():
      retired = (
          "utils/api.py",
          "utils/model_util.py",
          "utils/tdx_util.py",
          "utils/driver_chrome.py",
          "tests/test_driver_chrome.py",
      )
      assert [path for path in retired if (ROOT / path).exists()] == []
  ```

- [ ] **Step 2: Verify RED**

  Run the focused test and confirm all five paths are reported.

- [ ] **Step 3: Delete the five files**

  Use tracked file deletion only; do not modify surviving `utils` compatibility modules.

- [ ] **Step 4: Verify GREEN and references**

  Run the focused contract and search active Python/tests/docs for the four removed module names.

- [ ] **Step 5: Commit**

  Commit message: `删除无引用旧工具代码`.

### Task 2: Remove Frontend Template Residue

**Files:**
- Delete: `front/src/assets/hero.png`
- Delete: `front/src/assets/vite.svg`
- Delete: `front/src/assets/vue.svg`
- Delete: `front/public/icons.svg`
- Delete: `front/README.md`
- Modify: `front/package.json`
- Modify: `front/package-lock.json`
- Modify: `front/src/style.css`
- Modify: `front/src/views/StrategyPickMonitor.vue`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Produces: `test_frontend_template_residue_is_absent()`.

- [ ] **Step 1: Write the failing frontend deletion contract**

  Assert all five files are absent, `@tailwindcss/postcss` is absent from `package.json`, dead selectors are absent from `style.css`, and `StrategyPickMonitor.vue` does not declare `active`.

- [ ] **Step 2: Verify RED**

  Run the focused contract and confirm it fails on current files/dependency/selectors.

- [ ] **Step 3: Delete files and remove dead code**

  Run `npm uninstall @tailwindcss/postcss` in `front/`, remove only `.card`, `.card:hover`, `.tab-active`, and remove only the unread `active` prop declaration.

- [ ] **Step 4: Verify GREEN**

  Run the focused contract, `npm test`, and `npm run build`.

- [ ] **Step 5: Commit**

  Commit message: `清理前端模板残留`.

### Task 3: Stop Tracking Generated Output

**Files:**
- Delete: all currently tracked descendants under `output/`
- Create: `output/.gitignore`
- Modify: `tests/test_cutover_contracts.py`

**Interfaces:**
- Produces: an ignored but writable `output/` runtime directory.

- [ ] **Step 1: Write the failing output contract**

  ```python
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
  ```

- [ ] **Step 2: Verify RED**

  Run the focused contract and confirm tracked generated files are listed.

- [ ] **Step 3: Delete tracked output and add policy**

  Delete all tracked output descendants and create the exact ignore policy. Do not change code that writes to `output/`.

- [ ] **Step 4: Verify GREEN**

  Run the focused contract and confirm a temporary generated file under `output/` does not appear in `git status`, then remove that temporary file.

- [ ] **Step 5: Commit**

  Commit message: `停止跟踪生成输出文件`.

### Task 4: Merge Database Cutover And Verify

**Files:**
- Merge branch: `migration/final-legacy-cutover` at `d721ce1`

**Interfaces:**
- Produces: `main` containing migration `004`, hardened `003`, and retired Jiuyan reconciliation files.

- [ ] **Step 1: Merge the branch**

  Run `git merge migration/final-legacy-cutover`. Resolve only genuine conflicts in shared migration/test documentation.

- [ ] **Step 2: Run complete tests**

  ```powershell
  uv run pytest --import-mode=importlib -q
  npm --prefix front test
  npm --prefix front run build
  git diff --check
  ```

- [ ] **Step 3: Verify database state**

  Confirm no mapped legacy tables remain, `003_drop_legacy_schema` is recorded once, and the latest run has 16 detail rows with zero missing/mismatch/lost counts.

- [ ] **Step 4: Clean worktree and branch**

  Remove `.worktrees/final-legacy-cutover`, prune worktrees, and delete `migration/final-legacy-cutover` only after all merged verification passes.
