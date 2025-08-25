import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import time
from typing import Any, Dict

import pytest
from bs4 import BeautifulSoup
import requests

from scraper.atcoder_scraper import AtCoderScraper
from scraper.codeforces_scraper import CodeforcesScraper
from scraper.spoj_scraper import SPOJScraper
from utils.error_handler import NetworkError, URLValidationError

ATCODER_URL = "https://atcoder.jp/contests/abc001/tasks/abc001_a"
CODEFORCES_URL = "https://codeforces.com/contest/1/problem/A"
SPOJ_URL = "https://www.spoj.com/problems/TEST/"

ATCODER_HTML = """
<html>
<span class='h2'>Sample Title</span>
<div id='task-statement'>
  <div class='lang-en'>Sample problem statement</div>
</div>
</html>
"""

CODEFORCES_HTML = """
<div class='problem-statement'>
  <div class='title'>A. Sample Problem</div>
  <div class='header'>
    <div class='time-limit'>time limit per test2 seconds</div>
    <div class='memory-limit'>memory limit per test256 megabytes</div>
  </div>
  <div class='input-specification'>Input desc</div>
  <div class='output-specification'>Output desc</div>
  <div class='sample-tests'>
    <div class='sample-test'>
      <div class='input'><pre>1</pre></div>
      <div class='output'><pre>2</pre></div>
    </div>
  </div>
</div>
"""

SPOJ_HTML = """
<h1>TEST - Sample Problem</h1>
<div id='problem-body'>
  <p>Statement</p>
  <h2>Input</h2><p>Input desc</p>
  <h2>Output</h2><p>Output desc</p>
  <pre>1</pre><pre>1</pre>
</div>
"""


@pytest.fixture(autouse=True)
def disable_rate_limit(monkeypatch):
    monkeypatch.setattr(AtCoderScraper, '_enforce_rate_limit', lambda self: None)
    monkeypatch.setattr(CodeforcesScraper, '_enforce_rate_limit', lambda self: None)
    monkeypatch.setattr(SPOJScraper, '_enforce_rate_limit', lambda self: None)


def test_atcoder_is_valid_url():
    scraper = AtCoderScraper()
    assert scraper.is_valid_url(ATCODER_URL)
    assert not scraper.is_valid_url('https://example.com')


def test_codeforces_is_valid_url():
    scraper = CodeforcesScraper()
    assert scraper.is_valid_url(CODEFORCES_URL)
    assert not scraper.is_valid_url('https://example.com')


def test_spoj_is_valid_url():
    scraper = SPOJScraper()
    assert scraper.is_valid_url(SPOJ_URL)
    assert not scraper.is_valid_url('https://example.com')


def test_atcoder_parsing(monkeypatch):
    def fake_page(self, url: str):
        return BeautifulSoup(ATCODER_HTML, 'lxml')

    def fake_extract(self, lang_div, url: str) -> Dict[str, Any]:
        return {
            'problem_statement': lang_div.get_text(strip=True),
            'input_format': '',
            'output_format': '',
            'constraints': '',
            'examples': [],
        }

    monkeypatch.setattr(AtCoderScraper, 'get_page_content', fake_page)
    monkeypatch.setattr(AtCoderScraper, '_extract_problem_sections', fake_extract, raising=False)
    monkeypatch.setattr(AtCoderScraper, 'handle_images_for_pdf', lambda self, soup, url: [])

    scraper = AtCoderScraper()
    data = scraper.get_problem_statement(ATCODER_URL)
    assert data['title'] == 'Sample Title'
    assert 'Sample problem statement' in data['problem_statement']


def test_codeforces_parsing(monkeypatch):
    monkeypatch.setattr(CodeforcesScraper, 'get_page_content', lambda self, url: BeautifulSoup(CODEFORCES_HTML, 'lxml'))
    monkeypatch.setattr(CodeforcesScraper, 'handle_images_for_pdf', lambda self, soup, url: [])

    scraper = CodeforcesScraper()
    data = scraper.get_problem_statement(CODEFORCES_URL)
    assert data['title'] == 'Sample Problem'
    assert data['time_limit'] == '2 seconds'
    assert data['input_format'] == 'Input desc'
    assert data['output_format'] == 'Output desc'
    assert isinstance(data['examples'], list)
    assert '256' in data['memory_limit']


def test_spoj_parsing(monkeypatch):
    monkeypatch.setattr(SPOJScraper, 'get_page_content', lambda self, url: BeautifulSoup(SPOJ_HTML, 'lxml'))
    monkeypatch.setattr(SPOJScraper, 'handle_images_for_pdf', lambda self, soup, url: [])

    scraper = SPOJScraper()
    data = scraper.get_problem_statement(SPOJ_URL)
    assert data['title'] == 'Sample Problem'
    assert 'Statement' in data['problem_statement']
    assert data['examples'][0]['input'] == '1'


def test_invalid_url_raises():
    scraper = AtCoderScraper()
    with pytest.raises(URLValidationError):
        scraper.get_problem_statement('https://atcoder.jp/invalid')


def test_network_error(monkeypatch):
    def fail_requests(self, url: str):
        raise requests.exceptions.ConnectionError('fail')

    monkeypatch.setattr(AtCoderScraper, '_get_content_requests', fail_requests)

    scraper = AtCoderScraper()
    with pytest.raises(NetworkError):
        scraper.get_page_content(ATCODER_URL)


def test_scraper_performance(monkeypatch):
    monkeypatch.setattr(CodeforcesScraper, 'get_page_content', lambda self, url: BeautifulSoup(CODEFORCES_HTML, 'lxml'))
    monkeypatch.setattr(CodeforcesScraper, 'handle_images_for_pdf', lambda self, soup, url: [])
    scraper = CodeforcesScraper()
    start = time.perf_counter()
    scraper.get_problem_statement(CODEFORCES_URL)
    duration = time.perf_counter() - start
    assert duration < 1.0
