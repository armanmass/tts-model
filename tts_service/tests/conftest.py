import pytest
import sys
from pathlib import Path
import nltk
import os

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def pytest_configure(config):
    """Download NLTK data before running tests"""
    # Create data directory if it doesn't exist
    nltk_data_dir = os.path.join(os.path.dirname(__file__), 'nltk_data')
    os.makedirs(nltk_data_dir, exist_ok=True)
    
    # Set NLTK data path
    nltk.data.path.append(nltk_data_dir)
    
    # Download required NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', download_dir=nltk_data_dir, quiet=True)

def pytest_sessionstart(session):
    """Download NLTK data before running any tests"""
    # Download punkt tokenizer data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True) 