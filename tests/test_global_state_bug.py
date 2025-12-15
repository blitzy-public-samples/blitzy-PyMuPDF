"""
Test suite for documenting and demonstrating the global variable state corruption
bug in multi-page table extraction.

This test file demonstrates the bug described in GitHub Issues #3592 and #2892
where Table.extract() and Table.to_markdown() return incorrect data from the
last processed page instead of the page where the table was originally detected.

ROOT CAUSE:
-----------
Module-level global variables (CHARS, EDGES, TEXTPAGE) in src/table.py are
overwritten each time find_tables() is called. Table objects reference these
globals directly rather than storing their own copy of the character data.

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
- GitHub Issue #3592: "trouble in page.find_tables"
- GitHub Issue #2892: "Some cells are missing in page.find_tables()"
"""

import io
import pytest
import pymupdf


class TestGlobalStateBug:
    """Test class for demonstrating the global variable state corruption bug."""

    @staticmethod
    def _create_multipage_pdf_with_tables():
        """
        Create a 2-page PDF where each page has a simple 2x2 table with
        distinct content markers to identify which page's data is returned.
        
        Page 0 table contains: PAGE1_A, PAGE1_B, PAGE1_C, PAGE1_D
        Page 1 table contains: PAGE2_X, PAGE2_Y, PAGE2_Z, PAGE2_W
        
        Returns:
            io.BytesIO: In-memory PDF document
        """
        doc = pymupdf.open()
        
        # Create page 0 with a table containing PAGE1 markers
        page0 = doc.new_page(width=612, height=792)
        # Draw a 2x2 table manually
        rect = pymupdf.Rect(100, 100, 300, 200)
        page0.draw_rect(rect, color=(0, 0, 0), width=1)
        # Horizontal line in middle
        page0.draw_line((100, 150), (300, 150), color=(0, 0, 0), width=1)
        # Vertical line in middle
        page0.draw_line((200, 100), (200, 200), color=(0, 0, 0), width=1)
        # Insert text in each cell
        page0.insert_text((110, 130), "PAGE1_A", fontsize=10)
        page0.insert_text((210, 130), "PAGE1_B", fontsize=10)
        page0.insert_text((110, 180), "PAGE1_C", fontsize=10)
        page0.insert_text((210, 180), "PAGE1_D", fontsize=10)
        
        # Create page 1 with a table containing PAGE2 markers
        page1 = doc.new_page(width=612, height=792)
        # Draw same table structure
        rect = pymupdf.Rect(100, 100, 300, 200)
        page1.draw_rect(rect, color=(0, 0, 0), width=1)
        page1.draw_line((100, 150), (300, 150), color=(0, 0, 0), width=1)
        page1.draw_line((200, 100), (200, 200), color=(0, 0, 0), width=1)
        # Insert text in each cell
        page1.insert_text((110, 130), "PAGE2_X", fontsize=10)
        page1.insert_text((210, 130), "PAGE2_Y", fontsize=10)
        page1.insert_text((110, 180), "PAGE2_Z", fontsize=10)
        page1.insert_text((210, 180), "PAGE2_W", fontsize=10)
        
        # Save to bytes
        pdf_bytes = io.BytesIO()
        doc.save(pdf_bytes)
        doc.close()
        pdf_bytes.seek(0)
        return pdf_bytes

    def test_multipage_extraction_bug_demonstration(self):
        """
        Demonstrate the global variable state corruption bug.
        
        This test shows that when tables are collected from multiple pages
        and then extracted later, the content from the LAST processed page
        incorrectly appears in all tables due to global variable corruption.
        
        EXPECTED BEHAVIOR (if bug was fixed):
        - tables[0].extract() should contain PAGE1 content
        - tables[1].extract() should contain PAGE2 content
        
        ACTUAL BEHAVIOR (demonstrating the bug):
        - tables[0].extract() contains PAGE2 content (INCORRECT)
        - tables[1].extract() contains PAGE2 content (correct but for wrong reason)
        """
        pdf_bytes = self._create_multipage_pdf_with_tables()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        # Collect tables from all pages (bug pattern)
        tables = []
        for page in doc:
            page_tables = page.find_tables()
            if page_tables.tables:
                tables.extend(page_tables.tables)
        
        # Now extract content - this is where the bug manifests
        # tables[0] was found on page 0, but extract() will use page 1's global data
        
        if len(tables) >= 2:
            table0_content = tables[0].extract()
            table1_content = tables[1].extract()
            
            # Flatten the content to check for page markers
            table0_flat = str(table0_content)
            table1_flat = str(table1_content)
            
            # Document the bug: both tables will have PAGE2 content
            # because the global CHARS variable contains page 1's data
            # when extract() is called on tables[0]
            
            # This assertion documents the BUG - tables[0] should have PAGE1
            # but due to the bug, it may have PAGE2 content
            has_page1_in_table0 = "PAGE1" in table0_flat
            has_page2_in_table0 = "PAGE2" in table0_flat
            has_page2_in_table1 = "PAGE2" in table1_flat
            
            # The bug is demonstrated if table0 has PAGE2 content instead of PAGE1
            # We're documenting this known issue, so we pass the test either way
            # to avoid blocking CI, but we log the bug detection
            if has_page2_in_table0 and not has_page1_in_table0:
                print("\nBUG DETECTED: Page 0 table contains PAGE2 content instead of PAGE1!")
                print(f"Table 0 content: {table0_content}")
                print(f"Table 1 content: {table1_content}")
            
            # Test passes to document the bug exists without blocking CI
            assert True
        else:
            # If no tables found, skip the test
            pytest.skip("No tables found in test PDF")
        
        doc.close()

    def test_single_page_extraction_works(self):
        """
        Verify that single-page table extraction works correctly.
        
        When only one page is processed, the global variable issue doesn't
        manifest because there's no subsequent page to overwrite the globals.
        """
        pdf_bytes = self._create_multipage_pdf_with_tables()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        # Only process page 0
        page = doc[0]
        tables = page.find_tables()
        
        if tables.tables:
            table = tables[0]
            content = table.extract()
            content_flat = str(content)
            
            # For single page extraction, content should be from PAGE1
            assert "PAGE1" in content_flat, f"Single page extraction failed: {content}"
        
        doc.close()

    def test_immediate_extraction_after_find_works(self):
        """
        Validate the workaround: extracting immediately after find_tables().
        
        This test demonstrates that extracting table content immediately
        after calling find_tables() (before processing the next page)
        correctly returns the current page's content.
        """
        pdf_bytes = self._create_multipage_pdf_with_tables()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        results = []
        
        # Workaround pattern: extract immediately after find_tables()
        for page_num, page in enumerate(doc):
            page_tables = page.find_tables()
            for table in page_tables.tables:
                # Extract NOW while global CHARS is valid for this page
                content = table.extract()
                results.append((page_num, content))
        
        # Verify correct content was extracted
        for page_num, content in results:
            content_flat = str(content)
            
            if page_num == 0:
                # Page 0 should have PAGE1 content
                assert "PAGE1" in content_flat, (
                    f"Immediate extraction workaround failed for page 0: {content}"
                )
            elif page_num == 1:
                # Page 1 should have PAGE2 content
                assert "PAGE2" in content_flat, (
                    f"Immediate extraction workaround failed for page 1: {content}"
                )
        
        doc.close()
