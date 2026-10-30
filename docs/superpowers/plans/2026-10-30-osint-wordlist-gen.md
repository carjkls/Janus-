# Gerador de OSINT + Wordlist Inteligente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **This plan has no TDD/RED-GREEN steps by explicit user decision** (see Global Constraints) — each task ends with a manual sanity check and a self-review pass instead of a test run.

**Goal:** Fetch an Instagram profile's public data (logic adapted from toutatis), extract seed words from it, and generate both an expanded wordlist (`.txt`) and an equivalent hashcat rule file (`.rule`), plus an OSINT report that keeps system-discovered and operator-added data clearly separated.

**Architecture:** A single-pass pipeline — profile fetch → seed extraction → mutation (wordlist + rule file) → report assembly — with no shared mutable state between stages; each stage is a pure function over the previous stage's output.

**Tech Stack:** Python 3.10+, `requests`, `phonenumbers` + `pycountry` (carried over from toutatis for phone-number formatting), stdlib only otherwise.

**Spec:** `docs/superpowers/specs/2026-10-30-janus-design.md`

## Global Constraints

- v1 covers exactly one Instagram profile per execution — no other OSINT sources.
- No automatic breach/leak checking (no HIBP call) — an email is "leaked" only if the operator says so via `--user-email`.
- No local hash cracking — the wordlist is delivered as a file; cracking happens in the operator's own separate system, which this project never touches.
- Emails and wordlists each split into two groups that are never merged: `osint` (system-discovered) vs `user_added` (operator-supplied).
- The `.rule` file's content is fixed and **independent of any specific profile's data** — no seed, year, or name gets baked into it; only the `.txt` wordlist is data-specific.
- License is **GPLv3** (not MIT) — code in `osint/instagram_profile.py` is adapted from [toutatis](https://github.com/megadose/toutatis) by megadose (GPLv3); attribution required in that file's header and in the README.
- **No automated test suite, no TDD** — this is an explicit user decision to prioritize delivery speed. Each task substitutes a manual sanity check (a one-off `python -c` run against synthetic/mocked data) and ends with a self-review pass instead of a RED→GREEN cycle.
- No commit steps in this plan — the user commits from their own terminal.

## Review Focus

- An invalid/expired `sessionid` or a 404 profile must surface as a clear CLI message, never a raw traceback. → Task 2, Task 7
- A rate-limited Instagram response (empty/non-JSON body) must be detected and reported clearly, not crash on a JSON-decode error. → Task 2
- A profile missing optional fields (no bio, no external URL, no business category) must not crash seed extraction — those seeds are just absent, not an error. → Task 3
- `wordlist.generated` and `wordlist.user_added` must never be merged into the same file or the same count in the report. → Task 6, Task 7
- The emitted `.rule` file's content must be identical regardless of which profile or years were used to generate the run — no data leaks into it. → Task 5

---

## File Structure

```
janus/
  pyproject.toml
  requirements.txt
  .gitignore
  LICENSE                      # GPLv3 full text
  README.md
  janus/
    __init__.py
    __main__.py
    cli.py
    osint/
      __init__.py
      instagram_profile.py     # adapted from toutatis, attribution header
    seeds.py
    mutation/
      __init__.py
      rules.py                  # wordlist generation
      hashcat_rules.py          # .rule file generation
    report.py
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `.gitignore`, `LICENSE`, `README.md`
- Create: `janus/__init__.py`, `janus/__main__.py`
- Create: `janus/osint/__init__.py`, `janus/mutation/__init__.py`

**Interfaces:**
- Produces: installable package `janus`, `__version__ = "0.1.0"`, console entrypoint `janus` (wired now, implemented in Task 7).

- [ ] **Step 1: Write `pyproject.toml`**

`[project]` name `janus`, `requires-python = ">=3.10"`, `license = { text = "GPL-3.0-or-later" }`, `dependencies = ["requests>=2.31", "phonenumbers>=8.13", "pycountry>=23.12"]`, `[project.scripts] janus = "janus.cli:main"`, `[tool.setuptools.packages.find] include = ["janus*"]`. Mirror the `[build-system]` block from the other two projects in this session.

- [ ] **Step 2: Write `requirements.txt`**

`requests>=2.31`, `phonenumbers>=8.13`, `pycountry>=23.12`.

- [ ] **Step 3: Write `.gitignore`**

Same as the session's other two projects (`__pycache__/`, `*.py[cod]`, `*.egg-info/`, `build/`, `dist/`, `.venv/`, `venv/`, `.pytest_cache/`, `reports/`, `*.json.report`, `.DS_Store`).

- [ ] **Step 4: Write `LICENSE`**

Full GPLv3 text (same text as toutatis's own `LICENSE`, with the copyright line updated to this project's author/year).

- [ ] **Step 5: Write `README.md`**

Cover: what the tool does (OSINT report + mutation-based wordlist from one Instagram profile), the authorized-use-only disclaimer, a clear **attribution section** naming toutatis (megadose, https://github.com/megadose/toutatis, GPLv3) and stating that `osint/instagram_profile.py` adapts its profile-fetch logic, install instructions, usage examples for every CLI flag from the spec's `cli.py` section, the v1 scope limits (one Instagram profile only; no breach checking; no local cracking) from the spec's "Fora de escopo" section, and a note on obtaining an Instagram `sessionid` (same pointer toutatis's own README gives).

- [ ] **Step 6: Write package skeleton**

`janus/__init__.py`: docstring + `__version__ = "0.1.0"` + `__all__ = ["__version__"]`. `janus/__main__.py`: `from .cli import main` + `if __name__ == "__main__": raise SystemExit(main())`. One-line docstring `__init__.py` for `osint/` and `mutation/`.

- [ ] **Step 7: Verify the package installs**

Run: `pip install -e .`
Expected: succeeds with no errors.

- [ ] **Step 8: Self-review**

Read `pyproject.toml` and `README.md` back: license says GPLv3 everywhere (not MIT, which the other two session projects use), toutatis attribution is present and accurate (correct URL, correct license name).

---

### Task 2: `osint/instagram_profile.py`

**Files:**
- Create: `janus/osint/instagram_profile.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Profile:
      username: str
      user_id: str
      full_name: str
      biography: str
      external_url: str | None
      is_business: bool
      business_category: str | None
      follower_count: int
      following_count: int
      public_email: str | None
      obfuscated_email: str | None
      obfuscated_phone: str | None
      profile_pic_url: str | None

  class ProfileError(RuntimeError):
      """Not found, rate-limited, or invalid session — carries a human-readable message."""

  def get_profile(search: str, session_id: str, search_type: str = "username") -> Profile: ...
  ```

- [ ] **Step 1: Write the module header and adapt the three toutatis functions**

Start the file with a comment block: `# Profile-fetch logic adapted from toutatis (https://github.com/megadose/toutatis) by megadose, GPLv3.` Port `getUserId`, the `info/` lookup, and `advanced_lookup` from toutatis's `core.py` into three internal functions (`_get_user_id`, `_get_user_info`, `_advanced_lookup`), keeping their request shapes (headers, cookies, endpoints) identical — only change: raise `ProfileError` with a specific message instead of returning `{"error": ...}` dicts:
  - user not found (404) → `ProfileError("profile not found")`
  - non-JSON / empty response (toutatis's `JSONDecodeError` case) → `ProfileError("rate limited by Instagram — wait a few minutes and retry")`
  - any `requests.exceptions.RequestException` → `ProfileError(f"request failed: {exc}")`

- [ ] **Step 2: Implement `get_profile`**

Orchestrates: resolve `user_id` (via `_get_user_id` if `search_type == "username"`, else `str(int(search))`, raising `ProfileError("invalid id")` on a non-numeric id), call `_get_user_info(user_id, session_id)`, call `_advanced_lookup(info["username"])` and merge its `obfuscated_email`/`obfuscated_phone` into the result if present (missing/error from the advanced lookup is not fatal — leave those two fields `None`). Build and return a `Profile` from the merged dict, mapping toutatis's raw field names (`full_name`, `biography`, `external_url`, `is_business`, `follower_count`, `following_count`, `public_email`, `public_phone_number` region info not needed here) onto the dataclass; `business_category` comes from `info.get("category_name")` (`None` if absent).

- [ ] **Step 3: Manual sanity check**

Run: `python -c "from janus.osint.instagram_profile import Profile; print(Profile(username='x', user_id='1', full_name='X', biography='', external_url=None, is_business=False, business_category=None, follower_count=0, following_count=0, public_email=None, obfuscated_email=None, obfuscated_phone=None, profile_pic_url=None))"`
Expected: prints the dataclass with no import error (confirms the module loads and the dataclass signature is well-formed — a live API call isn't exercised here per the spec's no-automated-network-test constraint).

- [ ] **Step 4: Self-review**

Re-read against toutatis's `core.py`: every raw field read from the API response matches toutatis's own field names exactly (no typo'd key). Every error path toutatis handled (404, rate limit, request exception) has a corresponding `ProfileError` here, matching Review Focus items 1–2.

---

### Task 3: `seeds.py`

**Files:**
- Create: `janus/seeds.py`

**Interfaces:**
- Consumes: `Profile` (Task 2).
- Produces:
  ```python
  @dataclass(frozen=True)
  class SeedSet:
      name_parts: list[str]   # from full_name, lowercased, deduped
      other: list[str]         # username + bio tokens + url domain + business_category + extra_seeds

  def extract_seeds(profile: Profile, extra_seeds: list[str] | None = None) -> SeedSet: ...
  ```

- [ ] **Step 1: Implement `extract_seeds`**

`name_parts`: `profile.full_name.split()`, lowercased, deduped, tokens shorter than 2 chars dropped.
`other`: starts with `[profile.username]` (lowercased); if `profile.biography`, tokenize on `re.split(r"[^\w]+", biography)`, lowercase, drop tokens shorter than 3 chars or in a small stopword set `{"the", "and", "for", "com", "de", "da", "do", "que", "para", "com"}`, keep at most the first 15 surviving tokens (documented shortcut: caps seed growth from long bios); if `profile.external_url`, take `urlsplit(url).netloc`, strip a leading `"www."`, take the segment before the first `.` as a seed; if `profile.business_category`, lowercase it and split on whitespace, add each word; finally extend with `extra_seeds` (lowercased). Dedupe `other` preserving first-seen order, cap at 20 total entries (documented shortcut: keeps the wordlist generator's output bounded).

- [ ] **Step 2: Manual sanity check**

Run a `python -c` call building a synthetic `Profile` (full_name="Ana Souza", username="anasouza", biography="CEO at Minha Empresa", external_url="https://www.minhaempresa.com.br", business_category="Local Business") through `extract_seeds`, print the result.
Expected: `name_parts == ["ana", "souza"]`; `other` contains `"anasouza"`, `"minhaempresa"` (from the URL), `"local"`, `"business"` (from the category); no crash.

- [ ] **Step 3: Self-review**

Confirm a `Profile` with every optional field `None`/empty (no bio, no external_url, no business_category) produces a `SeedSet` with `other == [profile.username]` and no exception — Review Focus item 3.

---

### Task 4: `mutation/rules.py`

**Files:**
- Create: `janus/mutation/rules.py`

**Interfaces:**
- Consumes: `SeedSet` (Task 3).
- Produces: `generate_wordlist(seed_set: SeedSet, years: list[str] | None = None) -> list[str]`.
- Constants (exact values, pinned by the spec): `LEET_MAP = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5"}`; `SEPARATORS = (".", "_", "-", "")`; `SUFFIXES = ("123", "!", "@") + tuple(f"{n:02d}" for n in range(100))`.

- [ ] **Step 1: Implement `generate_wordlist`**

Algorithm, in order:
1. `base = list(seed_set.name_parts) + list(seed_set.other)`, plus every ordered pair `(a, b)` of **distinct** `seed_set.name_parts` joined as `f"{a}{sep}{b}"` for each `sep` in `SEPARATORS` (name-part concatenations only — not a cross product over all seeds, to keep output bounded per the spec).
2. For each word in `base`, generate its case variants: the word itself, `.lower()`, `.upper()`, `.capitalize()` — dedupe this set of 4 (or fewer, if some collide).
3. For each case variant, also generate **one** leet variant: apply every substitution in `LEET_MAP` simultaneously (not per-letter subsets) to that variant's lowercase form.
4. Collect every variant from steps 2–3 into `candidates`.
5. For each candidate, also emit candidate + each suffix in `SUFFIXES`, and — if `years` is given — candidate prefixed and suffixed by each year in `years`.
6. Return the deduplicated union of every string produced in steps 2–5, sorted.

- [ ] **Step 2: Manual sanity check**

Run: `python -c` with `SeedSet(name_parts=["ana","souza"], other=["anasouza"])` and `years=["1998"]` through `generate_wordlist`, print `len(result)` and check `"Ana"`, `"4n4"`, `"ana.souza"`, `"anasouza123"`, `"1998ana"` are all present.
Expected: all five appear in the returned list; no exception.

- [ ] **Step 3: Self-review**

Confirm the function never raises on an empty `SeedSet` (e.g. `SeedSet([], [])` with no years) — it should just return `[]` or a very small suffix-only list, not crash. Confirm `years=None` is handled (no prefix/suffix step attempted).

---

### Task 5: `mutation/hashcat_rules.py`

**Files:**
- Create: `janus/mutation/hashcat_rules.py`

**Interfaces:**
- Produces: `generate_rule_file() -> str` — **no parameters**, per the Global Constraint that this content is data-independent.

- [ ] **Step 1: Implement `generate_rule_file`**

Returns this fixed multi-line string (one hashcat rule per line), reproducing the same mutation classes as `rules.py` but as rule syntax rather than pre-expanded strings:
```
:
l
u
c
sa4
se3
si1
so0
ss5
l sa4 se3 si1 so0 ss5
c sa4 se3 si1 so0 ss5
$1
$2
$3
$!
$@
c $1 $2 $3
l $1 $2 $3
```
(`:` = no-op/keep original, `l`/`u`/`c` = lower/upper/capitalize, `sXY` = substitute X with Y, `$N` = append character N — standard hashcat rule syntax.)

- [ ] **Step 2: Manual sanity check**

Run: `python -c "from janus.mutation.hashcat_rules import generate_rule_file; print(generate_rule_file())"` twice.
Expected: identical output both times (confirms it takes no input and is deterministic — Review Focus item 5), and every line is non-empty.

- [ ] **Step 3: Self-review**

Confirm no profile data, seed, or year appears anywhere in the function — it must compile to the same constant regardless of caller.

---

### Task 6: `report.py`

**Files:**
- Create: `janus/report.py`

**Interfaces:**
- Consumes: `Profile` (Task 2).
- Produces:
  ```python
  @dataclass(frozen=True)
  class EmailSet:
      osint: list[str]
      user_added: list[str]

  @dataclass(frozen=True)
  class WordlistInfo:
      path: str
      count: int

  @dataclass(frozen=True)
  class Report:
      profile: Profile
      emails: EmailSet
      wordlist_generated: WordlistInfo
      wordlist_user_added: WordlistInfo | None
      rules_path: str

  def build_report(
      profile: Profile, user_emails: list[str],
      wordlist_path: str, wordlist_count: int,
      user_wordlist_path: str | None, user_wordlist_count: int,
      rules_path: str,
  ) -> Report: ...
  def print_report(report: Report) -> None: ...
  def report_to_json(report: Report) -> str: ...
  def save_json(report: Report, path: str) -> None: ...
  ```

- [ ] **Step 1: Implement `build_report`**

`emails.osint = [profile.public_email] if profile.public_email else []`; `emails.user_added = list(user_emails)`; `wordlist_generated = WordlistInfo(wordlist_path, wordlist_count)`; `wordlist_user_added = WordlistInfo(user_wordlist_path, user_wordlist_count) if user_wordlist_path else None` — **never** combine `wordlist_generated` and `wordlist_user_added` into one count or one path (Review Focus item 4).

- [ ] **Step 2: Implement `print_report` and `report_to_json`/`save_json`**

`print_report`: same console style as the other two session projects (a header banner, then sections for profile summary, emails split by `osint`/`user_added`, wordlist counts split by `generated`/`user_added`, and the rules file path). `report_to_json`: `json.dumps(dataclasses.asdict(report), indent=2, ensure_ascii=False)`. `save_json`: writes that to `path`.

- [ ] **Step 3: Manual sanity check**

Build a `Report` from a synthetic `Profile` plus `user_emails=["old@leak.example"]`, call `print_report` and `report_to_json`, inspect the JSON.
Expected: `emails.osint` and `emails.user_added` are distinct lists in the JSON; printed output has no exception.

- [ ] **Step 4: Self-review**

Confirm `wordlist_generated.path` and `wordlist_user_added.path` (when present) are never the same string, and that `json.dumps` round-trips without a `TypeError` (every field is a plain dataclass/str/int/list, nothing exotic).

---

### Task 7: `cli.py`

**Files:**
- Create: `janus/cli.py`

**Interfaces:**
- Consumes: `get_profile`, `ProfileError` (Task 2); `extract_seeds` (Task 3); `generate_wordlist` (Task 4); `generate_rule_file` (Task 5); `build_report`, `print_report`, `save_json` (Task 6); `__version__` (Task 1).
- Produces: `build_parser() -> argparse.ArgumentParser`, `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Implement `build_parser`**

Flags: `-u/--username` and `-i/--id` as a mutually exclusive required group (matching toutatis's own interface); `-s/--session-id` (required); `--years` (comma-separated string, parsed into a list); `--extra-seed` (`action="append"`); `--user-email` (`action="append"`); `--user-wordlist` (path, optional); `-o/--output` (default `"report.json"`); `--wordlist-out` (default `"wordlist.txt"`); `--rules-out` (default `"rules.rule"`); `--version`.

- [ ] **Step 2: Implement `main`**

Parse args; call `get_profile(args.username or args.id, args.session_id, "username" if args.username else "id")` inside a `try/except ProfileError as exc`, printing `f"[!] {exc}"` to stderr and returning `2` on failure (Review Focus item 1). On success: `extract_seeds(profile, extra_seeds=args.extra_seed or [])`; `generate_wordlist(seed_set, years=args.years.split(",") if args.years else None)` → write to `args.wordlist_out`, one word per line; `generate_rule_file()` → write to `args.rules_out`; if `args.user_wordlist`, read it and count its lines (do not merge its contents into `wordlist_out`); `build_report(...)` with all of the above; `print_report(report)`; `save_json(report, args.output)`. Return `0`.

- [ ] **Step 3: Manual sanity check**

Run: `python -m janus --help`
Expected: prints usage with every flag listed, exit code `0`.

Run: `python -m janus -u x -s y` (no real network reachable from this sanity check, or an obviously invalid session) and confirm the failure path prints `[!] ...` and returns a non-zero code rather than a traceback.

- [ ] **Step 4: Self-review**

Walk `main` against the Global Constraints list once more: no HIBP call anywhere, no cracking logic, `.rule` file write has no profile data threaded into it, wordlist and user-wordlist never touch the same file handle.

---

### Task 8: Final adversarial review

**Files:** none (read-only review pass; fixes land in whichever task's file they belong to).

**Interfaces:**
- Consumes: everything (Tasks 1–7).

- [ ] **Step 1: Dispatch a fresh reviewer** (same process as the session's other two projects: a subagent with no prior context, reading the whole `janus/` tree against this plan and the spec, with the plan's Review Focus section given verbatim)

- [ ] **Step 2: Triage findings**

Re-grade by actual user impact. Fix Critical/Important findings directly (with a manual sanity check proving the fix, since there's no test suite to pin it); ledger Minor findings as deferred, matching the process used for the other two projects in this session.

- [ ] **Step 3: Confirm the package still installs and the CLI still runs after any fixes**

Run: `pip install -e .` then `python -m janus --help`.
Expected: both succeed.
