from fastapi import Request
from fastapi.responses import JSONResponse
from tts_service.services.pdf_service import PDFExtractionError

async def pdf_extraction_error_handler(request: Request, exc: PDFExtractionError) -> JSONResponse:
    """Handle PDF extraction errors"""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic errors"""
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"}
    ) 