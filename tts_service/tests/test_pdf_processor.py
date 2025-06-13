import os
import pytest
import tempfile
from pathlib import Path
from typing import Iterator, List
import asyncio

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from tts_service.pdf_processor import (
    PDFProcessor,
    TextChunk,
    process_pdf,
    create_chunks_from_text,
    PDFExtractionError
)

def create_simple_pdf(output_path: str, content: str) -> None:
    """Create a simple PDF file with basic content"""
    c = canvas.Canvas(output_path, pagesize=letter)
    # Position text higher on the page and use a standard font
    c.setFont("Helvetica", 12)
    # Break content into lines to avoid text overflow
    y_position = 750  # Start near top of page
    for line in content.split('\n'):
        c.drawString(50, y_position, line)
        y_position -= 15
    c.save()

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(temp_dir)

@pytest.fixture
def pdf_processor(temp_dir):
    """Create a PDFProcessor instance"""
    return PDFProcessor(temp_dir=temp_dir)

def test_create_chunks_from_text():
    """Test basic text chunking"""
    text = "First sentence. Second sentence. Third sentence."
    chunks = list(create_chunks_from_text(text, page_number=1, max_chunk_size=100))
    
    assert len(chunks) > 0
    assert isinstance(chunks[0], TextChunk)
    assert chunks[0].text.startswith("First sentence")

def test_basic_pdf_processing(temp_dir):
    """Test basic PDF processing with simple content"""
    pdf_path = os.path.join(temp_dir, "test.pdf")
    content = "This is a test sentence."
    
    # Create PDF
    create_simple_pdf(pdf_path, content)
    assert os.path.exists(pdf_path)
    
    # Process PDF
    chunks = list(process_pdf(pdf_path))
    assert len(chunks) > 0
    assert chunks[0].text.strip() == content.strip()

@pytest.mark.asyncio
async def test_pdf_upload(pdf_processor, temp_dir):
    """Test PDF upload processing"""
    # Create test PDF
    pdf_path = os.path.join(temp_dir, "upload_test.pdf")
    content = "Upload test content."
    create_simple_pdf(pdf_path, content)
    
    # Read PDF content
    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
    
    # Process uploaded content
    chunks = []
    async for chunk in pdf_processor.process_uploaded_pdf(pdf_content, "test.pdf"):
        chunks.append(chunk)
    
    assert len(chunks) > 0
    assert chunks[0].text.strip() == content.strip()

def test_multi_page_pdf(temp_dir):
    """Test processing multi-page PDF"""
    pdf_path = os.path.join(temp_dir, "multipage.pdf")
    
    # Create multi-page PDF
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Page 1
    c.drawString(50, 750, "Page one content.")
    c.showPage()
    
    # Page 2
    c.drawString(50, 750, "Page two content.")
    c.save()
    
    # Process PDF
    chunks = list(process_pdf(pdf_path))
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2

def test_empty_content():
    """Test handling of empty content"""
    chunks = list(create_chunks_from_text("", page_number=1))
    assert len(chunks) == 0

def test_large_content_chunking():
    """Test chunking of large content"""
    # Create a text with known size
    sentence = "This is a test sentence that has exactly sixty characters in it."  # 60 chars
    long_text = " ".join([sentence] * 5)  # Will be > 300 chars with spaces
    max_chunk_size = 100
    
    chunks = list(create_chunks_from_text(long_text, page_number=1, max_chunk_size=max_chunk_size))
    
    # Verify we got multiple chunks
    assert len(chunks) > 1, f"Expected multiple chunks but got {len(chunks)}"
    
    # Verify each chunk is within size limit
    for i, chunk in enumerate(chunks):
        assert len(chunk.text) <= max_chunk_size, \
            f"Chunk {i} exceeds max size: {len(chunk.text)} > {max_chunk_size}"
    
    # Verify all text is preserved (ignoring extra spaces)
    original_words = set(long_text.split())
    chunk_words = set(" ".join(chunk.text for chunk in chunks).split())
    assert original_words == chunk_words, "Some content was lost in chunking"
    
    # Verify chunk indexing
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i, f"Wrong chunk index: {chunk.chunk_index} != {i}"

def test_very_long_sentence():
    """Test handling of sentences longer than max_chunk_size"""
    # Create a very long sentence
    long_sentence = "word " * 30  # Will be 150 characters with spaces
    max_chunk_size = 50
    
    chunks = list(create_chunks_from_text(long_sentence, page_number=1, max_chunk_size=max_chunk_size))
    
    assert len(chunks) > 1, "Long sentence should be split into multiple chunks"
    assert all(len(chunk.text) <= max_chunk_size for chunk in chunks), \
        "All chunks should be within size limit"
    
    # Verify content preservation
    original_words = set(long_sentence.split())
    chunk_words = set(" ".join(chunk.text for chunk in chunks).split())
    assert original_words == chunk_words, "Some words were lost in chunking"

def test_malformed_pdf(pdf_processor, temp_dir):
    """Test handling of malformed PDF content"""
    # Create invalid PDF content
    invalid_pdf = b"This is not a valid PDF file"
    
    with pytest.raises(PDFExtractionError):
        list(process_pdf(os.path.join(temp_dir, "invalid.pdf")))

def test_pdf_with_images(temp_dir):
    """Test PDF with images (should extract only text)"""
    pdf_path = os.path.join(temp_dir, "with_images.pdf")
    
    # Create PDF with text and a dummy image placeholder
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(50, 750, "Text before image.")
    # Add some space for where image would be
    c.drawString(50, 700, "Text after image.")
    c.save()
    
    chunks = list(process_pdf(pdf_path))
    assert any("Text before image" in chunk.text for chunk in chunks)
    assert any("Text after image" in chunk.text for chunk in chunks)

def test_pdf_with_special_characters():
    """Test handling of special characters and Unicode"""
    text = "Special characters: áéíóú ñ € © ™ • —"
    chunks = list(create_chunks_from_text(text, page_number=1))
    assert chunks[0].text == text, "Special characters should be preserved"

def test_concurrent_processing(pdf_processor, temp_dir):
    """Test concurrent processing of multiple PDFs"""
    import asyncio
    
    async def process_one(content: bytes, filename: str):
        chunks = []
        async for chunk in pdf_processor.process_uploaded_pdf(content, filename):
            chunks.append(chunk)
        return chunks
    
    async def test_concurrent():
        # Create multiple test PDFs
        pdfs = []
        for i in range(3):
            pdf_path = os.path.join(temp_dir, f"test{i}.pdf")
            content = f"Test content for PDF {i}"
            create_simple_pdf(pdf_path, content)
            with open(pdf_path, 'rb') as f:
                pdfs.append((f.read(), f"test{i}.pdf"))
        
        # Process PDFs concurrently
        tasks = [process_one(content, filename) for content, filename in pdfs]
        results = await asyncio.gather(*tasks)
        
        # Verify results
        assert len(results) == 3
        for i, chunks in enumerate(results):
            assert len(chunks) > 0
            assert f"Test content for PDF {i}" in chunks[0].text
    
    asyncio.run(test_concurrent())

def test_large_pdf_memory_management(pdf_processor, temp_dir):
    """Test memory management with very large PDFs"""
    import psutil
    import os
    
    # Create a large PDF
    pdf_path = os.path.join(temp_dir, "large.pdf")
    large_text = "Test sentence. " * 1000
    create_simple_pdf(pdf_path, large_text)
    
    # Measure memory before
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss
    
    # Process PDF
    chunks = list(process_pdf(pdf_path))
    
    # Measure memory after
    mem_after = process.memory_info().rss
    
    # Check memory usage didn't grow too much
    # Allow for some overhead but shouldn't be more than 50MB
    assert mem_after - mem_before < 50 * 1024 * 1024, "Memory usage grew too much"
    assert len(chunks) > 0

def test_pdf_with_tables(temp_dir):
    """Test handling of PDFs with table-like content"""
    pdf_path = os.path.join(temp_dir, "table.pdf")
    
    # Create PDF with table-like content
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    y = 750
    for i in range(3):
        x = 50
        for j in range(3):
            c.drawString(x, y, f"Cell {i},{j}")
            x += 100
        y -= 20
    c.save()
    
    chunks = list(process_pdf(pdf_path))
    assert len(chunks) > 0
    # Verify some cell content is present
    assert any("Cell" in chunk.text for chunk in chunks)

def test_empty_pages_handling(temp_dir):
    """Test handling of PDFs with empty pages"""
    pdf_path = os.path.join(temp_dir, "empty_pages.pdf")
    
    c = canvas.Canvas(pdf_path, pagesize=letter)
    # Page 1 - empty
    c.showPage()
    # Page 2 - with content
    c.drawString(50, 750, "Content on page 2")
    c.showPage()
    # Page 3 - empty
    c.showPage()
    c.save()
    
    chunks = list(process_pdf(pdf_path))
    assert len(chunks) > 0
    assert all(chunk.page_number == 2 for chunk in chunks)
    assert "Content on page 2" in chunks[0].text

@pytest.mark.asyncio
async def test_pdf_cleanup_on_error(pdf_processor, temp_dir):
    """Test temporary file cleanup when processing fails"""
    # Create invalid PDF content
    invalid_pdf = b"Invalid PDF content"
    
    # Count files before
    files_before = len(os.listdir(pdf_processor.temp_dir))
    
    # Process should fail but cleanup
    with pytest.raises(PDFExtractionError):
        async for _ in pdf_processor.process_uploaded_pdf(invalid_pdf, "invalid.pdf"):
            pass
    
    # Verify no temporary files were left
    files_after = len(os.listdir(pdf_processor.temp_dir))
    assert files_before == files_after, "Temporary files were not cleaned up" 