# Batch Sales Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `get_sales_data_batch()` (calling `POST /api/v0.3/salesdata/batch`, up to 100 events per request) to both SDK clients, with SDK-wide `402 -> SeatDataPaymentError` handling, released as 1.1.0.

**Architecture:** A new pure module `seatdata/_batch.py` (client-side validation/coercion via `prepare_batch_payload` and response normalization via `normalize_batch_response`) is shared by `SeatDataClient` and `AsyncSeatDataClient`, each of which adds a thin `get_sales_data_batch()` over the existing shared `_Transport`. The transport's error routing gains a `payment_required` mapping plus a status-first 402 backstop (status checked before the type map) so a 402 raises the new `SeatDataPaymentError` for every body shape (proper envelope with mapped type, unmapped type, or missing `type`; legacy string; non-JSON). Responses are normalized into a `BatchSalesResult` TypedDict (`results` + `errors` maps keyed by canonical decimal-string event id) so both keys are always present.

**Tech Stack:** Python 3.8+ (`typing` + `typing_extensions`), httpx, pytest + respx + pytest-asyncio, black (line length 100), mypy.

**Source of truth:** `/home/chaz/Storage/CreativeStirLLC/SeatDataSDK-Python/docs/superpowers/specs/2026-07-09-batch-salesdata-design.md`

## Global Constraints

- Python 3.8+ compatibility. Annotations use `typing` (`Dict`, `List`, `Optional`, `Sequence`, `Union`, `Any`), and `typing_extensions` for `TypedDict`/`NotRequired` — match the existing files.
- **No comments in code files** (project preference) — implementation code blocks contain no comments. Test files may follow existing test style. (The one docstring on `get_sales_data_batch` is mandated by the design spec's retry re-bill note; a docstring is not a comment — do not remove it.)
- Black formatter, line length 100. mypy must stay clean (`mypy seatdata/`; config `python_version = "3.9"` in `pyproject.toml`).
- Tests use `pytest` + `respx` mocking httpx; unit by default; base URL `https://seatdata.io`. Async tests follow the existing `tests/test_async_client.py` markers/patterns (`@pytest.mark.asyncio` + `@respx.mock`; `pytest.ini` sets `asyncio_mode = auto`).
- Commit steps: conventional prefixes (`feat:`, `test:`, `docs:`, `build:`, `fix:`). Feature/test commits are fine. **No `Co-Authored-By` trailer** and no other attribution trailer in any commit message. Each task ends with its own commit.
- All commands run from the repo root: `/home/chaz/Storage/CreativeStirLLC/SeatDataSDK-Python`.
- Full-suite runs use `pytest -m "not integration" -q` (deterministic even if `SEATDATA_API_KEY` happens to be set; expected shape `N passed, 5 deselected`).
- Line references like `path:NN` describe the file state at the start of that task assuming tasks run in order. Always locate edits by the exact code blocks shown ("replace this exact block"), never by line number alone. Every "replace" anchor below occurs exactly once in its file.
- `CLAUDE.md` is currently **untracked** in git (deliberately). Task 9 edits it on disk but must NOT `git add` it.

## Execution model assignments

Subagent-driven execution dispatches a fresh subagent per task, so the model is chosen per task. **Opus** for the two correctness-critical / subtle tasks; **Sonnet** for the mechanical tasks whose exact code is already spelled out and scratchpad-verified. The orchestrator and the between-task reviewer stay on Opus.

| Task | Model | Why |
|---|---|---|
| 0 Preflight | Sonnet | Run baseline commands; no code. |
| 1 `SeatDataPaymentError` + export | Sonnet | Bare subclass + import/`__all__` edit. |
| 2 SDK-wide 402 transport wiring | **Opus** | Error routing, status-first backstop, mypy `cls: type` narrowing, 7 body-shape tests — subtle. |
| 3 `BatchSalesResult` TypedDict | Sonnet | Add TypedDict + `Any` import. |
| 4 `_batch.py` helpers | **Opus** | Coercion (bool-before-int), str/bytes + non-iterable guards, dedup-before-count — correctness-critical. |
| 5 Sync `get_sales_data_batch` | Sonnet | Thin method + respx tests from exact provided code. |
| 6 Async `get_sales_data_batch` | Sonnet | Async parallel of Task 5 from exact provided code. |
| 7 Deprecation target v1.1 → v2.0 | Sonnet | Three string edits + pinning test. |
| 8 Version bump | Sonnet | Two version-string edits. |
| 9 Docs | Sonnet | CHANGELOG / README / CLAUDE.md from exact provided text. |
| 10 Example + final gate | Sonnet | Example script + run black / mypy / full suite. |

---

### Task 0: Preflight (no commit)

**Model:** Sonnet (baseline commands only).

**Files:** none changed.

- [ ] **Step 1: Confirm the toolchain and baseline.** Run:

  ```bash
  cd /home/chaz/Storage/CreativeStirLLC/SeatDataSDK-Python
  pip install -e ".[dev]" -q
  pytest -m "not integration" -q
  mypy seatdata/
  black --check seatdata/ tests/ examples/
  ```

  Expected: `118 passed, 5 deselected`, `Success: no issues found in 7 source files`, `22 files would be left unchanged`. If the baseline differs, stop and reconcile before starting Task 1.

---

### Task 1: `SeatDataPaymentError` exception + top-level export

**Model:** Sonnet (bare subclass + import/`__all__` edit).

**Files:**
- Modify: `seatdata/exceptions.py:54-59` (insert new class between `SeatDataSubscriptionError` and `SeatDataServerError`)
- Modify: `seatdata/__init__.py:9-10` (import list), `seatdata/__init__.py:30-31` (`__all__`)
- Test: `tests/test_exceptions.py`

**Interfaces:**
- Consumes: existing `class SeatDataError(Exception)` in `seatdata/exceptions.py`.
- Produces: `class SeatDataPaymentError(SeatDataError)` importable as `seatdata.SeatDataPaymentError` and `seatdata.exceptions.SeatDataPaymentError`; listed in `seatdata.__all__`. Tasks 2, 5, 6, 9, 10 use this exact name.

- [ ] **Step 1: Write the failing tests.** In `tests/test_exceptions.py`, make three changes.

  (a) Replace this exact block (in the `from seatdata.exceptions import (...)` at the top of the file):

  ```python
      SeatDataSubscriptionError,
      SeatDataServerError,
      CursorExpiredError,
  ```

  with:

  ```python
      SeatDataSubscriptionError,
      SeatDataPaymentError,
      SeatDataServerError,
      CursorExpiredError,
  ```

  (b) Replace this exact block (inside `test_all_inherit_from_base`):

  ```python
              SeatDataSubscriptionError,
              SeatDataServerError,
              CursorExpiredError,
  ```

  with:

  ```python
              SeatDataSubscriptionError,
              SeatDataPaymentError,
              SeatDataServerError,
              CursorExpiredError,
  ```

  (c) Append this method at the end of class `TestExceptionHierarchy` (end of file, after `test_base_error_carries_diagnostic_fields`):

  ```python
      def test_payment_error_importable_from_top_level_package(self):
          import seatdata

          assert seatdata.SeatDataPaymentError is SeatDataPaymentError
          assert "SeatDataPaymentError" in seatdata.__all__
  ```

- [ ] **Step 2: Run the test, expect FAIL.**

  ```bash
  pytest tests/test_exceptions.py -q
  ```

  Expected: `1 error` during collection — `ImportError: cannot import name 'SeatDataPaymentError' from 'seatdata.exceptions'`.

- [ ] **Step 3: Add the exception class.** In `seatdata/exceptions.py`, replace this exact block:

  ```python
  class SeatDataSubscriptionError(SeatDataError):
      pass


  class SeatDataServerError(SeatDataError):
      pass
  ```

  with:

  ```python
  class SeatDataSubscriptionError(SeatDataError):
      pass


  class SeatDataPaymentError(SeatDataError):
      pass


  class SeatDataServerError(SeatDataError):
      pass
  ```

- [ ] **Step 4: Run the test, expect one remaining FAIL.**

  ```bash
  pytest tests/test_exceptions.py -q
  ```

  Expected: `1 failed, 9 passed` — `test_payment_error_importable_from_top_level_package` fails with `AttributeError: module 'seatdata' has no attribute 'SeatDataPaymentError'`.

- [ ] **Step 5: Export from the package.** In `seatdata/__init__.py`, make two changes.

  (a) Replace this exact block (in the `from .exceptions import (...)` list):

  ```python
      SeatDataSubscriptionError,
      SeatDataServerError,
      CursorExpiredError,
  ```

  with:

  ```python
      SeatDataSubscriptionError,
      SeatDataPaymentError,
      SeatDataServerError,
      CursorExpiredError,
  ```

  (b) Replace this exact block (in `__all__`):

  ```python
      "SeatDataSubscriptionError",
      "SeatDataServerError",
  ```

  with:

  ```python
      "SeatDataSubscriptionError",
      "SeatDataPaymentError",
      "SeatDataServerError",
  ```

- [ ] **Step 6: Run the test, expect PASS.**

  ```bash
  pytest tests/test_exceptions.py -q
  ```

  Expected: `10 passed`.

- [ ] **Step 7: Format and type-check.**

  ```bash
  black seatdata/ tests/
  mypy seatdata/
  ```

  Expected: no reformatting; `Success: no issues found in 7 source files`.

- [ ] **Step 8: Commit.**

  ```bash
  git add seatdata/exceptions.py seatdata/__init__.py tests/test_exceptions.py
  git commit -m "feat: add SeatDataPaymentError exception"
  ```

---

### Task 2: SDK-wide 402 transport wiring

**Model:** Opus (error routing + status-first backstop + mypy narrowing + 7 body-shape tests).

**Files:**
- Modify: `seatdata/_transport.py:9-18` (exception imports), `:67-74` (`_ERROR_TYPE_MAP`), `:78-82` (fallback-type map in `_parse_error_body`), `:132` (backstop in `_raise_from_response`)
- Test: `tests/test_transport.py`

**Interfaces:**
- Consumes: `SeatDataPaymentError` from Task 1.
- Produces: every HTTP 402 reaching `_raise_from_response` raises `SeatDataPaymentError` (proper envelope with `type: "payment_required"`, proper envelope with an unmapped `type`, proper envelope missing `type`, legacy string body, non-JSON body), via both `request_json` and `arequest_json`. This holds because the backstop is status-first — it checks `status_code == 402` before consulting the type map, so it wins even when `err_type` has defaulted to `"server_error"` (the typeless-envelope case). `402` remains absent from `_RETRY_STATUS` (never retried). The existing `invalid_cursor` -> `CursorExpiredError` branch and the `SeatDataInvalidRequestError` (`param`) / `SeatDataRateLimitError` (`retry_after`) kwargs handling are preserved unchanged.

- [ ] **Step 1: Write the failing tests.** In `tests/test_transport.py`, make two changes.

  (a) Replace this exact block (in the `from seatdata.exceptions import (...)` at the top of the file):

  ```python
      SeatDataNotFoundError,
      SeatDataRateLimitError,
  ```

  with:

  ```python
      SeatDataNotFoundError,
      SeatDataPaymentError,
      SeatDataRateLimitError,
  ```

  (b) Append this class at the very end of the file (after class `TestAsyncTransport`, separated by two blank lines):

  ```python
  class TestPaymentRequired:
      @respx.mock
      def test_402_envelope_with_unmapped_type_raises_payment_error(self, transport):
          respx.get("https://seatdata.io/api/v1/x").mock(
              return_value=httpx.Response(
                  402,
                  json={
                      "error": {
                          "type": "insufficient_balance",
                          "code": "balance_exhausted",
                          "message": "no balance",
                      }
                  },
              )
          )
          with pytest.raises(SeatDataPaymentError) as exc_info:
              transport.request_json("GET", "/api/v1/x")
          assert exc_info.value.status_code == 402

      @respx.mock
      def test_402_envelope_without_type_raises_payment_error(self, transport):
          respx.get("https://seatdata.io/api/v1/x").mock(
              return_value=httpx.Response(
                  402,
                  json={"error": {"code": "balance_exhausted", "message": "no balance"}},
              )
          )
          with pytest.raises(SeatDataPaymentError) as exc_info:
              transport.request_json("GET", "/api/v1/x")
          assert exc_info.value.status_code == 402

      @respx.mock
      def test_402_envelope_with_payment_required_type(self, transport):
          respx.get("https://seatdata.io/api/v1/x").mock(
              return_value=httpx.Response(
                  402,
                  json={
                      "error": {
                          "type": "payment_required",
                          "code": "payment_required",
                          "message": "payment required",
                      }
                  },
              )
          )
          with pytest.raises(SeatDataPaymentError):
              transport.request_json("GET", "/api/v1/x")

      @respx.mock
      def test_402_legacy_string_body(self, transport):
          respx.get("https://seatdata.io/api/v1/x").mock(
              return_value=httpx.Response(402, json={"error": "Payment required"})
          )
          with pytest.raises(SeatDataPaymentError, match="Payment required"):
              transport.request_json("GET", "/api/v1/x")

      @respx.mock
      def test_402_non_json_body(self, transport):
          respx.get("https://seatdata.io/api/v1/x").mock(
              return_value=httpx.Response(402, text="Payment Required")
          )
          with pytest.raises(SeatDataPaymentError, match="Payment Required"):
              transport.request_json("GET", "/api/v1/x")

      @respx.mock
      def test_402_is_not_retried(self):
          t = _Transport(api_key="a" * 64, max_retries=3)
          try:
              route = respx.get("https://seatdata.io/api/v1/x").mock(
                  return_value=httpx.Response(
                      402,
                      json={"error": {"type": "payment_required", "code": "x", "message": "x"}},
                  )
              )
              with pytest.raises(SeatDataPaymentError):
                  t.request_json("GET", "/api/v1/x")
              assert route.call_count == 1
          finally:
              t.close()

      @pytest.mark.asyncio
      @respx.mock
      async def test_402_async_raises_payment_error_and_is_not_retried(self):
          t = _Transport(api_key="a" * 64, max_retries=3)
          try:
              route = respx.get("https://seatdata.io/api/v1/x").mock(
                  return_value=httpx.Response(
                      402,
                      json={
                          "error": {
                              "type": "insufficient_balance",
                              "code": "balance_exhausted",
                              "message": "no balance",
                          }
                      },
                  )
              )
              with pytest.raises(SeatDataPaymentError):
                  await t.arequest_json("GET", "/api/v1/x")
              assert route.call_count == 1
          finally:
              await t.aclose()
  ```

- [ ] **Step 2: Run the tests, expect FAIL.**

  ```bash
  pytest tests/test_transport.py -k "PaymentRequired" -q
  ```

  Expected: `7 failed, 28 deselected`. Each fails because the wrong exception type propagates out of `pytest.raises(SeatDataPaymentError)` — e.g. `seatdata.exceptions.SeatDataError: no balance` (unmapped envelope), `seatdata.exceptions.SeatDataServerError: no balance` (the typeless envelope — `err.get("type", "server_error")` defaults to `"server_error"`), and `seatdata.exceptions.SeatDataServerError` (legacy-string and non-JSON bodies).

- [ ] **Step 3: Import the exception in the transport.** In `seatdata/_transport.py`, replace this exact block (in the `from .exceptions import (...)` at the top):

  ```python
      SeatDataNotFoundError,
      SeatDataRateLimitError,
  ```

  with:

  ```python
      SeatDataNotFoundError,
      SeatDataPaymentError,
      SeatDataRateLimitError,
  ```

- [ ] **Step 4: Map the explicit envelope type.** In `seatdata/_transport.py`, replace this exact block:

  ```python
      "not_found": SeatDataNotFoundError,
      "rate_limit_error": SeatDataRateLimitError,
  ```

  with:

  ```python
      "not_found": SeatDataNotFoundError,
      "payment_required": SeatDataPaymentError,
      "rate_limit_error": SeatDataRateLimitError,
  ```

- [ ] **Step 5: Add 402 to the non-envelope fallback map.** In `seatdata/_transport.py` (inside `_parse_error_body`), replace this exact block:

  ```python
      fallback_type = {
          401: "authentication_error",
          404: "not_found",
          429: "rate_limit_error",
      }.get(response.status_code, "server_error")
  ```

  with:

  ```python
      fallback_type = {
          401: "authentication_error",
          402: "payment_required",
          404: "not_found",
          429: "rate_limit_error",
      }.get(response.status_code, "server_error")
  ```

- [ ] **Step 6: Add the status-first backstop.** In `seatdata/_transport.py` (inside `_raise_from_response`, after the `CursorExpiredError` branch), replace this exact line:

  ```python
      cls = _ERROR_TYPE_MAP.get(err_type, SeatDataError)
  ```

  with:

  ```python
      cls: type
      if response.status_code == 402:
          cls = SeatDataPaymentError
      else:
          cls = _ERROR_TYPE_MAP.get(err_type, SeatDataError)
  ```

  The status check comes **before** the type-map lookup, so a 402 routes to `SeatDataPaymentError` regardless of the envelope's `type` (including a proper envelope that has no `type` key, where `err_type` has defaulted to `"server_error"`). The `cls: type` line is a local variable annotation (not a comment — allowed under the no-comments rule, and not evaluated at runtime, so it is Python 3.8-safe). It is **required** for mypy: without it, mypy narrows `cls` to `type[SeatDataPaymentError]` from the first branch and then rejects the wider `else`-branch value (`error: Incompatible types in assignment`). This annotation reproduces the type mypy inferred for `cls` in the original single-line form.

  Do not touch anything else in `_raise_from_response`: the `if err_type == "invalid_request" and err_code == "invalid_cursor":` branch above stays first, and the `if cls is SeatDataInvalidRequestError:` / `if cls is SeatDataRateLimitError:` kwargs blocks below stay as-is. Do not add `402` to `_RETRY_STATUS`.

- [ ] **Step 7: Run the tests, expect PASS.**

  ```bash
  pytest tests/test_transport.py -q
  ```

  Expected: `35 passed` (28 existing + 7 new).

- [ ] **Step 8: Format and type-check.**

  ```bash
  black seatdata/ tests/
  mypy seatdata/
  ```

  Expected: no reformatting; `Success: no issues found in 7 source files`.

- [ ] **Step 9: Commit.**

  ```bash
  git add seatdata/_transport.py tests/test_transport.py
  git commit -m "feat: raise SeatDataPaymentError for 402 responses SDK-wide"
  ```

---

### Task 3: `BatchSalesResult` TypedDict

**Model:** Sonnet (add TypedDict + `Any` import).

**Files:**
- Modify: `seatdata/types.py:1` (typing import), `seatdata/types.py:104` (insert new class after `EventStatsPage`, before `ErrorEnvelopeBody`)
- Test: `tests/test_types.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `class BatchSalesResult(TypedDict)` with fields `results: Dict[str, List[Dict[str, Any]]]` and `errors: Dict[str, str]`, importable from `seatdata.types` (not a top-level export, matching the other response TypedDicts). Tasks 4, 5, 6 import this exact name.

- [ ] **Step 1: Write the failing test.** In `tests/test_types.py`, make two changes.

  (a) Replace this exact block (top of file):

  ```python
  from seatdata.types import (
      AccountResponse,
  ```

  with:

  ```python
  from seatdata.types import (
      AccountResponse,
      BatchSalesResult,
  ```

  (b) Append this function at the very end of the file:

  ```python
  def test_batch_sales_result_shape():
      result: BatchSalesResult = {
          "results": {"225220": [{"price": 100.0, "quantity": 2}]},
          "errors": {"105288127": "not_found"},
      }
      assert result["results"]["225220"][0]["quantity"] == 2
      assert result["errors"]["105288127"] == "not_found"
  ```

- [ ] **Step 2: Run the test, expect FAIL.**

  ```bash
  pytest tests/test_types.py -q
  ```

  Expected: `1 error` during collection — `ImportError: cannot import name 'BatchSalesResult' from 'seatdata.types'`.

- [ ] **Step 3: Add the type.** In `seatdata/types.py`, make two changes.

  (a) Replace this exact line (line 1):

  ```python
  from typing import Dict, List, Optional
  ```

  with:

  ```python
  from typing import Any, Dict, List, Optional
  ```

  (b) Replace this exact block (end of `EventStatsPage` through the start of `ErrorEnvelopeBody`):

  ```python
      available_zones: NotRequired[List[str]]
      total_count: NotRequired[int]


  class ErrorEnvelopeBody(TypedDict):
  ```

  with:

  ```python
      available_zones: NotRequired[List[str]]
      total_count: NotRequired[int]


  class BatchSalesResult(TypedDict):
      results: Dict[str, List[Dict[str, Any]]]
      errors: Dict[str, str]


  class ErrorEnvelopeBody(TypedDict):
  ```

- [ ] **Step 4: Run the test, expect PASS.**

  ```bash
  pytest tests/test_types.py -q
  ```

  Expected: `11 passed`.

- [ ] **Step 5: Format and type-check.**

  ```bash
  black seatdata/ tests/
  mypy seatdata/
  ```

  Expected: no reformatting; `Success: no issues found in 7 source files`.

- [ ] **Step 6: Commit.**

  ```bash
  git add seatdata/types.py tests/test_types.py
  git commit -m "feat: add BatchSalesResult response type"
  ```

---

### Task 4: `seatdata/_batch.py` pure helpers

**Model:** Opus (coercion/dedup edge cases — correctness-critical).

**Files:**
- Create: `seatdata/_batch.py`
- Test: create `tests/test_batch.py`

**Interfaces:**
- Consumes: `BatchSalesResult` from Task 3 (`from .types import BatchSalesResult`).
- Produces (exact signatures relied on by Tasks 5 and 6):
  - `prepare_batch_payload(event_ids_sh: Optional[Sequence[Union[int, str]]], event_ids: Optional[Sequence[Union[int, str]]]) -> Dict[str, List[int]]`
  - `normalize_batch_response(body: Any) -> BatchSalesResult`
- Behavior contract (all client-side failures are a single exception type, `ValueError`):
  - Argument guard: each argument must be `None` or a non-`str`/non-`bytes` iterable; a bare `str`/`bytes` or a non-iterable (e.g. bare `int`) raises `ValueError` naming the argument.
  - Element coercion: accept only `int` (rejecting `bool` — checked FIRST because `isinstance(True, int)` is `True`) and `str` that `int()` parses in base 10; reject `float`/`None`/containers; wrap `int()`'s `TypeError`/`ValueError` into one uniform `ValueError` naming the offending value.
  - Coerce-then-dedup within each list, order-preserving (`list(dict.fromkeys(...))`); never across lists.
  - Both lists empty/`None` after processing -> `ValueError`. Combined unique count > 100 -> `ValueError` (dedup happens before the count check). Returned dict omits a key whose list is empty.
  - `normalize_batch_response` guards a `None` body and `None` values via `... or {}` so `results`/`errors` are always present dicts.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_batch.py` with exactly this content:

  ```python
  import pytest

  from seatdata._batch import normalize_batch_response, prepare_batch_payload


  class TestPrepareBatchPayload:
      def test_int_ids_pass_through(self):
          assert prepare_batch_payload([105294241, 105288127], None) == {
              "event_ids_sh": [105294241, 105288127]
          }

      def test_str_ids_coerced_to_int(self):
          assert prepare_batch_payload(None, ["225220", "225221"]) == {"event_ids": [225220, 225221]}

      def test_mixed_int_and_str_duplicate_collapses_to_one(self):
          assert prepare_batch_payload([225220, "225220"], None) == {"event_ids_sh": [225220]}

      def test_whitespace_and_leading_zero_strings_coerce_to_same_id(self):
          assert prepare_batch_payload([" 225220", "0225220"], None) == {"event_ids_sh": [225220]}

      def test_dedup_preserves_first_seen_order(self):
          assert prepare_batch_payload([3, 1, 3, 2, 1], None) == {"event_ids_sh": [3, 1, 2]}

      def test_dedup_is_per_list_not_cross_list(self):
          assert prepare_batch_payload([225220], [225220]) == {
              "event_ids_sh": [225220],
              "event_ids": [225220],
          }

      def test_sh_only_call_omits_event_ids_key(self):
          assert "event_ids" not in prepare_batch_payload([1], None)

      def test_event_ids_only_call_omits_sh_key(self):
          assert "event_ids_sh" not in prepare_batch_payload(None, [1])

      def test_both_none_raises(self):
          with pytest.raises(ValueError, match="Either event_ids_sh or event_ids must be provided"):
              prepare_batch_payload(None, None)

      def test_both_empty_raises(self):
          with pytest.raises(ValueError, match="Either event_ids_sh or event_ids must be provided"):
              prepare_batch_payload([], [])

      def test_bare_string_argument_raises(self):
          with pytest.raises(ValueError, match="event_ids_sh"):
              prepare_batch_payload("225220", None)

      def test_bare_bytes_argument_raises(self):
          with pytest.raises(ValueError, match="event_ids"):
              prepare_batch_payload(None, b"225220")

      def test_non_iterable_argument_raises(self):
          with pytest.raises(ValueError, match="event_ids_sh"):
              prepare_batch_payload(225220, None)

      def test_none_element_raises(self):
          with pytest.raises(ValueError, match="None"):
              prepare_batch_payload([225220, None], None)

      def test_bool_element_raises(self):
          with pytest.raises(ValueError, match="True"):
              prepare_batch_payload([True], None)

      def test_float_element_raises(self):
          with pytest.raises(ValueError, match="105294241.9"):
              prepare_batch_payload([105294241.9], None)

      def test_non_numeric_string_element_raises(self):
          with pytest.raises(ValueError, match="abc"):
              prepare_batch_payload(["abc"], None)

      def test_nested_container_element_raises(self):
          with pytest.raises(ValueError):
              prepare_batch_payload([[225220]], None)

      def test_100_unique_ids_allowed(self):
          payload = prepare_batch_payload(list(range(1, 51)), list(range(51, 101)))
          assert len(payload["event_ids_sh"]) + len(payload["event_ids"]) == 100

      def test_101_unique_ids_raises(self):
          with pytest.raises(ValueError, match="at most 100 unique event ids"):
              prepare_batch_payload(list(range(1, 52)), list(range(52, 102)))

      def test_dedup_happens_before_count_check(self):
          ids = list(range(1, 101)) + [1, 2, 3]
          assert prepare_batch_payload(ids, None) == {"event_ids_sh": list(range(1, 101))}


  class TestNormalizeBatchResponse:
      def test_full_body_passes_through(self):
          body = {"results": {"1": [{"price": 10}]}, "errors": {"2": "not_found"}}
          assert normalize_batch_response(body) == body

      def test_missing_errors_filled_with_empty_dict(self):
          assert normalize_batch_response({"results": {}}) == {"results": {}, "errors": {}}

      def test_missing_results_filled_with_empty_dict(self):
          assert normalize_batch_response({"errors": {}}) == {"results": {}, "errors": {}}

      def test_none_body_normalized(self):
          assert normalize_batch_response(None) == {"results": {}, "errors": {}}

      def test_none_values_normalized(self):
          assert normalize_batch_response({"results": None, "errors": None}) == {
              "results": {},
              "errors": {},
          }
  ```

- [ ] **Step 2: Run the tests, expect FAIL.**

  ```bash
  pytest tests/test_batch.py -q
  ```

  Expected: `1 error` during collection — `ModuleNotFoundError: No module named 'seatdata._batch'`.

- [ ] **Step 3: Write the module.** Create `seatdata/_batch.py` with exactly this content:

  ```python
  from typing import Any, Dict, List, Optional, Sequence, Union

  from .types import BatchSalesResult


  def _coerce_ids(name: str, values: Optional[Sequence[Union[int, str]]]) -> List[int]:
      if values is None:
          return []
      if isinstance(values, (str, bytes)):
          raise ValueError(f"{name} must be an iterable of event ids, not {type(values).__name__}")
      try:
          iterator = iter(values)
      except TypeError:
          raise ValueError(
              f"{name} must be an iterable of event ids, not {type(values).__name__}"
          ) from None
      coerced: List[int] = []
      for value in iterator:
          if isinstance(value, bool):
              raise ValueError(f"Invalid event id in {name}: {value!r}")
          if isinstance(value, int):
              coerced.append(value)
          elif isinstance(value, str):
              try:
                  coerced.append(int(value))
              except (TypeError, ValueError):
                  raise ValueError(f"Invalid event id in {name}: {value!r}") from None
          else:
              raise ValueError(f"Invalid event id in {name}: {value!r}")
      return list(dict.fromkeys(coerced))


  def prepare_batch_payload(
      event_ids_sh: Optional[Sequence[Union[int, str]]],
      event_ids: Optional[Sequence[Union[int, str]]],
  ) -> Dict[str, List[int]]:
      sh_ids = _coerce_ids("event_ids_sh", event_ids_sh)
      sd_ids = _coerce_ids("event_ids", event_ids)
      if not sh_ids and not sd_ids:
          raise ValueError("Either event_ids_sh or event_ids must be provided")
      total = len(sh_ids) + len(sd_ids)
      if total > 100:
          raise ValueError(f"A batch supports at most 100 unique event ids, got {total}")
      payload: Dict[str, List[int]] = {}
      if sh_ids:
          payload["event_ids_sh"] = sh_ids
      if sd_ids:
          payload["event_ids"] = sd_ids
      return payload


  def normalize_batch_response(body: Any) -> BatchSalesResult:
      data = body or {}
      return {
          "results": data.get("results") or {},
          "errors": data.get("errors") or {},
      }
  ```

- [ ] **Step 4: Run the tests, expect PASS.**

  ```bash
  pytest tests/test_batch.py -q
  ```

  Expected: `26 passed`.

- [ ] **Step 5: Format and type-check.**

  ```bash
  black seatdata/ tests/
  mypy seatdata/
  ```

  Expected: no reformatting; `Success: no issues found in 8 source files` (the count grows to 8 with `_batch.py`).

- [ ] **Step 6: Commit.**

  ```bash
  git add seatdata/_batch.py tests/test_batch.py
  git commit -m "feat: add batch payload validation and response normalization helpers"
  ```

---

### Task 5: Sync `SeatDataClient.get_sales_data_batch()`

**Model:** Sonnet (thin method + respx tests from exact provided code).

**Files:**
- Modify: `seatdata/client.py:2` (typing import), `:4` (add `._batch` import above `._transport`), `:7-14` (`.types` import), `:57-59` (insert method between `get_sales_data` and `get_listings`)
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `prepare_batch_payload`, `normalize_batch_response` (Task 4), `BatchSalesResult` (Task 3), `SeatDataPaymentError` (Tasks 1-2, in tests), `_Transport.request_json` (existing).
- Produces: `SeatDataClient.get_sales_data_batch(event_ids_sh: Optional[Sequence[Union[int, str]]] = None, event_ids: Optional[Sequence[Union[int, str]]] = None) -> BatchSalesResult`, calling `POST /api/v0.3/salesdata/batch` with `retry_safe=True` (transport default — do NOT pass `retry_safe=False`).

- [ ] **Step 1: Write the failing tests.** In `tests/test_client.py`, make two changes.

  (a) Replace this exact block (top-of-file import):

  ```python
  from seatdata import (
      SeatDataClient,
      SeatDataException,
  ```

  with:

  ```python
  from seatdata import (
      SeatDataClient,
      SeatDataException,
      SeatDataPaymentError,
  ```

  (b) Append these six methods at the end of class `TestSeatDataClient` (end of file, after `test_event_request_status_alias_emits_deprecation`, indented as class members):

  ```python
      @respx.mock
      def test_get_sales_data_batch_success(self):
          payload = {
              "results": {"105294241": [{"price": 100}], "225220": [{"price": 55}]},
              "errors": {"105288127": "not_found"},
          }
          route = respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json=payload)
          )
          client = SeatDataClient(api_key="a" * 64)
          result = client.get_sales_data_batch(
              event_ids_sh=[105294241, 105288127], event_ids=[225220]
          )
          assert result == payload
          assert route.called

      @respx.mock
      def test_get_sales_data_batch_per_event_payment_required_does_not_raise(self):
          payload = {
              "results": {"105294241": [{"price": 100}]},
              "errors": {"105288127": "payment_required"},
          }
          respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json=payload)
          )
          client = SeatDataClient(api_key="a" * 64)
          result = client.get_sales_data_batch(event_ids_sh=[105294241, 105288127])
          assert result["errors"]["105288127"] == "payment_required"

      @respx.mock
      def test_get_sales_data_batch_missing_errors_normalized_to_empty_dict(self):
          respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json={"results": {"225220": []}})
          )
          client = SeatDataClient(api_key="a" * 64)
          result = client.get_sales_data_batch(event_ids=[225220])
          assert result["results"] == {"225220": []}
          assert result["errors"] == {}

      @respx.mock
      def test_get_sales_data_batch_sends_deduped_int_body(self):
          route = respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json={"results": {}, "errors": {}})
          )
          client = SeatDataClient(api_key="a" * 64)
          client.get_sales_data_batch(
              event_ids_sh=[105294241, "105294241", 105288127], event_ids=["225220"]
          )
          body = json.loads(route.calls.last.request.content)
          assert body == {"event_ids_sh": [105294241, 105288127], "event_ids": [225220]}

      @respx.mock
      def test_get_sales_data_batch_402_raises_payment_error(self):
          respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(
                  402,
                  json={
                      "error": {
                          "type": "payment_required",
                          "code": "payment_required",
                          "message": "No event in the batch could be served",
                      }
                  },
              )
          )
          client = SeatDataClient(api_key="a" * 64)
          with pytest.raises(SeatDataPaymentError):
              client.get_sales_data_batch(event_ids_sh=[105294241])

      @respx.mock
      def test_get_sales_data_batch_validation_error_makes_no_http_call(self):
          route = respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json={"results": {}, "errors": {}})
          )
          client = SeatDataClient(api_key="a" * 64)
          with pytest.raises(ValueError):
              client.get_sales_data_batch()
          with pytest.raises(ValueError):
              client.get_sales_data_batch(event_ids_sh=list(range(101)))
          with pytest.raises(ValueError):
              client.get_sales_data_batch(event_ids_sh="105294241")
          assert not route.called
  ```

- [ ] **Step 2: Run the tests, expect FAIL.**

  ```bash
  pytest tests/test_client.py -k "get_sales_data_batch" -q
  ```

  Expected: `6 failed, 32 deselected` — each with `AttributeError: 'SeatDataClient' object has no attribute 'get_sales_data_batch'`.

- [ ] **Step 3: Add the imports.** In `seatdata/client.py`, make two changes.

  (a) Replace this exact block (top of file):

  ```python
  from typing import Any, Dict, List, Optional, cast

  from ._transport import _Transport
  ```

  with:

  ```python
  from typing import Any, Dict, List, Optional, Sequence, Union, cast

  from ._batch import normalize_batch_response, prepare_batch_payload
  from ._transport import _Transport
  ```

  (b) Replace this exact block:

  ```python
  from .types import (
      AccountResponse,
      EventSearchItem,
  ```

  with:

  ```python
  from .types import (
      AccountResponse,
      BatchSalesResult,
      EventSearchItem,
  ```

- [ ] **Step 4: Add the method.** In `seatdata/client.py`, replace this exact block (the tail of `get_sales_data` and the head of `get_listings`):

  ```python
          return cast(
              List[Dict[str, Any]],
              self._transport.request_json("GET", "/api/v0.3/salesdata/get", params=params),
          )

      def get_listings(
  ```

  with:

  ```python
          return cast(
              List[Dict[str, Any]],
              self._transport.request_json("GET", "/api/v0.3/salesdata/get", params=params),
          )

      def get_sales_data_batch(
          self,
          event_ids_sh: Optional[Sequence[Union[int, str]]] = None,
          event_ids: Optional[Sequence[Union[int, str]]] = None,
      ) -> BatchSalesResult:
          """Fetch sales data for up to 100 events in one request.

          Transient failures (429/5xx, timeouts) are retried by default. The API
          has no idempotency key, so a retried timeout may re-bill up to one
          salesdata pull per event in the batch. Construct the client with
          max_retries=0 to opt out of retries.
          """
          payload = prepare_batch_payload(event_ids_sh, event_ids)
          response = self._transport.request_json("POST", "/api/v0.3/salesdata/batch", json=payload)
          return normalize_batch_response(response)

      def get_listings(
  ```

- [ ] **Step 5: Run the tests, expect PASS.**

  ```bash
  pytest tests/test_client.py -k "get_sales_data_batch" -q
  pytest tests/test_client.py -q
  ```

  Expected: `6 passed, 32 deselected`, then `38 passed`.

- [ ] **Step 6: Format and type-check.**

  ```bash
  black seatdata/ tests/
  mypy seatdata/
  ```

  Expected: no reformatting; `Success: no issues found in 8 source files`.

- [ ] **Step 7: Commit.**

  ```bash
  git add seatdata/client.py tests/test_client.py
  git commit -m "feat: add get_sales_data_batch() to SeatDataClient"
  ```

---

### Task 6: Async `AsyncSeatDataClient.get_sales_data_batch()`

**Model:** Sonnet (async parallel of Task 5 from exact provided code).

**Files:**
- Modify: `seatdata/async_client.py:2` (typing import), `:4` (add `._batch` import above `._transport`), `:7-14` (`.types` import), `:218-220` (insert method between `get_sales_data` and `get_listings`)
- Test: `tests/test_async_client.py`

**Interfaces:**
- Consumes: same as Task 5, plus `_Transport.arequest_json` (existing). The async body MUST `await self._transport.arequest_json(...)` — not `request_json`.
- Produces: `async def AsyncSeatDataClient.get_sales_data_batch(event_ids_sh: Optional[Sequence[Union[int, str]]] = None, event_ids: Optional[Sequence[Union[int, str]]] = None) -> BatchSalesResult` — identical signature, semantics, and docstring to the sync method.

- [ ] **Step 1: Write the failing tests.** In `tests/test_async_client.py`, make two changes.

  (a) Replace this exact block (the entire top-of-file import section):

  ```python
  import httpx
  import pytest
  import respx

  from seatdata import AsyncSeatDataClient
  ```

  with:

  ```python
  import json

  import httpx
  import pytest
  import respx

  from seatdata import AsyncSeatDataClient, SeatDataPaymentError
  ```

  (b) Append these six methods at the end of class `TestAsyncSeatDataClient` (end of file, after `test_aclose_closes_underlying_async_client`, indented as class members):

  ```python
      @pytest.mark.asyncio
      @respx.mock
      async def test_get_sales_data_batch_success(self):
          payload = {
              "results": {"105294241": [{"price": 100}], "225220": [{"price": 55}]},
              "errors": {"105288127": "not_found"},
          }
          route = respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json=payload)
          )
          async with AsyncSeatDataClient(api_key="a" * 64) as client:
              result = await client.get_sales_data_batch(
                  event_ids_sh=[105294241, 105288127], event_ids=[225220]
              )
              assert result == payload
              assert route.called

      @pytest.mark.asyncio
      @respx.mock
      async def test_get_sales_data_batch_per_event_payment_required_does_not_raise(self):
          payload = {
              "results": {"105294241": [{"price": 100}]},
              "errors": {"105288127": "payment_required"},
          }
          respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json=payload)
          )
          async with AsyncSeatDataClient(api_key="a" * 64) as client:
              result = await client.get_sales_data_batch(event_ids_sh=[105294241, 105288127])
              assert result["errors"]["105288127"] == "payment_required"

      @pytest.mark.asyncio
      @respx.mock
      async def test_get_sales_data_batch_missing_errors_normalized_to_empty_dict(self):
          respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json={"results": {"225220": []}})
          )
          async with AsyncSeatDataClient(api_key="a" * 64) as client:
              result = await client.get_sales_data_batch(event_ids=[225220])
              assert result["results"] == {"225220": []}
              assert result["errors"] == {}

      @pytest.mark.asyncio
      @respx.mock
      async def test_get_sales_data_batch_sends_deduped_int_body(self):
          route = respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json={"results": {}, "errors": {}})
          )
          async with AsyncSeatDataClient(api_key="a" * 64) as client:
              await client.get_sales_data_batch(
                  event_ids_sh=[105294241, "105294241", 105288127], event_ids=["225220"]
              )
          body = json.loads(route.calls.last.request.content)
          assert body == {"event_ids_sh": [105294241, 105288127], "event_ids": [225220]}

      @pytest.mark.asyncio
      @respx.mock
      async def test_get_sales_data_batch_402_raises_payment_error(self):
          respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(
                  402,
                  json={
                      "error": {
                          "type": "payment_required",
                          "code": "payment_required",
                          "message": "No event in the batch could be served",
                      }
                  },
              )
          )
          async with AsyncSeatDataClient(api_key="a" * 64) as client:
              with pytest.raises(SeatDataPaymentError):
                  await client.get_sales_data_batch(event_ids_sh=[105294241])

      @pytest.mark.asyncio
      @respx.mock
      async def test_get_sales_data_batch_validation_error_makes_no_http_call(self):
          route = respx.post("https://seatdata.io/api/v0.3/salesdata/batch").mock(
              return_value=httpx.Response(200, json={"results": {}, "errors": {}})
          )
          async with AsyncSeatDataClient(api_key="a" * 64) as client:
              with pytest.raises(ValueError):
                  await client.get_sales_data_batch()
              with pytest.raises(ValueError):
                  await client.get_sales_data_batch(event_ids_sh=list(range(101)))
              with pytest.raises(ValueError):
                  await client.get_sales_data_batch(event_ids_sh="105294241")
          assert not route.called
  ```

- [ ] **Step 2: Run the tests, expect FAIL.**

  ```bash
  pytest tests/test_async_client.py -k "get_sales_data_batch" -q
  ```

  Expected: `6 failed, 13 deselected` — each with `AttributeError: 'AsyncSeatDataClient' object has no attribute 'get_sales_data_batch'`.

- [ ] **Step 3: Add the imports.** In `seatdata/async_client.py`, make two changes.

  (a) Replace this exact block (top of file):

  ```python
  from typing import Any, Dict, List, Optional, cast

  from ._transport import _Transport
  ```

  with:

  ```python
  from typing import Any, Dict, List, Optional, Sequence, Union, cast

  from ._batch import normalize_batch_response, prepare_batch_payload
  from ._transport import _Transport
  ```

  (b) Replace this exact block:

  ```python
  from .types import (
      AccountResponse,
      EventSearchItem,
  ```

  with:

  ```python
  from .types import (
      AccountResponse,
      BatchSalesResult,
      EventSearchItem,
  ```

- [ ] **Step 4: Add the method.** In `seatdata/async_client.py`, replace this exact block (the tail of the async `get_sales_data` and the head of the async `get_listings`):

  ```python
          return cast(
              List[Dict[str, Any]],
              await self._transport.arequest_json("GET", "/api/v0.3/salesdata/get", params=params),
          )

      async def get_listings(
  ```

  with:

  ```python
          return cast(
              List[Dict[str, Any]],
              await self._transport.arequest_json("GET", "/api/v0.3/salesdata/get", params=params),
          )

      async def get_sales_data_batch(
          self,
          event_ids_sh: Optional[Sequence[Union[int, str]]] = None,
          event_ids: Optional[Sequence[Union[int, str]]] = None,
      ) -> BatchSalesResult:
          """Fetch sales data for up to 100 events in one request.

          Transient failures (429/5xx, timeouts) are retried by default. The API
          has no idempotency key, so a retried timeout may re-bill up to one
          salesdata pull per event in the batch. Construct the client with
          max_retries=0 to opt out of retries.
          """
          payload = prepare_batch_payload(event_ids_sh, event_ids)
          response = await self._transport.arequest_json(
              "POST", "/api/v0.3/salesdata/batch", json=payload
          )
          return normalize_batch_response(response)

      async def get_listings(
  ```

- [ ] **Step 5: Run the tests, expect PASS.**

  ```bash
  pytest tests/test_async_client.py -q
  ```

  Expected: `19 passed` (13 existing + 6 new).

- [ ] **Step 6: Format and type-check.**

  ```bash
  black seatdata/ tests/
  mypy seatdata/
  ```

  Expected: no reformatting; `Success: no issues found in 8 source files`.

- [ ] **Step 7: Commit.**

  ```bash
  git add seatdata/async_client.py tests/test_async_client.py
  git commit -m "feat: add get_sales_data_batch() to AsyncSeatDataClient"
  ```

---

### Task 7: Deprecation removal target v1.1 -> v2.0

**Model:** Sonnet (three string edits + pinning test).

**Files:**
- Modify: `seatdata/client.py:296-303, 315-322, 340-345` (pre-Task-5 numbering; after Task 5 these sit ~19 lines lower — use the exact string anchors below)
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: the three sync `DeprecationWarning` messages say "removed in v2.0" instead of "removed in v1.1". The async client's warnings name no version (verified in Step 5) and are not changed.

- [ ] **Step 1: Write the failing test.** Append this method at the end of class `TestSeatDataClient` in `tests/test_client.py` (end of file, after `test_get_sales_data_batch_validation_error_makes_no_http_call`, indented as a class member):

  ```python
      @respx.mock
      def test_deprecation_warnings_name_v2_0(self):
          import warnings

          respx.post("https://seatdata.io/api/v0.4/events/event-request-add").mock(
              return_value=httpx.Response(202, json={"job_id": "x"})
          )
          respx.get("https://seatdata.io/api/v0.4/events/event-request-status/x/").mock(
              return_value=httpx.Response(200, json={"job_id": "x"})
          )
          respx.post("https://seatdata.io/api/v0.3.1/events/search").mock(
              return_value=httpx.Response(200, json={"result_total": 0, "items": []})
          )
          client = SeatDataClient(api_key="a" * 64)
          with warnings.catch_warnings(record=True) as caught:
              warnings.simplefilter("always")
              client.event_request_add(search_query="X")
              client.event_request_status(job_id="x")
              client.search_events_legacy(event_name="X")
          messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
          assert sum("removed in v2.0" in m for m in messages) == 3
          assert not any("removed in v1.1" in m for m in messages)
  ```

- [ ] **Step 2: Run the test, expect FAIL.**

  ```bash
  pytest tests/test_client.py -k "v2_0" -q
  ```

  Expected: `1 failed, 38 deselected` — `assert 0 == 3` on the `sum("removed in v2.0" ...)` line.

- [ ] **Step 3: Update the three warning strings.** In `seatdata/client.py`, make three replacements.

  (a) Replace this exact block:

  ```python
              "event_request_add() is deprecated. Use create_event_request() instead. "
              "This alias will be removed in v1.1.",
  ```

  with:

  ```python
              "event_request_add() is deprecated. Use create_event_request() instead. "
              "This alias will be removed in v2.0.",
  ```

  (b) Replace this exact block:

  ```python
              "event_request_status() is deprecated. Use get_event_request_status() instead. "
              "This alias will be removed in v1.1.",
  ```

  with:

  ```python
              "event_request_status() is deprecated. Use get_event_request_status() instead. "
              "This alias will be removed in v2.0.",
  ```

  (c) Replace this exact block:

  ```python
              "search_events_legacy() calls the deprecated v0.3.1 POST endpoint. "
              "Use search_events() (v1 GET) instead. This method will be removed in v1.1.",
  ```

  with:

  ```python
              "search_events_legacy() calls the deprecated v0.3.1 POST endpoint. "
              "Use search_events() (v1 GET) instead. This method will be removed in v2.0.",
  ```

- [ ] **Step 4: Run the tests, expect PASS.**

  ```bash
  pytest tests/test_client.py -k "v2_0" -q
  pytest tests/test_client.py -q
  ```

  Expected: `1 passed, 38 deselected`, then `39 passed`.

- [ ] **Step 5: Confirm the async warnings need no change.**

  ```bash
  grep -n "removed in v" seatdata/async_client.py
  ```

  Expected: no output (the async deprecation messages name no version). Do not edit `seatdata/async_client.py`.

- [ ] **Step 6: Format check and commit.**

  ```bash
  black seatdata/ tests/
  git add seatdata/client.py tests/test_client.py
  git commit -m "fix: defer deprecated-API removal target from v1.1 to v2.0"
  ```

---

### Task 8: Version bump to 1.1.0

**Model:** Sonnet (two version-string edits).

**Files:**
- Modify: `pyproject.toml:7`, `seatdata/__init__.py:22` (post-Task-1 numbering; anchor by exact strings)

**Interfaces:**
- Produces: `seatdata.__version__ == "1.1.0"`; package metadata `version = "1.1.0"`.

- [ ] **Step 1: Bump pyproject.** In `pyproject.toml`, replace this exact line:

  ```toml
  version = "1.0.0"
  ```

  with:

  ```toml
  version = "1.1.0"
  ```

- [ ] **Step 2: Bump the package dunder.** In `seatdata/__init__.py`, replace this exact line:

  ```python
  __version__ = "1.0.0"
  ```

  with:

  ```python
  __version__ = "1.1.0"
  ```

- [ ] **Step 3: Verify.**

  ```bash
  python -c "import seatdata; print(seatdata.__version__)"
  pytest -m "not integration" -q
  ```

  Expected: `1.1.0`, then `166 passed, 5 deselected`. (Note: the `User-Agent` header derives its version from installed package metadata via `importlib.metadata`, so it reports 1.1.0 only after `pip install -e .` is re-run; no test depends on the exact version segment.)

- [ ] **Step 4: Commit.**

  ```bash
  git add pyproject.toml seatdata/__init__.py
  git commit -m "build: bump version to 1.1.0"
  ```

---

### Task 9: Documentation (CHANGELOG, README, CLAUDE.md)

**Model:** Sonnet (docs from exact provided text).

**Files:**
- Modify: `CHANGELOG.md:6-8` (insert new entry above `## [1.0.0]`), `README.md:64-67` (insert new section between the Async quick start and "Migrating"), `CLAUDE.md:50, 65, 98` (three additions)
- **Commit only `CHANGELOG.md` and `README.md`. `CLAUDE.md` is untracked in git — edit it on disk but do NOT `git add` it.**

**Interfaces:**
- Consumes: names and behavior from Tasks 1-8 exactly as spelled there (`get_sales_data_batch`, `SeatDataPaymentError`, `BatchSalesResult`).

- [ ] **Step 1: Add the CHANGELOG entry.** In `CHANGELOG.md`, replace this exact block:

  ```markdown
  and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

  ## [1.0.0] - 2026-04-30
  ```

  with:

  ```markdown
  and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

  ## [1.1.0] - 2026-07-09

  ### Added
  - `get_sales_data_batch()` on `SeatDataClient` and `AsyncSeatDataClient` - fetches sales data for up to 100 events in one `POST /v0.3/salesdata/batch` request. Accepts `event_ids_sh` (StubHub ids) and/or `event_ids` (SeatData ids) as sequences of `int` or `str`; validates, coerces, and dedupes client-side before any HTTP call.
  - `SeatDataPaymentError` exception (subclass of `SeatDataError`) for HTTP `402 Payment Required` responses, exported from the top-level package.
  - `seatdata.types.BatchSalesResult` typed response shape (`results` and `errors` maps keyed by canonical decimal-string event id).

  ### Fixed
  - `402` responses now consistently raise `SeatDataPaymentError` SDK-wide (previously surfaced as `SeatDataServerError` or the base `SeatDataError` depending on response body). This also covers `get_sales_data()` and `get_listings()` under pay-as-you-go billing.

  ### Deprecated
  - Removal of `search_events_legacy()`, `event_request_add()`, and `event_request_status()` is deferred from v1.1 to v2.0 (removing public API in a minor release would violate semver). Their `DeprecationWarning` messages now say v2.0. The historical `[1.0.0]` entry below is left as written.

  ## [1.0.0] - 2026-04-30
  ```

- [ ] **Step 2: Add the README batch section.** In `README.md`, replace this exact block (the tail of the Async quick-start code block and the next heading):

  ````markdown
  asyncio.run(main())
  ```

  ## Migrating from v0.3.x
  ````

  with:

  ````markdown
  asyncio.run(main())
  ```

  ### Batch sales data

  Fetch sales for up to 100 events in one request (`POST /v0.3/salesdata/batch`).
  Billing matches the single-event endpoint: one pull per event that returns
  sales; events with no sales are free.

  ```python
  from seatdata import SeatDataClient, SeatDataPaymentError

  client = SeatDataClient(api_key="your_64_char_api_key")

  event_ids_sh = [105294241, 105288127]
  event_ids = [225220]

  try:
      resp = client.get_sales_data_batch(event_ids_sh=event_ids_sh, event_ids=event_ids)
  except SeatDataPaymentError as e:
      print(f"Payment required - no event in the batch could be served: {e.message}")
      raise

  for event_id in event_ids_sh + event_ids:
      sales = resp["results"].get(str(int(event_id)), [])
      print(f"{event_id}: {len(sales)} sales records")

  for event_id, reason in resp["errors"].items():
      print(f"{event_id}: {reason}")
  ```

  The async client is identical, just awaited:

  ```python
  async with AsyncSeatDataClient(api_key="your_64_char_api_key") as client:
      resp = await client.get_sales_data_batch(event_ids_sh=[105294241], event_ids=[225220])
  ```

  `results` and `errors` are keyed by the canonical decimal string of each id
  (`str(int(event_id))`). An event with no sales is free and may be absent from
  `results`, so use `.get(str(int(event_id)), [])`. Per-event `errors` values
  are `"not_found"` or `"payment_required"`; a per-event `payment_required`
  arrives in a normal `200` response and does not raise.

  > **Billing note:** transient failures (429/5xx/timeouts) are retried by
  > default. The API has no idempotency key, so a retried timeout may re-bill
  > up to one salesdata pull per event in the batch. Construct the client with
  > `max_retries=0` to opt out of retries.

  ## Migrating from v0.3.x
  ````

- [ ] **Step 3: Update CLAUDE.md (three additions; do not change anything else in the file, including the pre-existing stale "api-key" auth note, which the spec keeps out of scope).**

  (a) Replace this exact block (Response Handling):

  ```markdown
  - `get_sales_data()` returns a list of sales records
  - `get_listings()` returns a dict with `listings` array
  ```

  with:

  ```markdown
  - `get_sales_data()` returns a list of sales records
  - `get_sales_data_batch()` returns a `BatchSalesResult` dict: `results` and `errors` maps keyed by decimal-string event id
  - `get_listings()` returns a dict with `listings` array
  ```

  (b) Replace this exact block (Error Handling):

  ```markdown
  - `ServiceUnavailableError` for 503 responses
  - `SeatDataException` for other API errors
  ```

  with:

  ```markdown
  - `ServiceUnavailableError` for 503 responses
  - `SeatDataPaymentError` for 402 responses (payment required / billing balance exhausted)
  - `SeatDataException` for other API errors
  ```

  (c) Replace this exact block (end of file, endpoint 4):

  ```markdown
  4. **GET /v0.5/daily-csv/download**
     - Returns: CSV file content as text
     - Rate limit: 5/hour
     - Parameters: date (optional, YYYYMMDD format, defaults to latest, limited to last 30 days)
     - Requires: Active API subscription AND Daily Event CSV subscription
  ```

  with:

  ```markdown
  4. **GET /v0.5/daily-csv/download**
     - Returns: CSV file content as text
     - Rate limit: 5/hour
     - Parameters: date (optional, YYYYMMDD format, defaults to latest, limited to last 30 days)
     - Requires: Active API subscription AND Daily Event CSV subscription

  5. **POST /v0.3/salesdata/batch**
     - Returns: `{results: {"<event_id>": [sales...]}, errors: {"<event_id>": "not_found" | "payment_required"}}`
     - Rate limit: 500/60s (dedicated `salesdata_batch` bucket, one count per call)
     - Parameters: JSON body with `event_ids_sh` and/or `event_ids` (max 100 unique ids after dedup)
     - Billing: one pull per event that returns sales; events with no sales are free
  ```

- [ ] **Step 4: Verify nothing broke and commit (without CLAUDE.md).**

  ```bash
  pytest -m "not integration" -q
  git add CHANGELOG.md README.md
  git commit -m "docs: add 1.1.0 changelog entry and batch usage docs"
  git status --short
  ```

  Expected: `166 passed, 5 deselected`; after commit, `git status` still shows `?? CLAUDE.md` (modified on disk, deliberately left untracked) plus the other pre-existing untracked example files.

---

### Task 10: Example script + final gate

**Model:** Sonnet (example script + run black / mypy / full suite).

**Files:**
- Create: `examples/batch_sales_data.py`

**Interfaces:**
- Consumes: `SeatDataClient.get_sales_data_batch` (Task 5), `SeatDataPaymentError` (Task 1).

- [ ] **Step 1: Write the example.** Create `examples/batch_sales_data.py` with exactly this content:

  ```python
  import os
  from seatdata import SeatDataClient, SeatDataPaymentError


  def main():
      api_key = os.environ.get("SEATDATA_API_KEY")
      if not api_key:
          print("Please set SEATDATA_API_KEY environment variable")
          print("You can get an API key from support@seatdata.io")
          return

      base_url = os.environ.get("SEATDATA_BASE_URL", "https://seatdata.io").rstrip("/")
      print(f"Base URL: {base_url}")

      event_ids_sh = [105294241, "105288127"]
      event_ids = [225220]

      with SeatDataClient(api_key=api_key, base_url=base_url) as client:
          print("\n=== Fetching Batch Sales Data ===")
          try:
              resp = client.get_sales_data_batch(event_ids_sh=event_ids_sh, event_ids=event_ids)
          except SeatDataPaymentError as e:
              print(f"Payment required - no event in the batch could be served: {e.message}")
              return
          except Exception as e:
              print(f"Error fetching batch sales data: {e}")
              return

          print("\n=== Results ===")
          for event_id in list(event_ids_sh) + list(event_ids):
              sales = resp["results"].get(str(int(event_id)), [])
              print(f"Event {event_id}: {len(sales)} sales records")

          print("\n=== Per-event Errors ===")
          if not resp["errors"]:
              print("None")
          for event_id, reason in resp["errors"].items():
              print(f"Event {event_id}: {reason}")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 2: Syntax-check the example.**

  ```bash
  python -m py_compile examples/batch_sales_data.py && echo OK
  ```

  Expected: `OK`. (Running it live requires a real `SEATDATA_API_KEY` and bills pulls; do not run it as part of this plan.)

- [ ] **Step 3: Final gate — full suite, formatter, type checker.**

  ```bash
  black seatdata/ tests/ examples/
  mypy seatdata/
  pytest -m "not integration" -q
  ```

  Expected: black reports all files unchanged; `Success: no issues found in 8 source files`; `166 passed, 5 deselected`.

- [ ] **Step 4: Commit.**

  ```bash
  git add examples/batch_sales_data.py
  git commit -m "docs: add batch sales data example"
  ```

---

## Spec coverage

| Spec section | Task(s) |
|---|---|
| Context / Goals / Non-goals (no auto-chunking, untyped rows, stale auth note untouched) | Honored throughout; Task 4 (>100 -> `ValueError`), Task 3 (rows stay `Dict[str, Any]`), Task 9 Step 3 (auth note untouched) |
| Public API (`get_sales_data_batch` signature, param names, retry-safe default, docstring re-bill note) | Tasks 5, 6 |
| Return value (str keys, normalization guarantee, absent-vs-empty caveat) | Tasks 4, 5, 6 (normalization + tests), Task 9 (README `.get(str(int(id)), [])` guidance) |
| New type `BatchSalesResult` (+ `Any` import, `seatdata.types` only) | Task 3 |
| New exception `SeatDataPaymentError` (+ top-level export, no legacy alias) | Task 1 |
| Two payment surfaces must not be conflated (per-event `payment_required` in 200 vs top-level 402) | Tasks 5, 6 (`per_event_payment_required_does_not_raise` tests), Task 9 (README prose) |
| Transport wiring items 1-4 (import, `_ERROR_TYPE_MAP`, fallback map, status-first backstop) | Task 2 Steps 3-6 (backstop checks status before the type map; pinned for typeless envelope by `test_402_envelope_without_type_raises_payment_error`) |
| Transport wiring item 5 (402 not in `_RETRY_STATUS`) | Task 2 (no code change needed; pinned by `test_402_is_not_retried` sync + async) |
| Validation / payload helper rules (arg guard, strict coercion, bool-first, per-list dedup, dedup-before-count, empty, >100, omit empties) | Task 4 |
| `normalize_batch_response` companion | Task 4 (with `or {}` None-value guards; see Risks note 2) |
| Versioning & deprecation (1.1.0 bump; three sync warnings -> v2.0; async warnings unchanged; 1.0.0 changelog entry left intact) | Tasks 7, 8, 9 |
| Files changed table | Tasks 1-10 (one-to-one; `examples/batch_sales_data.py` is distinct from the existing `batch_event_requests.py`) |
| Implementation notes (`Sequence`/`Union` imports, `._batch` imports, async must `await arequest_json`, gzip/headers automatic) | Tasks 5, 6 |
| Testing strategy (test_batch, test_client, test_async_client, test_transport incl. both retry loops, test_exceptions) | Tasks 1, 2, 4, 5, 6 |
| Documentation & examples (README, CLAUDE.md, CHANGELOG wording, example content) | Tasks 9, 10 |
| Decisions log 1-4 | Decision 1 -> Task 3; Decision 2 -> Tasks 1-2; Decision 3 -> Task 4; Decision 4 -> Tasks 7-8 |

## Risks and spec-vs-code notes

1. **Spec-internal inconsistency, resolved:** the spec's "Public API" sketch shows `cast(BatchSalesResult, self._transport.request_json(...))` with no normalization, but its "Return value" section mandates that the method normalizes via `normalize_batch_response`. This plan implements the normalizing form (Tasks 5-6); `cast` is unnecessary because `normalize_batch_response` already returns `BatchSalesResult` (mypy verified clean).
2. **Normalization stricter than the spec sketch:** the spec sketch uses `.get("results", {})`, which does not guard a present-but-`None` value. The plan uses `data.get("results") or {}` (and `body or {}`), guarding both `None` body and `None` values, matching the testing requirements. Behavior for all spec-listed cases is identical.
3. **Typeless-envelope 402 edge — RESOLVED.** An earlier draft of the backstop (`_ERROR_TYPE_MAP.get(err_type)` then a `None` check) mis-routed a 402 whose body is a proper envelope dict lacking a `"type"` key: `err_type` defaults to `"server_error"`, which is a mapped type, so the backstop never fired and it raised `SeatDataServerError`. The spec (and Task 2 Step 6) now route **status-first** — `if response.status_code == 402: cls = SeatDataPaymentError` runs before the type-map lookup — so every 402 raises `SeatDataPaymentError` regardless of `type`, including the typeless envelope. `test_402_envelope_without_type_raises_payment_error` pins this. No accepted edge remains.
4. **Docstring vs no-comments preference:** the spec requires the retry re-bill note in the method docstring; the codebase otherwise has no docstrings. The docstring (not a comment) is included on the two new methods only, per the spec mandate.
5. **`CLAUDE.md` is untracked in git** (`?? CLAUDE.md` in status). Task 9 edits it on disk but excludes it from the commit to preserve the repo's current tracking choices. Its stale "api-key header" auth note is out of scope per the spec.
6. **Test invocation determinism:** plain `pytest` would also collect integration tests (they self-skip without `SEATDATA_API_KEY`, but would run live if it is set); all full-suite commands here use `-m "not integration"`.
7. **User-Agent version lag:** `_transport._sdk_version()` reads installed package metadata, so the header shows 1.1.0 only after re-running `pip install -e .`; no test asserts the exact version segment.
8. **`examples/README.md` is not updated** — the spec's files-changed table intentionally omits it.
9. **`cls: type` annotation added to the status-first backstop.** The design spec's snippet for the status-first backstop shows the bare `if/else` with no annotation. That exact form does not type-check (`mypy seatdata/` -> `Incompatible types in assignment ... [assignment]`), because mypy narrows `cls` to `type[SeatDataPaymentError]` from the 402 branch and rejects the wider `else`-branch value. Task 2 Step 6 adds a single `cls: type` local-variable annotation directly above the `if/else` to widen the declared type (this reproduces the type mypy inferred for the original single-line form; local annotations are not evaluated at runtime, so it is Python 3.8-safe). Semantics are unchanged and identical to the spec snippet; this is the minimal edit needed to satisfy the mypy-clean global constraint.
10. All code in this plan was pre-validated against the real repository state, including this status-first revision: final suite `166 passed, 5 deselected`; Task 2 red `7 failed, 28 deselected` and green `35 passed` (transport file); `mypy seatdata/` clean (8 files); `black --check` clean (22 files); and every task's red state produced exactly the failure quoted in its "expect FAIL" step (the typeless-envelope test fails red with `SeatDataServerError: no balance`).
