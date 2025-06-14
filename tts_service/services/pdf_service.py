from typing import Iterator, List, Optional, AsyncIterator
from pathlib import Path
import pdfplumber
import nltk
from nltk.tokenize import sent_tokenize
import tempfile
import os
from pydantic import BaseModel
from pdfplumber.utils.exceptions import PdfminerException

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

    @classmethod
    def create_chunks_from_text(cls, text: str, page_number: int, max_chunk_size: int = 2000) -> Iterator['TextChunk']:
        """Split text into chunks respecting sentence boundaries"""
        if not text or not text.strip():
            return
        
        # Split into sentences, preserving punctuation
        sentences = []
        current = []
        for char in text:
            current.append(char)
            if char in '.!?' and len(current) > 1:
                sentences.append(''.join(current).strip())
                current = []
        if current:
            sentences.append(''.join(current).strip())
        
        if not sentences:
            return
        
        current_chunk = []
        current_length = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Calculate new length including the space that would be added
            sentence_length = len(sentence)
            new_length = current_length + (1 if current_chunk else 0) + sentence_length
            
            # If adding this sentence would exceed max_chunk_size and we have content,
            # yield the current chunk
            if new_length > max_chunk_size and current_chunk:
                yield cls(
                    text=" ".join(current_chunk),
                    page_number=page_number,
                    chunk_index=chunk_index,
                    start_position=(0, 0),
                    is_sentence_start=True
                )
                chunk_index += 1
                current_chunk = []
                current_length = 0
            
            # If a single sentence is longer than max_chunk_size, split it
            if sentence_length > max_chunk_size:
                # First yield any accumulated content
                if current_chunk:
                    yield cls(
                        text=" ".join(current_chunk),
                        page_number=page_number,
                        chunk_index=chunk_index,
                        start_position=(0, 0),
                        is_sentence_start=True
                    )
                    chunk_index += 1
                    current_chunk = []
                    current_length = 0
                
                # Split long sentence into words
                words = sentence.split()
                current_words = []
                current_word_length = 0
                
                for word in words:
                    word_length = len(word)
                    if current_word_length + word_length + (1 if current_words else 0) > max_chunk_size and current_words:
                        yield cls(
                            text=" ".join(current_words),
                            page_number=page_number,
                            chunk_index=chunk_index,
                            start_position=(0, 0),
                            is_sentence_start=True
                        )
                        chunk_index += 1
                        current_words = []
                        current_word_length = 0
                    
                    current_words.append(word)
                    current_word_length += word_length + (1 if current_word_length > 0 else 0)
                
                if current_words:
                    yield cls(
                        text=" ".join(current_words),
                        page_number=page_number,
                        chunk_index=chunk_index,
                        start_position=(0, 0),
                        is_sentence_start=True
                    )
                    chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_length += sentence_length + (1 if current_length > 0 else 0)
        
        # Yield any remaining text
        if current_chunk:
            yield cls(
                text=" ".join(current_chunk),
                page_number=page_number,
                chunk_index=chunk_index,
                start_position=(0, 0),
                is_sentence_start=True
            )

class PDFExtractionError(Exception):
    """Custom exception for PDF processing errors"""
    pass

def process_pdf_page(page: pdfplumber.page.Page, page_number: int, max_chunk_size: int = 2000) -> Iterator[TextChunk]:
    """Process a single PDF page and extract text chunks"""
    try:
        # Extract text with layout preservation
        text = page.extract_text(layout=True)
        if not text or not text.strip():
            return
        
        # Clean up the text - remove excessive whitespace but preserve sentence boundaries
        text = ' '.join(text.split())
        
        # Ensure we have at least one sentence
        if not any(c in text for c in '.!?'):
            text = text + '.'
        
        yield from TextChunk.create_chunks_from_text(
            text=text.strip(),
            page_number=page_number,
            max_chunk_size=max_chunk_size
        )
    except Exception as e:
        raise PDFExtractionError(f"Error processing page {page_number}: {str(e)}")

def process_pdf(pdf_path: str | Path, max_chunk_size: int = 2000) -> Iterator[TextChunk]:
    """Process PDF file and yield text chunks"""
    if not os.path.exists(pdf_path):
        raise PDFExtractionError(f"PDF file not found: {pdf_path}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise PDFExtractionError("PDF has no pages")
            
            for page_number, page in enumerate(pdf.pages, 1):
                try:
                    yield from process_pdf_page(
                        page=page,
                        page_number=page_number,
                        max_chunk_size=max_chunk_size
                    )
                except Exception as e:
                    raise PDFExtractionError(f"Error processing page {page_number}: {str(e)}")
    except PdfminerException as e:
        raise PDFExtractionError(f"Invalid PDF format: {str(e)}")
    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
        raise PDFExtractionError(f"Invalid PDF format: {str(e)}")
    except Exception as e:
        raise PDFExtractionError(f"Error processing PDF: {str(e)}")

class PDFProcessor:
    """Manages PDF processing state and temporary storage"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir or os.path.join(tempfile.gettempdir(), "pdf_processor")
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def process_uploaded_pdf(self, pdf_content: bytes, filename: str) -> AsyncIterator[TextChunk]:
        """Process uploaded PDF content"""
        if not pdf_content:
            raise PDFExtractionError("Empty PDF content")
            
        temp_path = os.path.join(self.temp_dir, f"temp_{filename}")
        try:
            with open(temp_path, "wb") as f:
                f.write(pdf_content)
            
            try:
                async for chunk in self._process_pdf_async(temp_path):
                    yield chunk
            except PDFExtractionError:
                raise
            except Exception as e:
                raise PDFExtractionError(f"Error processing PDF: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    async def _process_pdf_async(self, pdf_path: str) -> AsyncIterator[TextChunk]:
        """Process PDF file asynchronously"""
        for chunk in process_pdf(pdf_path):
            yield chunk 