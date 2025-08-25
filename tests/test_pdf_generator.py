import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time

from pdf_generator.pdf_creator import PDFCreator
from reportlab.platypus import Paragraph

SAMPLE_PROBLEM = {
    'title': 'Sample Problem',
    'problem_statement': 'Solve X.',
    'input_format': 'Input',
    'output_format': 'Output',
    'constraints': 'None',
    'examples': [{'input': '1', 'output': '2', 'explanation': ''}],
    'time_limit': '1s',
    'memory_limit': '256MB',
    'images': [],
    'platform': 'Sample',
    'url': 'https://example.com',
}


def test_pdf_generation_and_quality(tmp_path, monkeypatch):
    monkeypatch.setattr(PDFCreator, "_add_summary", lambda self, story, problem: None)
    monkeypatch.setattr(PDFCreator, "_build_content_story", lambda self, problem, section_title: [Paragraph(problem["problem_statement"], self.styles["Normal"])])
    creator = PDFCreator(output_dir=str(tmp_path))
    path = creator.create_problem_pdf(SAMPLE_PROBLEM, filename='sample.pdf')
    assert os.path.exists(path)
    with open(path, 'rb') as f:
        header = f.read(4)
    assert header == b'%PDF'


def test_pdf_generation_performance(tmp_path, monkeypatch):
    monkeypatch.setattr(PDFCreator, "_add_summary", lambda self, story, problem: None)
    monkeypatch.setattr(PDFCreator, "_build_content_story", lambda self, problem, section_title: [Paragraph(problem["problem_statement"], self.styles["Normal"])])
    creator = PDFCreator(output_dir=str(tmp_path))
    start = time.perf_counter()
    creator.create_problem_pdf(SAMPLE_PROBLEM, filename='perf.pdf')
    duration = time.perf_counter() - start
    assert duration < 5.0


def test_process_text_content_handles_single_newlines(tmp_path):
    creator = PDFCreator(output_dir=str(tmp_path))
    raw = 'Output\nthe\nanswers\nin\na\ntotal\nof\nQ\nlines.'
    # By default single newlines are converted to spaces
    assert creator._process_text_content(raw) == ['Output the answers in a total of Q lines.']
    # When preserving lines they remain intact
    assert creator._process_text_content(raw, preserve_lines=True) == [raw]
