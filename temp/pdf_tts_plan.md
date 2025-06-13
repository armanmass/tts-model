# PDF TTS Service Implementation Plan

## 1. Current State Overview
- FastAPI service with Edge TTS integration
- Supports text-to-speech synthesis with voice, rate, and volume controls
- Handles text chunking for long inputs (>2000 chars)
- Uses temporary file storage for audio files
- Simple REST API with /synth and /audio endpoints

## 2. Final State Overview
- PDF upload and processing support
- Sequential reading with navigation capabilities
- Maintain existing text-to-speech functionality
- Support for jumping to specific sentences/chunks
- Efficient PDF processing with streaming support
- Clean separation of concerns between PDF processing and TTS

## 3. Files to Change

### New Files:
1. `tts_service/pdf_processor.py`
   - PDF text extraction and chunking
   - Sentence boundary detection
   - Navigation point tracking
   - Streaming PDF processing

2. `tts_service/models.py`
   - PDF processing request/response models
   - Navigation state models
   - PDF metadata models

3. `tts_service/pdf_storage.py`
   - PDF file storage management
   - Temporary file handling
   - Cleanup routines

### Modified Files:
1. `tts_service/app.py`
   - Add PDF upload endpoint
   - Add PDF navigation endpoints
   - Extend existing TTS endpoints for PDF support
   - Add PDF session management

2. `requirements.txt`
   - Add PDF processing dependencies (PyPDF2 or pdfplumber)
   - Add file handling utilities

## 4. Implementation Checklist

### Core PDF Processing
- [ ] Create PDF processor module with streaming support
  - [ ] Implement PDF text extraction
  - [ ] Add sentence boundary detection
  - [ ] Create chunk management system
  - [ ] Add navigation point tracking

### Data Models
- [ ] Define PDF processing request/response models
  - [ ] PDF upload request model
  - [ ] Navigation state model
  - [ ] PDF metadata model
  - [ ] Session management model

### Storage Management
- [ ] Implement PDF storage system
  - [ ] Create temporary storage for PDFs
  - [ ] Add cleanup routines
  - [ ] Implement file rotation policy

### API Endpoints
- [ ] Add new API endpoints
  - [ ] PDF upload endpoint
  - [ ] PDF navigation endpoint
  - [ ] PDF session management endpoint
  - [ ] Extend TTS endpoint for PDF support

### Integration
- [ ] Integrate PDF processing with existing TTS
  - [ ] Connect PDF chunks to TTS synthesis
  - [ ] Implement navigation controls
  - [ ] Add session management

### Testing & Documentation
- [ ] Add unit tests for new components
- [ ] Add integration tests
- [ ] Update API documentation
- [ ] Add example usage

## Additional Ideas (Not in Initial Implementation)
- PDF metadata extraction
- OCR support for scanned PDFs
- Progress tracking and resume capabilities
- Batch processing for multiple PDFs
- PDF text highlighting during playback
- Support for other document formats (DOCX, TXT)
- Caching system for processed PDFs
- User preferences for reading speed/voice per document 