import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import tempfile
from datetime import datetime, timezone
from typing import AsyncGenerator, List, AsyncIterator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from tts_service.app import app, PDFSession, pdf_sessions
from tts_service.pdf_processor import TextChunk
from tts_service.tests.test_pdf_processor import create_simple_pdf, temp_dir  # Import temp_dir fixture

# Test client fixture
@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)

# Mock PDF content fixture
@pytest.fixture
def mock_pdf_content(temp_dir):
    """Create a test PDF file and return its content"""
    pdf_path = os.path.join(temp_dir, "test.pdf")
    content = "This is a test sentence. This is another sentence."
    create_simple_pdf(pdf_path, content)
    
    with open(pdf_path, 'rb') as f:
        return f.read()

# Mock TTS synthesis fixture
@pytest.fixture
def mock_synthesize():
    """Mock the TTS synthesis function"""
    with patch('tts_service.app.synthesize', new_callable=AsyncMock) as mock:
        mock.return_value = b"mock_audio_data"
        yield mock

class MockPDFProcessor:
    """Mock PDF processor that properly implements async iteration"""
    def __init__(self, chunks: List[TextChunk], should_raise: bool = False):
        self.chunks = chunks
        self.should_raise = should_raise

    async def process_uploaded_pdf(self, content: bytes, filename: str) -> AsyncIterator[TextChunk]:
        """Process uploaded PDF content and yield chunks"""
        if self.should_raise:
            raise ValueError("Invalid PDF format")
        for chunk in self.chunks:
            yield chunk

# Mock PDF processor fixture
@pytest.fixture
def mock_pdf_processor():
    """Mock the PDF processor"""
    with patch('tts_service.app.PDFProcessor') as mock:
        # Create test chunks
        chunks = [
            TextChunk(text="Test chunk 1", page_number=1, chunk_index=0),
            TextChunk(text="Test chunk 2", page_number=1, chunk_index=1)
        ]
        # Create mock processor instance
        processor_instance = MockPDFProcessor(chunks)
        mock.return_value = processor_instance
        yield processor_instance

# Session cleanup fixture
@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Clean up sessions before and after each test"""
    pdf_sessions.clear()
    yield
    pdf_sessions.clear()

def get_utc_now() -> datetime:
    """Get current UTC time with timezone awareness"""
    return datetime.now(timezone.utc)

# Test PDF upload endpoint
@pytest.mark.asyncio
async def test_upload_pdf_success(client, mock_pdf_processor, mock_pdf_content):
    """Test successful PDF upload"""
    response = client.post(
        "/pdf/upload",
        files={"file": ("test.pdf", mock_pdf_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "total_chunks" in data
    assert data["total_chunks"] == 2
    assert data["session_id"] in pdf_sessions

def test_upload_pdf_invalid_file_type(client):
    """Test PDF upload with invalid file type"""
    response = client.post(
        "/pdf/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")}
    )
    
    assert response.status_code == 400
    assert "File must be a PDF" in response.json()["detail"]

@pytest.mark.asyncio
async def test_upload_pdf_empty_content(client, mock_pdf_processor):
    """Test PDF upload with empty content"""
    # Create a mock processor that yields no chunks
    mock_pdf_processor.chunks = []
    
    response = client.post(
        "/pdf/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    
    assert response.status_code == 400
    assert "Empty PDF file" in response.json()["detail"]

# Test chunk reading endpoint
@pytest.mark.asyncio
async def test_read_chunk_success(client, mock_synthesize):
    """Test successful chunk reading"""
    # Create a test session
    session_id = "test-session"
    chunks = [
        TextChunk(text="Test chunk 1", page_number=1, chunk_index=0),
        TextChunk(text="Test chunk 2", page_number=1, chunk_index=1)
    ]
    pdf_sessions[session_id] = PDFSession(
        id=session_id,
        chunks=chunks,
        current_index=0,
        last_accessed=get_utc_now()
    )
    
    response = client.get(f"/pdf/{session_id}/read/0")
    
    assert response.status_code == 200
    assert response.content == b"mock_audio_data"
    assert response.headers["content-type"] == "audio/mpeg"
    mock_synthesize.assert_called_once_with("Test chunk 1")

def test_read_chunk_invalid_session(client):
    """Test reading chunk with invalid session"""
    response = client.get("/pdf/invalid-session/read/0")
    
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]

def test_read_chunk_invalid_index(client):
    """Test reading chunk with invalid index"""
    # Create a test session
    session_id = "test-session"
    chunks = [TextChunk(text="Test chunk", page_number=1, chunk_index=0)]
    pdf_sessions[session_id] = PDFSession(
        id=session_id,
        chunks=chunks,
        current_index=0,
        last_accessed=get_utc_now()
    )
    
    response = client.get(f"/pdf/{session_id}/read/1")
    
    assert response.status_code == 400
    assert "Invalid chunk index" in response.json()["detail"]

# Test status endpoint
def test_get_status_success(client):
    """Test successful status retrieval"""
    # Create a test session
    session_id = "test-session"
    chunks = [
        TextChunk(text="Test chunk 1", page_number=1, chunk_index=0),
        TextChunk(text="Test chunk 2", page_number=2, chunk_index=1)
    ]
    pdf_sessions[session_id] = PDFSession(
        id=session_id,
        chunks=chunks,
        current_index=1,
        last_accessed=get_utc_now()
    )
    
    response = client.get(f"/pdf/{session_id}/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["current_index"] == 1
    assert data["total_chunks"] == 2
    assert data["current_page"] == 2

def test_get_status_invalid_session(client):
    """Test status retrieval with invalid session"""
    response = client.get("/pdf/invalid-session/status")
    
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]

# Test TTS endpoint
@pytest.mark.asyncio
async def test_synthesize_text_success(client, mock_synthesize):
    """Test successful text synthesis"""
    response = client.post(
        "/tts",
        json={
            "text": "Test text",
            "voice": "en-US-AriaNeural",
            "rate": "+0%",
            "volume": "+0%"
        }
    )
    
    assert response.status_code == 200
    assert response.content == b"mock_audio_data"
    assert response.headers["content-type"] == "audio/mpeg"
    mock_synthesize.assert_called_once_with(
        "Test text",
        voice="en-US-AriaNeural",
        rate="+0%",
        volume="+0%"
    )

def test_synthesize_text_empty(client):
    """Test text synthesis with empty text"""
    response = client.post(
        "/tts",
        json={
            "text": "",
            "voice": "en-US-AriaNeural",
            "rate": "+0%",
            "volume": "+0%"
        }
    )
    
    assert response.status_code == 422  # Validation error

@pytest.mark.asyncio
async def test_synthesize_text_error(client, mock_synthesize):
    """Test text synthesis with synthesis error"""
    mock_synthesize.side_effect = Exception("Synthesis failed")
    
    response = client.post(
        "/tts",
        json={
            "text": "Test text",
            "voice": "en-US-AriaNeural",
            "rate": "+0%",
            "volume": "+0%"
        }
    )
    
    assert response.status_code == 500
    assert "Synthesis failed" in response.json()["detail"]

# Additional test fixtures
@pytest.fixture
def large_pdf_content(temp_dir) -> bytes:
    """Create a large PDF file for testing memory management"""
    pdf_path = os.path.join(temp_dir, "large.pdf")
    # Create a large text with known size
    large_text = "Test sentence. " * 1000  # Will be > 15KB
    create_simple_pdf(pdf_path, large_text)
    
    with open(pdf_path, 'rb') as f:
        return f.read()

@pytest.fixture
def special_chars_pdf_content(temp_dir) -> bytes:
    """Create a PDF with special characters and Unicode"""
    pdf_path = os.path.join(temp_dir, "special.pdf")
    text = "Special chars: áéíóú ñ € © ™ • — 你好 こんにちは"
    create_simple_pdf(pdf_path, text)
    
    with open(pdf_path, 'rb') as f:
        return f.read()

@pytest.fixture
def multipage_pdf_content(temp_dir) -> bytes:
    """Create a multi-page PDF"""
    pdf_path = os.path.join(temp_dir, "multipage.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Page 1
    c.drawString(50, 750, "Page one content.")
    c.showPage()
    
    # Page 2
    c.drawString(50, 750, "Page two content.")
    c.showPage()
    
    # Page 3
    c.drawString(50, 750, "Page three content.")
    c.save()
    
    with open(pdf_path, 'rb') as f:
        return f.read()

# Additional test cases
@pytest.mark.asyncio
async def test_upload_large_pdf(client, mock_pdf_processor, large_pdf_content):
    """Test uploading a large PDF file"""
    # Configure mock to return chunks for large content
    chunks = [
        TextChunk(text="Large chunk 1", page_number=1, chunk_index=0),
        TextChunk(text="Large chunk 2", page_number=1, chunk_index=1),
        TextChunk(text="Large chunk 3", page_number=2, chunk_index=2)
    ]
    mock_pdf_processor.chunks = chunks
    
    response = client.post(
        "/pdf/upload",
        files={"file": ("large.pdf", large_pdf_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_chunks"] == 3

@pytest.mark.asyncio
async def test_upload_special_chars_pdf(client, mock_pdf_processor, special_chars_pdf_content):
    """Test uploading PDF with special characters"""
    chunks = [
        TextChunk(text="Special chars: áéíóú ñ € © ™ • — 你好 こんにちは", 
                 page_number=1, chunk_index=0)
    ]
    mock_pdf_processor.chunks = chunks
    
    response = client.post(
        "/pdf/upload",
        files={"file": ("special.pdf", special_chars_pdf_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_chunks"] == 1
    
    # Verify the chunk content
    session_id = data["session_id"]
    session = pdf_sessions[session_id]
    assert "你好" in session.chunks[0].text
    assert "こんにちは" in session.chunks[0].text

@pytest.mark.asyncio
async def test_upload_multipage_pdf(client, mock_pdf_processor, multipage_pdf_content):
    """Test uploading a multi-page PDF"""
    chunks = [
        TextChunk(text="Page one content.", page_number=1, chunk_index=0),
        TextChunk(text="Page two content.", page_number=2, chunk_index=1),
        TextChunk(text="Page three content.", page_number=3, chunk_index=2)
    ]
    mock_pdf_processor.chunks = chunks
    
    response = client.post(
        "/pdf/upload",
        files={"file": ("multipage.pdf", multipage_pdf_content, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_chunks"] == 3
    
    # Verify page numbers
    session_id = data["session_id"]
    session = pdf_sessions[session_id]
    assert session.chunks[0].page_number == 1
    assert session.chunks[1].page_number == 2
    assert session.chunks[2].page_number == 3

@pytest.mark.asyncio
async def test_concurrent_session_access(client, mock_pdf_processor, mock_pdf_content):
    """Test concurrent access to the same session"""
    import asyncio
    
    # First create a session
    response = client.post(
        "/pdf/upload",
        files={"file": ("test.pdf", mock_pdf_content, "application/pdf")}
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    
    # Simulate concurrent access
    async def read_chunk(index: int):
        return client.get(f"/pdf/{session_id}/read/{index}")
    
    # Read chunks concurrently
    tasks = [read_chunk(i) for i in range(2)]
    responses = await asyncio.gather(*tasks)
    
    # Verify all requests succeeded
    assert all(r.status_code == 200 for r in responses)
    assert all(r.headers["content-type"] == "audio/mpeg" for r in responses)

@pytest.mark.asyncio
async def test_tts_special_chars(client, mock_synthesize):
    """Test TTS synthesis with special characters"""
    text = "Special chars: áéíóú ñ € © ™ • — 你好 こんにちは"
    voice = "en-US-AriaNeural"
    rate = "+0%"
    volume = "+0%"
    
    response = client.post(
        "/tts",
        json={
            "text": text,
            "voice": voice,
            "rate": rate,
            "volume": volume
        }
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    mock_synthesize.assert_called_once_with(
        text,
        voice=voice,
        rate=rate,
        volume=volume
    )

@pytest.mark.asyncio
async def test_tts_voice_configurations(client, mock_synthesize):
    """Test TTS synthesis with different voice configurations"""
    test_cases = [
        {"voice": "en-US-GuyNeural", "rate": "+50%", "volume": "+20%"},
        {"voice": "en-GB-SoniaNeural", "rate": "-20%", "volume": "-10%"},
        {"voice": "en-AU-NatashaNeural", "rate": "+0%", "volume": "+0%"}
    ]
    
    for config in test_cases:
        response = client.post(
            "/tts",
            json={
                "text": "Test text",
                **config
            }
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        mock_synthesize.assert_called_with(
            "Test text",
            voice=config["voice"],
            rate=config["rate"],
            volume=config["volume"]
        )

@pytest.mark.asyncio
async def test_corrupted_pdf_handling(client, mock_pdf_processor):
    """Test handling of corrupted PDF files"""
    # Configure mock to raise error for corrupted PDFs
    mock_pdf_processor.should_raise = True
    
    # Create corrupted PDF content
    corrupted_content = b"%PDF-1.3\nThis is not a valid PDF file"
    
    response = client.post(
        "/pdf/upload",
        files={"file": ("corrupted.pdf", corrupted_content, "application/pdf")}
    )
    
    assert response.status_code == 400
    assert "Error processing PDF" in response.json()["detail"] 