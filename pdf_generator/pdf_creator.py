"""
PDF Creator for OJ Problem Editorial Downloader
Handles creation of formatted PDF documents from scraped content
"""

import os
import io
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import black, blue, darkblue, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, 
    Table, TableStyle, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors

from PIL import Image
import logging

logger = logging.getLogger(__name__)

class PDFCreator:
    """
    Creates formatted PDF documents from scraped problem and editorial data
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize PDF Creator
        
        Args:
            output_dir (str): Directory to save PDF files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Setup styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        # Image cache directory
        self.image_cache_dir = self.output_dir / "images"
        self.image_cache_dir.mkdir(exist_ok=True)
    
    def _setup_custom_styles(self):
        """
        Setup custom paragraph styles for PDF generation
        """
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=20,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=darkblue
        ))
        
        # Section heading style
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=darkblue
        ))
        
        # Subsection heading style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=15,
            textColor=blue
        ))
        
        # Code style
        self.styles.add(ParagraphStyle(
            name='Code',
            parent=self.styles['Normal'],
            fontName='Courier',
            fontSize=10,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=10,
            backColor=colors.lightgrey
        ))
        
        # Problem statement style
        self.styles.add(ParagraphStyle(
            name='ProblemText',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            alignment=TA_JUSTIFY
        ))
        
        # URL style
        self.styles.add(ParagraphStyle(
            name='URL',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=blue,
            spaceAfter=5
        ))
    
    def _download_image(self, img_url: str, filename: str) -> Optional[str]:
        """
        Download image from URL and save locally
        
        Args:
            img_url (str): Image URL
            filename (str): Local filename to save
            
        Returns:
            Optional[str]: Local file path if successful, None otherwise
        """
        try:
            response = requests.get(img_url, timeout=30)
            response.raise_for_status()
            
            # Save image
            local_path = self.image_cache_dir / filename
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Verify it's a valid image
            Image.open(local_path).verify()
            
            logger.info(f"Downloaded image: {img_url} -> {local_path}")
            return str(local_path)
            
        except Exception as e:
            logger.error(f"Failed to download image {img_url}: {e}")
            return None
    
    def _add_image_to_story(self, story: List, img_info: Dict[str, str], max_width: float = 5*inch):
        """
        Add image to PDF story
        
        Args:
            story (List): ReportLab story list
            img_info (Dict): Image information
            max_width (float): Maximum width for image
        """
        try:
            img_url = img_info.get('url', '')
            img_alt = img_info.get('alt', '')
            
            if not img_url:
                return
            
            # Generate filename
            filename = f"img_{hash(img_url) % 10000}.jpg"
            local_path = self._download_image(img_url, filename)
            
            if local_path and os.path.exists(local_path):
                # Add image to PDF
                img = RLImage(local_path, width=max_width, height=None)
                story.append(img)
                
                # Add alt text if available
                if img_alt:
                    story.append(Paragraph(f"<i>{img_alt}</i>", self.styles['Normal']))
                
                story.append(Spacer(1, 12))
                
        except Exception as e:
            logger.error(f"Failed to add image to PDF: {e}")
    
    def create_problem_pdf(self, problem_data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Create PDF from problem data
        
        Args:
            problem_data (Dict): Problem information
            filename (Optional[str]): Custom filename
            
        Returns:
            str: Path to created PDF file
        """
        try:
            # Generate filename if not provided
            if not filename:
                platform = problem_data.get('platform', 'Unknown')
                title = problem_data.get('title', 'Problem')
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{platform}_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            pdf_path = self.output_dir / filename
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            story = []
            
            # Title
            title = problem_data.get('title', 'Problem')
            story.append(Paragraph(title, self.styles['CustomTitle']))
            
            # Platform and URL
            platform = problem_data.get('platform', 'Unknown Platform')
            url = problem_data.get('url', '')
            story.append(Paragraph(f"Platform: {platform}", self.styles['Normal']))
            if url:
                story.append(Paragraph(f"URL: <link href='{url}'>{url}</link>", self.styles['URL']))
            
            story.append(Spacer(1, 20))
            
            # Problem ID/Contest info
            if 'contest_id' in problem_data:
                story.append(Paragraph(f"Contest: {problem_data['contest_id']}", self.styles['Normal']))
            if 'problem_id' in problem_data:
                story.append(Paragraph(f"Problem: {problem_data['problem_id']}", self.styles['Normal']))
            if 'problem_code' in problem_data:
                story.append(Paragraph(f"Problem Code: {problem_data['problem_code']}", self.styles['Normal']))
            
            # Limits
            limits = problem_data.get('limits', {})
            if limits:
                story.append(Paragraph("Constraints:", self.styles['SectionHeading']))
                for limit_type, limit_value in limits.items():
                    story.append(Paragraph(f"{limit_type.replace('_', ' ').title()}: {limit_value}", self.styles['Normal']))
            
            story.append(Spacer(1, 20))
            
            # Problem statement
            statement = problem_data.get('statement', '')
            if statement:
                story.append(Paragraph("Problem Statement:", self.styles['SectionHeading']))
                # Split into paragraphs for better formatting
                paragraphs = statement.split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        story.append(Paragraph(para.strip(), self.styles['ProblemText']))
            
            # Input/Output specifications
            input_spec = problem_data.get('input_specification', '') or problem_data.get('input_format', '')
            output_spec = problem_data.get('output_specification', '') or problem_data.get('output_format', '')
            
            if input_spec:
                story.append(Paragraph("Input:", self.styles['SectionHeading']))
                story.append(Paragraph(input_spec, self.styles['ProblemText']))
            
            if output_spec:
                story.append(Paragraph("Output:", self.styles['SectionHeading']))
                story.append(Paragraph(output_spec, self.styles['ProblemText']))
            
            # Constraints
            constraints = problem_data.get('constraints', '')
            if constraints:
                story.append(Paragraph("Constraints:", self.styles['SectionHeading']))
                story.append(Paragraph(constraints, self.styles['ProblemText']))
            
            # Sample test cases
            samples = problem_data.get('samples', [])
            if samples:
                story.append(Paragraph("Sample Test Cases:", self.styles['SectionHeading']))
                
                # Handle different sample formats
                if isinstance(samples, list) and samples:
                    if isinstance(samples[0], dict) and 'input' in samples[0]:
                        # Codeforces format
                        for i, sample in enumerate(samples, 1):
                            story.append(Paragraph(f"Sample {i}:", self.styles['SubsectionHeading']))
                            story.append(Paragraph("Input:", self.styles['Normal']))
                            story.append(Paragraph(sample.get('input', ''), self.styles['Code']))
                            story.append(Paragraph("Output:", self.styles['Normal']))
                            story.append(Paragraph(sample.get('output', ''), self.styles['Code']))
                    else:
                        # AtCoder format or other
                        inputs = [s for s in samples if s.get('type') == 'input']
                        outputs = [s for s in samples if s.get('type') == 'output']
                        
                        for i, (inp, out) in enumerate(zip(inputs, outputs), 1):
                            story.append(Paragraph(f"Sample {i}:", self.styles['SubsectionHeading']))
                            story.append(Paragraph("Input:", self.styles['Normal']))
                            story.append(Paragraph(inp.get('content', ''), self.styles['Code']))
                            story.append(Paragraph("Output:", self.styles['Normal']))
                            story.append(Paragraph(out.get('content', ''), self.styles['Code']))
            
            # Notes
            notes = problem_data.get('notes', '')
            if notes:
                story.append(Paragraph("Notes:", self.styles['SectionHeading']))
                story.append(Paragraph(notes, self.styles['ProblemText']))
            
            # Statistics (for SPOJ)
            stats = problem_data.get('statistics', {})
            if stats:
                story.append(Paragraph("Statistics:", self.styles['SectionHeading']))
                for stat_name, stat_value in stats.items():
                    story.append(Paragraph(f"{stat_name.title()}: {stat_value}", self.styles['Normal']))
            
            # Footer
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                                  self.styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Problem PDF created: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Failed to create problem PDF: {e}")
            raise
    
    def create_editorial_pdf(self, editorial_data: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        Create PDF from editorial data
        
        Args:
            editorial_data (Dict): Editorial information
            filename (Optional[str]): Custom filename
            
        Returns:
            str: Path to created PDF file
        """
        try:
            # Generate filename if not provided
            if not filename:
                platform = editorial_data.get('platform', 'Unknown')
                title = editorial_data.get('title', 'Editorial')
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{platform}_Editorial_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            pdf_path = self.output_dir / filename
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            story = []
            
            # Title
            title = editorial_data.get('title', 'Editorial')
            story.append(Paragraph(title, self.styles['CustomTitle']))
            
            # Platform and URL
            platform = editorial_data.get('platform', 'Unknown Platform')
            url = editorial_data.get('url', '')
            story.append(Paragraph(f"Platform: {platform}", self.styles['Normal']))
            if url:
                story.append(Paragraph(f"URL: <link href='{url}'>{url}</link>", self.styles['URL']))
            
            # Author (for Codeforces)
            author = editorial_data.get('author', '')
            if author:
                story.append(Paragraph(f"Author: {author}", self.styles['Normal']))
            
            story.append(Spacer(1, 20))
            
            # Editorial sections
            sections = editorial_data.get('sections', [])
            if sections:
                for section in sections:
                    heading = section.get('heading', 'Section')
                    content = section.get('content', '')
                    
                    if heading and heading != 'Editorial':
                        story.append(Paragraph(heading, self.styles['SectionHeading']))
                    
                    if content:
                        # Split content into paragraphs
                        paragraphs = content.split('\n\n')
                        for para in paragraphs:
                            if para.strip():
                                story.append(Paragraph(para.strip(), self.styles['ProblemText']))
                        
                        story.append(Spacer(1, 15))
            
            # Images
            images = editorial_data.get('images', [])
            if images:
                story.append(Paragraph("Images:", self.styles['SectionHeading']))
                for img_info in images:
                    self._add_image_to_story(story, img_info)
            
            # Additional notes
            note = editorial_data.get('note', '')
            if note:
                story.append(Paragraph("Note:", self.styles['SectionHeading']))
                story.append(Paragraph(note, self.styles['ProblemText']))
            
            # Comments count (for Codeforces)
            comments_count = editorial_data.get('comments_count', 0)
            if comments_count > 0:
                story.append(Paragraph(f"Comments: {comments_count}", self.styles['Normal']))
            
            # Footer
            story.append(Spacer(1, 30))
            story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                                  self.styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Editorial PDF created: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Failed to create editorial PDF: {e}")
            raise
    
    def create_combined_pdf(self, problem_data: Dict[str, Any], editorial_data: Dict[str, Any], 
                          filename: Optional[str] = None) -> str:
        """
        Create combined PDF with both problem and editorial
        
        Args:
            problem_data (Dict): Problem information
            editorial_data (Dict): Editorial information
            filename (Optional[str]): Custom filename
            
        Returns:
            str: Path to created PDF file
        """
        try:
            # Generate filename if not provided
            if not filename:
                platform = problem_data.get('platform', 'Unknown')
                title = problem_data.get('title', 'Problem')
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{platform}_Complete_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            pdf_path = self.output_dir / filename
            
            # Create PDF document
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            story = []
            
            # Main title
            title = problem_data.get('title', 'Problem and Editorial')
            story.append(Paragraph(f"{title} - Complete Guide", self.styles['CustomTitle']))
            story.append(Spacer(1, 30))
            
            # Problem section
            story.append(Paragraph("PROBLEM", self.styles['CustomTitle']))
            story.append(Spacer(1, 20))
            
            # Add problem content (similar to create_problem_pdf but without title)
            # [Implementation similar to create_problem_pdf method]
            
            # Page break before editorial
            story.append(PageBreak())
            
            # Editorial section
            story.append(Paragraph("EDITORIAL", self.styles['CustomTitle']))
            story.append(Spacer(1, 20))
            
            # Add editorial content (similar to create_editorial_pdf but without title)
            # [Implementation similar to create_editorial_pdf method]
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Combined PDF created: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"Failed to create combined PDF: {e}")
            raise