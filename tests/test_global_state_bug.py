"""
Global Variable State Corruption Bug Documentation and Test Suite

This test file documents and demonstrates the global variable state corruption
bug in multi-page table extraction. The bug manifests when users iterate through
a multi-page PDF document, collecting Table objects from page.find_tables(),
and later call table.extract() or table.to_markdown() on those collected tables.
The extracted content incorrectly returns data from the LAST processed page
instead of the page where each table was originally detected.

ROOT CAUSE:
-----------
Module-level global variables (CHARS, EDGES, TEXTPAGE) in src/table.py are
overwritten each time find_tables() is called. Table objects reference these
globals directly rather than storing their own copy of the character data.

Bug Location: src/table.py
- Lines 90-92: Global declarations (EDGES, CHARS, TEXTPAGE)
- Line 1571: Table.extract() uses `chars = CHARS` (global reference)
- Line 1635: Table.to_markdown() uses `extract_cells(TEXTPAGE, ...)`
- Lines 2633-2638: find_tables() clears and repopulates globals

REPRODUCTION STEPS:
-------------------
    import fitz
    doc = fitz.open("multipage.pdf")
    tables = []
    for page in doc:
        tables.extend(page.find_tables().tables)
    # BUG: tables[0].extract() returns last page's content

WORKAROUND:
-----------
Extract table content immediately after calling find_tables(), before processing
the next page:

    for page in doc:
        page_tables = page.find_tables()
        for table in page_tables.tables:
            content = table.extract()  # Extract NOW while CHARS is valid
            results.append((page.number, content))

References:
- GitHub Issue #3592: "trouble in page.find_tables" - User reports content
  from first page replaced with last page content
- GitHub Issue #2892: "Some cells are missing in page.find_tables()"
"""

import pytest
import pymupdf


def create_multipage_test_pdf() -> bytes:
    """
    Create a 2-page PDF where each page has a 2x2 table with distinct content
    markers to identify which page's data is returned during extraction.

    Page 0 table contains: PAGE1_A, PAGE1_B, PAGE1_C, PAGE1_D (arranged in 2x2 grid)
    Page 1 table contains: PAGE2_X, PAGE2_Y, PAGE2_Z, PAGE2_W (arranged in 2x2 grid)

    This function is designed to clearly demonstrate the global variable state
    corruption bug where tables collected from page 0 incorrectly return page 1's
    content when extract() is called after processing all pages.

    Returns:
        bytes: PDF document as bytes suitable for opening with pymupdf.open()
    """
    doc = pymupdf.Document()

    # Page 0: Create table with PAGE1 content markers
    page0 = doc.new_page(width=612, height=792)
    rect0 = pymupdf.Rect(100, 100, 300, 200)  # 200x100 rectangle for 2x2 table
    
    # Use make_table to create a 2x2 grid of cell rectangles
    cells0 = pymupdf.make_table(rect0, rows=2, cols=2)
    
    # Draw table borders
    for row in cells0:
        for cell_rect in row:
            page0.draw_rect(cell_rect, color=(0, 0, 0), width=0.5)
    
    # Insert distinct PAGE1 content markers in each cell
    page1_content = [
        ["PAGE1_A", "PAGE1_B"],
        ["PAGE1_C", "PAGE1_D"]
    ]
    for i, row in enumerate(cells0):
        for j, cell_rect in enumerate(row):
            page0.insert_textbox(
                cell_rect,
                page1_content[i][j],
                fontsize=10,
                align=pymupdf.TEXT_ALIGN_CENTER
            )

    # Page 1: Create table with PAGE2 content markers
    page1 = doc.new_page(width=612, height=792)
    rect1 = pymupdf.Rect(100, 100, 300, 200)
    
    # Use make_table to create a 2x2 grid of cell rectangles
    cells1 = pymupdf.make_table(rect1, rows=2, cols=2)
    
    # Draw table borders
    for row in cells1:
        for cell_rect in row:
            page1.draw_rect(cell_rect, color=(0, 0, 0), width=0.5)
    
    # Insert distinct PAGE2 content markers in each cell
    page2_content = [
        ["PAGE2_X", "PAGE2_Y"],
        ["PAGE2_Z", "PAGE2_W"]
    ]
    for i, row in enumerate(cells1):
        for j, cell_rect in enumerate(row):
            page1.insert_textbox(
                cell_rect,
                page2_content[i][j],
                fontsize=10,
                align=pymupdf.TEXT_ALIGN_CENTER
            )

    # Return PDF as bytes
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestGlobalStateBug:
    """
    Test class for documenting and demonstrating the global variable state
    corruption bug in multi-page table extraction.

    This test class contains three test methods:
    1. test_multipage_extraction_bug_demonstration - Reproduces the bug
    2. test_single_page_extraction_works - Confirms single-page is unaffected
    3. test_immediate_extraction_after_find_works - Validates the workaround

    All tests create test PDFs with distinct content markers to verify which
    page's data is actually returned during table extraction.
    """

    @pytest.mark.xfail(
        reason="Known bug: Global CHARS variable causes Page 0 table to return Page 1 content. "
               "See GitHub Issues #3592 and #2892.",
        strict=False  # Don't fail if the bug is fixed
    )
    def test_multipage_extraction_bug_demonstration(self):
        """
        Demonstrate the global variable state corruption bug.

        This test reproduces the bug where Table objects collected from multiple
        pages all return the content from the LAST processed page when extract()
        is called after iterating through all pages.

        Bug Reproduction Pattern:
        1. Create 2-page PDF with distinct markers (PAGE1_* and PAGE2_*)
        2. Iterate through pages, collecting Table objects from find_tables()
        3. After processing all pages, call extract() on collected tables
        4. Page 0's table incorrectly returns PAGE2 content

        EXPECTED BEHAVIOR (if bug was fixed):
        - tables[0].extract() should contain PAGE1 content (PAGE1_A, PAGE1_B, etc.)
        - tables[1].extract() should contain PAGE2 content (PAGE2_X, PAGE2_Y, etc.)

        ACTUAL BEHAVIOR (demonstrating the bug):
        - tables[0].extract() contains PAGE2 content (INCORRECT - global corruption)
        - tables[1].extract() contains PAGE2 content (correct by coincidence)

        References: GitHub Issues #3592, #2892
        """
        pdf_bytes = create_multipage_test_pdf()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        # Bug Pattern: Collect tables from all pages first, extract later
        collected_tables = []
        for page in doc:
            page_tables = page.find_tables()
            if page_tables.tables:
                collected_tables.extend(page_tables.tables)

        # Verify we found tables on both pages
        assert len(collected_tables) >= 2, (
            f"Expected at least 2 tables (one per page), found {len(collected_tables)}"
        )

        # Extract content from collected tables - this is where the bug manifests
        # At this point, the global CHARS variable contains PAGE2's character data
        # because find_tables() was last called on page 1
        table0_content = collected_tables[0].extract()
        table1_content = collected_tables[1].extract()

        # Flatten content to string for marker verification
        table0_flat = str(table0_content)
        table1_flat = str(table1_content)

        # Log bug detection for diagnostic purposes
        has_page1_in_table0 = "PAGE1" in table0_flat
        has_page2_in_table0 = "PAGE2" in table0_flat

        if has_page2_in_table0 and not has_page1_in_table0:
            # Bug is present: Page 0 table has PAGE2 content
            print("\n" + "=" * 60)
            print("BUG DETECTED: Global Variable State Corruption")
            print("=" * 60)
            print(f"Page 0 table content: {table0_content}")
            print(f"Page 1 table content: {table1_content}")
            print("Page 0 table should have PAGE1 content, but has PAGE2!")
            print("=" * 60)

        # This assertion tests the EXPECTED behavior (will fail if bug present)
        # The xfail marker documents this as a known issue
        assert "PAGE1" in table0_flat, (
            f"BUG: Page 0 table should contain PAGE1 markers but got: {table0_content}. "
            "This demonstrates the global CHARS corruption bug."
        )
        assert "PAGE2" in table1_flat, (
            f"Page 1 table should contain PAGE2 markers but got: {table1_content}"
        )

        doc.close()

    def test_single_page_extraction_works(self):
        """
        Verify that single-page table extraction works correctly.

        When only one page is processed and extracted immediately, the global
        variable state corruption issue doesn't manifest because there's no
        subsequent page to overwrite the global CHARS, EDGES, TEXTPAGE variables.

        This test confirms that the bug is specifically a multi-page iteration
        issue, not a general table extraction failure.

        EXPECTED BEHAVIOR:
        - Extract table from page 0 only
        - Content should contain PAGE1 markers (PAGE1_A, PAGE1_B, etc.)

        ACTUAL BEHAVIOR:
        - Works correctly because globals aren't overwritten

        References: GitHub Issues #3592, #2892
        """
        pdf_bytes = create_multipage_test_pdf()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        # Only process page 0 - don't iterate to other pages
        page0 = doc[0]
        page_tables = page0.find_tables()

        assert page_tables.tables, "No tables found on page 0"

        # Extract immediately - globals contain page 0's data
        table = page_tables[0]
        content = table.extract()
        content_flat = str(content)

        # Single page extraction should work correctly
        assert "PAGE1" in content_flat, (
            f"Single page extraction should return PAGE1 content, got: {content}"
        )

        # Verify we DON'T have PAGE2 content (that would indicate a different bug)
        assert "PAGE2" not in content_flat, (
            f"Single page extraction should NOT have PAGE2 content, got: {content}"
        )

        doc.close()

    def test_immediate_extraction_after_find_works(self):
        """
        Validate the workaround: extract immediately after find_tables().

        This test demonstrates the recommended workaround for the global variable
        state corruption bug. By extracting table content immediately after
        calling find_tables() (before processing the next page), the correct
        page-specific data is captured while the globals still reference it.

        WORKAROUND PATTERN:
            for page in doc:
                page_tables = page.find_tables()
                for table in page_tables.tables:
                    content = table.extract()  # Extract NOW while CHARS is valid
                    results.append((page.number, content))

        EXPECTED BEHAVIOR:
        - Page 0 tables extracted immediately should have PAGE1 content
        - Page 1 tables extracted immediately should have PAGE2 content
        - Both extractions return correct data because globals aren't yet overwritten

        ACTUAL BEHAVIOR:
        - Works correctly with immediate extraction

        References: GitHub Issues #3592, #2892
        """
        pdf_bytes = create_multipage_test_pdf()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        # WORKAROUND: Extract immediately after find_tables() for each page
        extraction_results = []
        for page_num, page in enumerate(doc):
            page_tables = page.find_tables()
            for table in page_tables.tables:
                # Extract NOW while global CHARS is valid for this page
                content = table.extract()
                extraction_results.append({
                    "page_num": page_num,
                    "content": content,
                    "content_str": str(content)
                })

        # Should have results from both pages
        assert len(extraction_results) >= 2, (
            f"Expected results from at least 2 pages, got {len(extraction_results)}"
        )

        # Verify correct content was captured for each page
        page0_results = [r for r in extraction_results if r["page_num"] == 0]
        page1_results = [r for r in extraction_results if r["page_num"] == 1]

        # Page 0 should have PAGE1 content (immediate extraction workaround)
        for result in page0_results:
            assert "PAGE1" in result["content_str"], (
                f"WORKAROUND FAILED: Page 0 immediate extraction should have "
                f"PAGE1 content, got: {result['content']}"
            )
            assert "PAGE2" not in result["content_str"], (
                f"WORKAROUND FAILED: Page 0 should NOT have PAGE2 content, "
                f"got: {result['content']}"
            )

        # Page 1 should have PAGE2 content
        for result in page1_results:
            assert "PAGE2" in result["content_str"], (
                f"Page 1 extraction should have PAGE2 content, "
                f"got: {result['content']}"
            )
            assert "PAGE1" not in result["content_str"], (
                f"Page 1 should NOT have PAGE1 content, "
                f"got: {result['content']}"
            )

        doc.close()
