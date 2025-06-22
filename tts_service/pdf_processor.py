from typing import Iterator, List, TypedDict, Optional, AsyncIterator
from pathlib import Path
import pdfplumber
import nltk
from nltk.tokenize import sent_tokenize
import tempfile
import os
from pydantic import BaseModel

# Ensure NLTK data is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

class TextChunk(BaseModel):
    """Represents a chunk of text with its location information"""
    text: str
    page_number: int
    chunk_index: int
    start_position: tuple[float, float] = (0, 0)
    is_sentence_start: bool = True

class PDFExtractionError(Exception):
    """Custom exception for PDF processing errors"""
    pass

def create_chunks_from_text(text: str, page_number: int, max_chunk_size: int = 2000) -> Iterator[TextChunk]:
    """Split text into chunks respecting sentence boundaries"""
    if not text or not text.strip():
        return
    
    try:
        sentences = sent_tokenize(text.strip())
    except Exception as e:
        sentences = [text.strip()]
    
    current_sentences = []
    current_length = 0
    chunk_index = 0
    
    for sentence in sentences:
        # Calculate new length including the space that would be added
        sentence_length = len(sentence)
        new_length = current_length + (1 if current_sentences else 0) + sentence_length
        
        if new_length > max_chunk_size and current_sentences:
            # Yield current chunk
            yield TextChunk(
                text=" ".join(current_sentences),
                page_number=page_number,
                chunk_index=chunk_index,
                start_position=(0, 0),
                is_sentence_start=True
            )
            chunk_index += 1
            current_sentences = []
            current_length = 0
        
        current_sentences.append(sentence)
        current_length += sentence_length + (1 if current_length > 0 else 0)
        
        # If a single sentence is longer than max_chunk_size, force split it
        if current_length > max_chunk_size:
            words = sentence.split()
            current_chunk = []
            current_chunk_length = 0
            
            for word in words:
                word_length = len(word)
                if current_chunk_length + word_length + (1 if current_chunk else 0) > max_chunk_size and current_chunk:
                    yield TextChunk(
                        text=" ".join(current_chunk),
                        page_number=page_number,
                        chunk_index=chunk_index,
                        start_position=(0, 0),
                        is_sentence_start=True
                    )
                    chunk_index += 1
                    current_chunk = []
                    current_chunk_length = 0
                
                current_chunk.append(word)
                current_chunk_length += word_length + (1 if current_chunk_length > 0 else 0)
            
            if current_chunk:
                yield TextChunk(
                    text=" ".join(current_chunk),
                    page_number=page_number,
                    chunk_index=chunk_index,
                    start_position=(0, 0),
                    is_sentence_start=True
                )
                chunk_index += 1
            
            current_sentences = []
            current_length = 0
    
    # Yield any remaining text
    if current_sentences:
        yield TextChunk(
            text=" ".join(current_sentences),
            page_number=page_number,
            chunk_index=chunk_index,
            start_position=(0, 0),
            is_sentence_start=True
        )

def process_pdf_page(page: pdfplumber.page.Page, page_number: int, max_chunk_size: int = 2000) -> Iterator[TextChunk]:
    """Process a single PDF page and extract text chunks"""
    try:
        text = page.extract_text()
        if not text or not text.strip():
            return
        
        yield from create_chunks_from_text(
            text=text.strip(),
            page_number=page_number,
            max_chunk_size=max_chunk_size
        )
    except Exception as e:
        raise PDFExtractionError(f"Error processing page {page_number}: {str(e)}")

def process_pdf(pdf_path: str | Path, max_chunk_size: int = 2000) -> Iterator[TextChunk]:
    """
    Process PDF file and yield text chunks
    """
    if not os.path.exists(pdf_path):
        raise PDFExtractionError(f"PDF file not found: {pdf_path}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, 1):
                try:
                    yield from process_pdf_page(
                        page=page,
                        page_number=page_number,
                        max_chunk_size=max_chunk_size
                    )
                except Exception as e:
                    raise PDFExtractionError(f"Error processing page {page_number}: {str(e)}")
    except Exception as e:
        raise PDFExtractionError(f"Error processing PDF: {str(e)}")

class PDFProcessor:
    """Manages PDF processing state and temporary storage"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir or os.path.join(tempfile.gettempdir(), "pdf_processor")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def process_uploaded_pdf(self, pdf_content: bytes, filename: str) -> Iterator[TextChunk]:
        """
        Process uploaded PDF content
        """
        temp_path = os.path.join(self.temp_dir, f"temp_{filename}")
        try:
            with open(temp_path, "wb") as f:
                f.write(pdf_content)
            
            for chunk in process_pdf(temp_path):
                yield chunk
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path) 