"""
FastAPI backend application for video download service.
Provides endpoints for video preview and download functionality.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import os
import asyncio
from pathlib import Path

from utils.video_processor import video_processor

# Initialize FastAPI app
app = FastAPI(
    title="Video Download API",
    description="Professional video download service with dynamic quality selection",
    version="1.0.0"
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for downloads
downloads_path = Path("downloads")
downloads_path.mkdir(exist_ok=True)
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# Pydantic models for request/response
class VideoPreviewRequest(BaseModel):
    url: str

class VideoDownloadRequest(BaseModel):
    url: str
    quality: str
    format_id: Optional[str] = None

class VideoInfo(BaseModel):
    title: str
    thumbnail: str
    duration: int
    duration_formatted: str
    formats: list
    video_id: str
    uploader: str
    view_count: int
    like_count: int
    description: str

class DownloadResponse(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None
    filename: Optional[str] = None

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Video Download API",
        "version": "1.0.0",
        "endpoints": {
            "preview": "/preview - Get video information and available qualities",
            "download": "/download - Download video with specified quality"
        }
    }

@app.post("/preview", response_model=VideoInfo)
async def get_video_preview(request: VideoPreviewRequest):
    """
    Get video preview information including available qualities.
    
    Args:
        request: VideoPreviewRequest containing the YouTube URL
        
    Returns:
        VideoInfo: Video details and available formats
    """
    try:
        # Validate URL
        if not request.url or "youtube.com" not in request.url and "youtu.be" not in request.url:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        # Extract video information
        video_info = video_processor.get_video_info(request.url)
        
        return VideoInfo(**video_info)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/download", response_model=DownloadResponse)
async def download_video(request: VideoDownloadRequest, background_tasks: BackgroundTasks):
    """
    Download video with specified quality.
    
    Args:
        request: VideoDownloadRequest containing URL and quality selection
        background_tasks: FastAPI background tasks for async processing
        
    Returns:
        DownloadResponse: Download status and file information
    """
    try:
        # Validate request
        if not request.url or "youtube.com" not in request.url and "youtu.be" not in request.url:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        if not request.quality:
            raise HTTPException(status_code=400, detail="Quality selection required")
        
        # Download video
        file_path, filename = await video_processor.download_video(
            request.url, 
            request.quality, 
            request.format_id
        )
        
        # Generate download URL
        download_url = f"/downloads/{filename}"
        
        return DownloadResponse(
            success=True,
            message="Video downloaded successfully",
            download_url=download_url,
            filename=filename
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/downloads/{filename}")
async def serve_download(filename: str):
    """
    Serve downloaded video files.
    
    Args:
        filename: Name of the file to serve
        
    Returns:
        FileResponse: Video file for download
    """
    file_path = downloads_path / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {"status": "healthy", "service": "video-download-api"}

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Endpoint not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

