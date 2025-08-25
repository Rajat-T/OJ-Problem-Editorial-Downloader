#!/usr/bin/env python3
"""
Setup script for OJ Problem Editorial Downloader

This script handles the installation and distribution of the OJ Problem Editorial Downloader package.
It provides entry points for both GUI and CLI usage, and handles all dependencies automatically.

Usage:
    pip install -e .                    # Install in development mode
    pip install .                       # Install normally
    python setup.py sdist bdist_wheel    # Build distribution packages
    python setup.py develop             # Install in development mode (legacy)
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

# Ensure we're running on Python 3.8+
if sys.version_info < (3, 8):
    sys.exit("ERROR: Python 3.8 or higher is required")

# Get the directory containing this script
here = Path(__file__).parent.absolute()

# Read the README file for long description
def read_readme():
    """Read and return the contents of README.md"""
    readme_path = here / "README.md"
    if readme_path.exists():
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "A comprehensive tool for downloading and generating PDFs from online judge problems and editorials."

# Read requirements from requirements.txt
def read_requirements():
    """Read and return the list of requirements from requirements.txt"""
    requirements_path = here / "requirements.txt"
    requirements = []
    
    if requirements_path.exists():
        with open(requirements_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    # Handle version specifications
                    requirements.append(line)
    
    return requirements

# Get version from main module
def get_version():
    """Extract version from the main module"""
    version_file = here / "main.py"
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('__version__'):
                    return line.split('=')[1].strip().strip('"').strip("'")
    return "1.0.0"

# Package metadata
PACKAGE_NAME = "oj-problem-editorial-downloader"
PACKAGE_VERSION = get_version()
PACKAGE_DESCRIPTION = "Download and generate PDFs from online judge problem statements and editorials"
PACKAGE_LONG_DESCRIPTION = read_readme()
PACKAGE_URL = "https://github.com/your-username/OJ-Problem-Editorial-Downloader"
AUTHOR_NAME = "Your Name"
AUTHOR_EMAIL = "your.email@example.com"

# Package requirements
INSTALL_REQUIRES = read_requirements()

# Development dependencies
EXTRAS_REQUIRE = {
    'dev': [
        'pytest>=7.0.0',
        'pytest-cov>=4.0.0',
        'flake8>=5.0.0',
        'black>=22.0.0',
        'mypy>=1.0.0',
        'isort>=5.10.0',
        'pre-commit>=2.20.0',
    ],
    'docs': [
        'sphinx>=5.0.0',
        'sphinx-rtd-theme>=1.0.0',
        'myst-parser>=0.18.0',
    ],
    'test': [
        'pytest>=7.0.0',
        'pytest-cov>=4.0.0',
        'pytest-mock>=3.8.0',
        'responses>=0.21.0',
    ]
}

# All extra dependencies combined
EXTRAS_REQUIRE['all'] = [
    dep for deps in EXTRAS_REQUIRE.values() for dep in deps
]

# Entry points for command-line usage
ENTRY_POINTS = {
    'console_scripts': [
        'oj-downloader=main:main',
        'oj-problem-downloader=main:main',
        'ojpd=main:main',
    ],
}

# Classifiers for PyPI
CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Intended Audience :: Education',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Topic :: Education',
    'Topic :: Internet :: WWW/HTTP :: Browsers',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Text Processing :: Markup :: HTML',
    'Topic :: Utilities',
]

# Keywords for PyPI search
KEYWORDS = [
    'competitive-programming',
    'online-judge',
    'pdf-generation',
    'web-scraping',
    'atcoder',
    'codeforces',
    'spoj',
    'automation',
    'selenium',
    'educational-tools'
]

# Package data to include
PACKAGE_DATA = {
    '': [
        '*.txt',
        '*.md',
        '*.rst',
        '*.ini',
        '*.cfg',
        '*.yaml',
        '*.yml',
        '*.json',
    ],
}

# Data files to include
DATA_FILES = [
    ('config', ['example_config.ini']),
    ('examples', ['example_urls.txt', 'test_urls.txt']),
    ('docs', ['README.md', 'IMPLEMENTATION_SUMMARY.md']),
]

def main():
    """Main setup function"""
    
    # Verify that all required files exist
    required_files = ['main.py', 'requirements.txt', 'README.md']
    missing_files = [f for f in required_files if not (here / f).exists()]
    
    if missing_files:
        print(f"ERROR: Missing required files: {missing_files}")
        sys.exit(1)
    
    # Setup configuration
    setup(
        # Basic package information
        name=PACKAGE_NAME,
        version=PACKAGE_VERSION,
        description=PACKAGE_DESCRIPTION,
        long_description=PACKAGE_LONG_DESCRIPTION,
        long_description_content_type='text/markdown',
        url=PACKAGE_URL,
        
        # Author information
        author=AUTHOR_NAME,
        author_email=AUTHOR_EMAIL,
        
        # Package discovery
        packages=find_packages(exclude=['tests*', 'docs*']),
        py_modules=['main', 'usage_examples'],
        
        # Python version requirement
        python_requires='>=3.8',
        
        # Dependencies
        install_requires=INSTALL_REQUIRES,
        extras_require=EXTRAS_REQUIRE,
        
        # Package data
        package_data=PACKAGE_DATA,
        data_files=DATA_FILES,
        include_package_data=True,
        
        # Entry points
        entry_points=ENTRY_POINTS,
        
        # PyPI metadata
        classifiers=CLASSIFIERS,
        keywords=' '.join(KEYWORDS),
        
        # Project URLs
        project_urls={
            'Bug Reports': f'{PACKAGE_URL}/issues',
            'Source': PACKAGE_URL,
            'Documentation': f'{PACKAGE_URL}/blob/main/README.md',
            'Download': f'{PACKAGE_URL}/releases',
        },
        
        # Additional options
        zip_safe=False,  # For compatibility with some tools
        platforms=['any'],
        
        # License
        license='MIT',
        
        # Options for building wheels
        options={
            'bdist_wheel': {
                'universal': False,  # Not compatible with Python 2
            },
        },
    )

if __name__ == '__main__':
    main()