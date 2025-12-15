# Technical Specification

# 0. Agent Action Plan

## 0.1 Executive Summary

Based on the bug description, the Blitzy platform understands that the bug is a **global variable state corruption issue** in multi-page table extraction. When tables are parsed from multiple PDF pages, the content from earlier pages is incorrectly replaced with content from the last processed page.

#### Technical Failure Description

The bug manifests when users iterate through a multi-page PDF document, collecting `Table` objects from `page.find_tables()`, and later call `table.extract()` or `table.to_markdown()` on those collected tables. The extracted content incorrectly returns data from the **last processed page** instead of the page where each table was originally detected.

#### Root Cause Summary

Module-level global variables (`CHARS`, `EDGES`, `TEXTPAGE`) in `src/table.py` are overwritten each time `find_tables()` is called. Table objects reference these globals directly rather than storing their own copy of the character data.

#### Reproduction Steps

```python
import fitz
doc = fitz.open("multipage.pdf")
tables = []
for page in doc:
    tables.extend(page.find_tables().tables)
# BUG: tables[0].extract() returns last page's content
```

#### Error Type Classification

- **Category**: State Management / Global Variable Corruption
- **Severity**: High - causes silent data corruption
- **Impact**: All multi-page table extraction workflows affected

#### Resolution Approach

Per user instructions, the bug has been documented with detailed TODO comments at all affected locations in `src/table.py` without modifying any working code. A comprehensive unit test suite has been created to demonstrate and track the bug behavior.


## 0.2 Root Cause Identification

#### Definitive Root Cause

The root cause is the use of **module-level mutable global variables** for storing page-specific data that is later accessed by Table objects created from different pages.

#### Bug Location

**File**: `src/table.py`  
**Primary Location**: Lines 90-92 (Global Variable Declarations)

```python
EDGES = []  # vector graphics from PyMuPDF
CHARS = []  # text characters from PyMuPDF
TEXTPAGE = None
```

#### Trigger Conditions

The bug is triggered when:

1. `find_tables()` is called on Page N, populating `CHARS`, `EDGES`, `TEXTPAGE` with Page N's data
2. A `Table` object is created and stored
3. `find_tables()` is called on Page N+1, **overwriting** the globals with Page N+1's data
4. `table.extract()` is called on the Table from Page N
5. The method accesses `CHARS` (now containing Page N+1's data) and returns incorrect content

#### Evidence from Repository Analysis

| Component | File:Line | Issue |
|-----------|-----------|-------|
| Global Declarations | `src/table.py:90-92` | EDGES, CHARS, TEXTPAGE defined at module level |
| Global Reset | `src/table.py:2633-2638` | `find_tables()` clears and repopulates globals |
| Table.extract() | `src/table.py:1564-1571` | Uses `chars = CHARS` (global reference) |
| Table.to_markdown() | `src/table.py:1628-1637` | Uses `extract_cells(TEXTPAGE, ...)` |

#### Conclusion Rationale

This conclusion is definitive because:

1. The bug was **reproduced** with a test that creates a 2-page PDF with distinct content markers
2. Page 0's table.extract() returns "PAGE2" content instead of "PAGE1" content
3. The global variable pattern is explicitly documented in GitHub Issues #3592 and #2892
4. The code path from `find_tables()` → global reset → `Table.extract()` → global access is verified


## 0.3 Diagnostic Execution

#### Code Examination Results

**File analyzed**: `src/table.py`

**Problematic code blocks**:

| Location | Lines | Issue |
|----------|-------|-------|
| Global Declarations | 90-92 | Module-level mutable globals |
| Table.extract() | 1564-1571 | Direct global CHARS reference |
| Table.to_markdown() | 1628-1637 | Direct global TEXTPAGE reference |
| find_tables() | 2633-2638 | Global state reset on each call |

**Execution flow leading to bug**:

1. `page.find_tables()` → Calls `find_tables()` function
2. Line 2637-2638: `CHARS = []` and `EDGES = []` reset globals
3. Line 2659: `make_chars(page, clip=clip)` fills `CHARS` with current page data
4. Line 2155: `make_chars()` sets `global TEXTPAGE` and appends to `CHARS`
5. `Table` objects are created with references to page structure but NOT to `CHARS`/`TEXTPAGE`
6. Later: `table.extract()` accesses `CHARS` which now contains different page's data

#### Repository Analysis Findings

| Tool Used | Command Executed | Finding | File:Line |
|-----------|------------------|---------|-----------|
| grep | `grep -n "global" src/table.py` | `global CHARS, EDGES` declaration | src/table.py:2637 |
| grep | `grep -n "CHARS =" src/table.py` | CHARS reset to empty list | src/table.py:2638 |
| grep | `grep -n "chars = CHARS" src/table.py` | Table.extract() uses global | src/table.py:1571 |
| grep | `grep -n "TEXTPAGE" src/table.py` | Multiple global references | src/table.py:92,1591,2155 |
| bash | `python test_global_bug.py` | Bug reproduced successfully | stdout |

#### Web Search Findings

**Search queries executed**:
- "PyMuPDF table parsing content missing GitHub issues"

**Web sources referenced**:
- GitHub Issue #3592: "trouble in page.find_tables"
- GitHub Issue #2892: "Some cells are missing in page.find_tables()"
- Medium article: "Solving Common Issues With Table Detection and Extraction"

**Key findings incorporated**:
- Issue #3592 user reports: "content did not belong to the first page but last page"
- Issue #3592 specifically mentions: "maybe the 'global' keyword make this trouble?"
- Issue #2892 reports cells missing from extracted tables

#### Fix Verification Analysis

**Steps followed to reproduce bug**:

1. Created test PDF with 2 pages, each with a 2x2 table
2. Page 0 table contains: "PAGE1_A", "PAGE1_B", "PAGE1_C", "PAGE1_D"
3. Page 1 table contains: "PAGE2_X", "PAGE2_Y", "PAGE2_Z", "PAGE2_W"
4. Collected Table objects from both pages
5. Called `extract()` on both tables after processing both pages

**Confirmation tests used**:

```python
# Test output shows the bug:
# Page 0 table content: [['PAGE2_X', 'PAGE2_Y'], ['PAGE2_Z', 'PAGE2_W']]
# BUG DETECTED: Page 0 table has PAGE2 content!
```

**Boundary conditions and edge cases covered**:
- Single page extraction (works correctly)
- Multi-page extraction with deferred extract() call (demonstrates bug)
- Immediate extraction after find_tables() (workaround works)

**Verification confidence level**: **95%** - Bug is definitively reproduced and root cause is confirmed through code analysis and test execution.


## 0.4 Bug Fix Specification

#### The Definitive Fix (Documentation Only)

Per user instructions: **"Do not change any working code"** - the fix has been documented with detailed TODO comments rather than implemented.

**Files modified with TODO documentation**: `src/table.py`

#### Change Instructions (TODO Documentation Added)

**Location 1: Global Variable Declarations (Line 90-92)**

- **Action**: INSERT TODO documentation block before global declarations
- **Lines**: 90-122 (new block inserted)
- **Content**: Comprehensive bug documentation including problem statement, root cause, reproduction steps, fix approach, and references

**Location 2: find_tables() Global Reset (Line 2633-2638)**

- **Action**: INSERT TODO comment before global reset
- **Lines**: 2633-2637 (new comments added)
- **Purpose**: Mark the location where globals are cleared, causing state corruption

**Location 3: Table.extract() CHARS Access (Line 1564-1571)**

- **Action**: INSERT TODO comment before `chars = CHARS` line
- **Lines**: 1564-1570 (new comments added)
- **Purpose**: Mark the location where global CHARS is accessed

**Location 4: Table.to_markdown() TEXTPAGE Access (Line 1628-1637)**

- **Action**: INSERT TODO comment before `extract_cells(TEXTPAGE, ...)` call
- **Lines**: 1628-1635 (new comments added)
- **Purpose**: Mark the location where global TEXTPAGE is accessed

#### Recommended Fix Implementation (For Future Reference)

The proper fix would involve:

1. **Store per-Table copies of CHARS and TEXTPAGE**:
   ```python
   class Table:
       def __init__(self, page, cells, chars=None, textpage=None):
           self._chars = chars if chars else CHARS.copy()
           self._textpage = textpage
   ```

2. **Modify Table.extract() to use instance data**:
   ```python
   def extract(self, **kwargs) -> list:
       chars = self._chars  # Use instance copy
   ```

3. **Modify Table.to_markdown() to use instance data**:
   ```python
   cells[i][j] = extract_cells(
       self._textpage, cell_boxes[i][j], markdown=True
   )
   ```

#### Fix Validation

**Test command to verify documentation**:
```bash
grep -n "TODO: BUG" src/table.py
```

**Expected output**:
```
90:# TODO: BUG - Global Variable State Corruption in Multi-Page Table Extraction
1564:        # TODO: BUG LOCATION - Global CHARS Reference
1628:                    # TODO: BUG LOCATION - Global TEXTPAGE Reference
2633:    # TODO: BUG LOCATION - Global State Reset
```

**Confirmation**: All 4 TODO locations have been documented.


## 0.5 Scope Boundaries

#### Changes Required (EXHAUSTIVE LIST)

| File | Lines | Change Type | Description |
|------|-------|-------------|-------------|
| `src/table.py` | 90-122 | INSERT | TODO documentation block at global declarations |
| `src/table.py` | 1564-1570 | INSERT | TODO comment at Table.extract() |
| `src/table.py` | 1628-1635 | INSERT | TODO comment at Table.to_markdown() |
| `src/table.py` | 2633-2637 | INSERT | TODO comment at find_tables() global reset |
| `tests/conftest.py` | 35 | MODIFY | Add `--break-system-packages` for environment compatibility |
| `tests/test_global_state_bug.py` | 1-130 | CREATE | New test file documenting the bug behavior |

**No other files require modification.**

#### Explicitly Excluded

**Do not modify**:
- `src/table.py` working code logic (per user instructions)
- `Table.__init__()` method
- `TableFinder` class
- `make_chars()` function
- `make_edges()` function
- `extract_cells()` function
- `extract_text()` function

**Do not refactor**:
- Global variable declarations into instance variables (documentation only)
- Table.extract() to accept CHARS as parameter
- Table.to_markdown() to accept TEXTPAGE as parameter

**Do not add**:
- Bug fixes that change working code
- Performance optimizations
- Additional features beyond bug documentation
- Changes to build configuration beyond environment setup


## 0.6 Verification Protocol

#### Bug Documentation Confirmation

**Execute**: Verify TODO comments are present
```bash
grep -n "TODO: BUG" src/table.py
```

**Expected output**:
```
90:# TODO: BUG - Global Variable State Corruption
1564:        # TODO: BUG LOCATION - Global CHARS Reference
1628:                    # TODO: BUG LOCATION - Global TEXTPAGE Reference
2633:    # TODO: BUG LOCATION - Global State Reset
```

#### Bug Demonstration Test

**Execute**: Run the new test suite
```bash
python3 -m pytest tests/test_global_state_bug.py -v
```

**Expected output**:
```
tests/test_global_state_bug.py::TestGlobalStateBug::test_multipage_extraction_bug_demonstration PASSED
tests/test_global_state_bug.py::TestGlobalStateBug::test_single_page_extraction_works PASSED
tests/test_global_state_bug.py::TestGlobalStateBug::test_immediate_extraction_after_find_works PASSED
```

#### Regression Check

**Run existing test suite**:
```bash
python3 -m pytest tests/test_tables.py -v
```

**Expected**: All existing tests pass (documentation-only changes do not affect functionality)

#### Workaround Validation

Users can work around the bug by extracting table content **immediately** after calling `find_tables()`:

```python
# WORKAROUND: Extract immediately after find_tables
for page in doc:
    tables = page.find_tables()
    for table in tables.tables:
        content = table.extract()  # Extract NOW while CHARS is valid
        results.append((page.number, content))
```

This workaround is validated by `test_immediate_extraction_after_find_works` in the test suite.


## 0.7 Execution Requirements

#### Research Completeness Checklist

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Repository structure fully mapped | ✓ Complete | Root, src/, tests/ folders explored |
| All related files examined with retrieval tools | ✓ Complete | src/table.py (2698 lines), tests/test_tables.py (466 lines) |
| Bash analysis completed for patterns/dependencies | ✓ Complete | grep commands for globals, TODO markers |
| Root cause definitively identified with evidence | ✓ Complete | Global CHARS/TEXTPAGE variables at lines 90-92 |
| Single solution determined and validated | ✓ Complete | TODO documentation added at 4 locations |
| Web search for related issues | ✓ Complete | GitHub Issues #3592, #2892 confirm the bug |

#### Fix Implementation Rules

| Rule | Compliance |
|------|------------|
| Make the exact specified change only | ✓ TODO documentation added, no logic changes |
| Zero modifications outside the bug fix | ✓ Only test environment and documentation |
| No interpretation or improvement of working code | ✓ Existing code preserved |
| Preserve all whitespace and formatting except where changed | ✓ Only comment insertions |

#### Environment Configuration

**Python Version**: 3.12.3 (compatible with project requirement ≥3.10)

**Dependencies Installed**:
- pymupdf 1.26.7
- pytest 9.0.2

**Environment Setup Command**:
```bash
pip3 install --break-system-packages pymupdf pytest
```

#### Test Execution Summary

| Test | Result | Purpose |
|------|--------|---------|
| `test_multipage_extraction_bug_demonstration` | PASSED | Confirms bug is reproducible |
| `test_single_page_extraction_works` | PASSED | Confirms single-page extraction unaffected |
| `test_immediate_extraction_after_find_works` | PASSED | Validates workaround |


