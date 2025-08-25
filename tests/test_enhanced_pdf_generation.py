"""
Enhanced PDF Generation Test Suite

Tests for improved mathematical symbol handling, text processing,
and layout preservation in PDF generation for competitive programming problems.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pdf_generator.pdf_creator import PDFCreator
from scraper.base_scraper import BaseScraper
from bs4 import BeautifulSoup


class MockScraper(BaseScraper):
    """Concrete implementation of BaseScraper for testing."""
    
    def get_problem_statement(self, url: str) -> Dict[str, Any]:
        """Mock implementation."""
        return {}
    
    def get_editorial(self, url: str) -> Dict[str, Any]:
        """Mock implementation."""
        return {}
    
    def is_valid_url(self, url: str) -> bool:
        """Mock implementation."""
        return True


class TestEnhancedPDFGeneration(unittest.TestCase):
    """Test suite for enhanced PDF generation capabilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.pdf_creator = PDFCreator(output_dir=self.temp_dir)
        self.mock_scraper = MockScraper()
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_latex_symbol_conversion(self):
        """Test comprehensive LaTeX symbol conversion to Unicode."""
        test_cases = [
            # Comparison operators
            ("1 \\leq x \\leq 5", "≤"),
            ("a \\geq b", "≥"),
            ("x \\neq y", "≠"),
            
            # Arithmetic symbols
            ("a \\times b", "×"),
            ("x \\div y", "÷"),
            
            # Greek letters
            ("\\alpha + \\beta", "α"),
            ("\\pi \\approx 3.14", "π"),
            
            # Set theory
            ("A \\cap B", "∩"),
            ("x \\in S", "∈"),
        ]
        
        for latex_input, expected_symbol in test_cases:
            with self.subTest(latex_input=latex_input):
                result = self.pdf_creator._convert_latex_symbols(latex_input)
                self.assertIn(expected_symbol, result)
    
    def test_competitive_programming_patterns(self):
        """Test handling of competitive programming specific patterns."""
        test_cases = [
            # Case subscripts
            ("case1", "case"),
            ("output1", "output"),  
            ("input1", "input"),
            
            # Black square handling
            ("case■1■", "case"),
            ("A■i■", "A"),
        ]
        
        for input_text, expected_word in test_cases:
            with self.subTest(input_text=input_text):
                result = self.pdf_creator._improve_text_formatting(input_text)
                self.assertIn(expected_word, result)
                # Should not contain black squares
                self.assertNotIn("■", result)
    
    def test_image_filtering(self):
        """Test intelligent image filtering for competitive programming sites."""
        # Test exclusion cases
        exclusion_cases = [
            '<img src="/images/flag_jp.png" alt="Japanese">',
            '<img src="/lang/en.png" class="flag">',
            '<img src="logo.png" class="navbar-brand">',
            '<img width="16" height="16" src="favicon.ico">',
        ]
        
        for img_html in exclusion_cases:
            with self.subTest(img_html=img_html):
                soup = BeautifulSoup(img_html, 'html.parser')
                img_tag = soup.find('img')
                if img_tag is not None and hasattr(img_tag, 'get'):
                    src = img_tag.get('src', '') or ''
                    if isinstance(src, list):
                        src = src[0] if src else ''
                    
                    result = self.mock_scraper._should_exclude_image(img_tag, str(src))
                    self.assertTrue(result, f"Should exclude: {img_html}")
        
        # Test preservation cases  
        preservation_cases = [
            '<img src="diagram.png" alt="Problem diagram">',
            '<img src="graph.jpg" alt="Sample graph">',
            '<img src="example.png" alt="Input/output example">',
        ]
        
        for img_html in preservation_cases:
            with self.subTest(img_html=img_html):
                soup = BeautifulSoup(img_html, 'html.parser')
                img_tag = soup.find('img')
                if img_tag is not None and hasattr(img_tag, 'get'):
                    src = img_tag.get('src', '') or ''
                    if isinstance(src, list):
                        src = src[0] if src else ''
                    
                    result = self.mock_scraper._should_exclude_image(img_tag, str(src))
                    self.assertFalse(result, f"Should preserve: {img_html}")
    
    def test_pdf_generation_integration(self):
        """Integration test for complete PDF generation with enhanced features."""
        sample_problem = {
            'title': 'Enhanced Test Problem',
            'problem_statement': 'Given an array A of size N, find the sum for i=1 to N.',
            'input_format': 'First line: T',
            'output_format': 'Output the sum',
            'constraints': '1 ≤ T ≤ 100',
            'examples': [{'input': '2\\n3\\n1 2 3', 'output': '6'}],
            'time_limit': '1 second',
            'memory_limit': '256 MB',
            'images': [],
            'platform': 'Test Platform',
            'url': 'http://example.com/problem/123'
        }
        
        # Test PDF creation
        try:
            pdf_path = self.pdf_creator.create_problem_pdf(
                sample_problem, 
                filename='enhanced_test.pdf'
            )
            
            # Verify PDF was created
            self.assertTrue(os.path.exists(pdf_path))
            
            # Verify file is a valid PDF (basic check)
            with open(pdf_path, 'rb') as f:
                header = f.read(4)
                self.assertEqual(header, b'%PDF')
                
        except Exception as e:
            self.fail(f"PDF generation failed: {e}")


class TestTextProcessing(unittest.TestCase):
    """Specific tests for text processing enhancements."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.pdf_creator = PDFCreator(output_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_black_square_elimination(self):
        """Test elimination of problematic black square characters."""
        black_square_chars = [
            '■',  # Black Large Square
            '\u25A0',  # Black Large Square Unicode
            '\u2588',  # Full Block
        ]
        
        for char in black_square_chars:
            with self.subTest(char=repr(char)):
                input_text = f"case{char}1{char}"
                result = self.pdf_creator._improve_text_formatting(input_text)
                # Should not contain the problematic character
                self.assertNotIn(char, result)
                # Should contain reasonable replacement
                self.assertIn("case", result)
                self.assertIn("1", result)
    
    def test_html_entity_processing(self):
        """Test proper handling of HTML entities."""
        test_cases = [
            ("&lt;", "<"), 
            ("&gt;", ">"),
            ("&times;", "×"),
        ]
        
        for entity, expected in test_cases:
            with self.subTest(entity=entity):
                result = self.pdf_creator._improve_text_formatting(entity)
                self.assertEqual(result.strip(), expected)
        
        # Special test for nbsp - it should decode to a space character
        nbsp_result = self.pdf_creator._improve_text_formatting("test&nbsp;text")
        self.assertIn("test", nbsp_result)
        self.assertIn("text", nbsp_result)
    
    def test_html_sanitization_for_reportlab(self):
        """Test that HTML sanitization prevents ReportLab paragraph parsing errors."""
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        
        styles = getSampleStyleSheet()
        
        # Test cases with problematic HTML that would cause ReportLab errors
        problematic_html_cases = [
            '<span class = "lang - en"> Test content </span>',
            '<var>800< / var> points',
            '<h[3]>Problem Statement< / h[3]>',
            '<div class = "part"> Content </div>',
            '<p class = "test"> Paragraph </p>',
        ]
        
        for html_content in problematic_html_cases:
            with self.subTest(html=html_content):
                # Test that sanitization works
                sanitized = self.pdf_creator._sanitize_html_content(html_content)
                self.assertNotIn('class =', sanitized, "Malformed class attributes should be removed")
                self.assertNotIn('< /', sanitized, "Broken closing tags should be fixed")
                
                # Test that sanitized content can be used in ReportLab Paragraph
                try:
                    paragraph = Paragraph(sanitized, styles['Normal'])
                    self.assertIsNotNone(paragraph, "Paragraph creation should succeed")
                except Exception as e:
                    self.fail(f"Paragraph creation failed for sanitized content: {e}")
                
                # Test that improved formatting also works
                formatted = self.pdf_creator._improve_text_formatting(html_content)
                try:
                    paragraph = Paragraph(formatted, styles['Normal'])
                    self.assertIsNotNone(paragraph, "Paragraph creation should succeed for formatted content")
                except Exception as e:
                    self.fail(f"Paragraph creation failed for formatted content: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)