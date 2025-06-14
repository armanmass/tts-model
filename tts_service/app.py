import os
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tts_service.api.routes import pdf_routes, tts_routes
from tts_service.api.middleware.error_handlers import (
    pdf_extraction_error_handler,
    generic_error_handler
)
from tts_service.services.pdf_service import PDFExtractionError

# Constants
TEMP_DIR = os.path.join(tempfile.gettempdir(), "tts_service")
os.makedirs(TEMP_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app"""
    # Clean old files from temp directory
    for file in os.listdir(TEMP_DIR):
        try:
            os.remove(os.path.join(TEMP_DIR, file))
        except:
            pass
    yield

def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="Edge-TTS Service",
        description="A service for converting PDF documents to speech using Edge TTS",
        version="1.0.0",
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register error handlers
    app.add_exception_handler(PDFExtractionError, pdf_extraction_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # Include routers
    app.include_router(pdf_routes.router)
    app.include_router(tts_routes.router)

    return app

app = create_app()
