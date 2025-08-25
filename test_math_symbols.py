#!/usr/bin/env python3
"""
Test script to verify mathematical symbol handling in PDF generation.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from pdf_generator.pdf_creator import PDFCreator

def test_math_symbols():
    """Test mathematical symbol handling in PDF generation."""
    
    # Create a test problem with mathematical symbols
    test_problem = {
        "title": "Mathematical Symbols Test",
        "platform": "Test Platform",
        "url": "http://test.example.com",
        "scrape_date": "2024-01-01T00:00:00Z",
        "problem_statement": """This is a test problem with mathematical symbols.
        
        Mathematical expressions with subscripts and superscripts:
        - Summation: $\\sum_{i=1}^{n} x_i^2$
        - Integral: $\\int_{0}^{\\infty} e^{-x^2} dx$
        - Fraction: $\\frac{a+b}{c-d}$
        - Greek letters: $\\alpha, \\beta, \\gamma, \\delta, \\epsilon$
        - Inequalities: $a \\leq b, c \\geq d, e \\neq f$
        - Logic symbols: $\\forall x, \\exists y, \\neg p$
        - Set theory: $A \\cap B, C \\cup D, E \\subset F$
        - Arrows: $\\rightarrow, \\leftarrow, \\leftrightarrow$
        - Special symbols: $\\infty, \\partial, \\nabla, \\angle$
        
        Inline math: The formula $E = mc^2$ is Einstein's famous equation.
        
        More complex expressions: $\\sum_{i=1}^{n} (x_i - \\bar{x})^2$ represents variance.
        
        Subscript examples: $x_1, x_2, x_{i+1}, A_{ij}$
        
        Superscript examples: $x^2, x^3, x^{n}, e^{i\\pi}$
        
        Combined sub/superscripts: $x_1^2, A_{ij}^{kl}$""",
        
        "input_format": "Standard input format with mathematical notation.",
        "output_format": "Expected output with properly rendered mathematical symbols.",
        "constraints": "Time limit: 1 second, Memory limit: 256 MB",
        "examples": [
            {
                "input": "Sample input with symbols like $\\alpha$ and $x_1$",
                "output": "Sample output with symbols like $\\beta$ and $x_2$"
            }
        ]
    }
    
    # Create PDF creator with better font support
    pdf_creator = PDFCreator(output_dir="./test_output")
    
    # Generate PDF
    try:
        output_path = pdf_creator.create_problem_pdf(test_problem, "math_symbols_test.pdf")
        print(f"PDF created successfully: {output_path}")
        return True
    except Exception as e:
        print(f"Error creating PDF: {e}")
        return False

if __name__ == "__main__":
    success = test_math_symbols()
    sys.exit(0 if success else 1)