"""
Video processing utilities for YouTube video download and preview.
Handles video information extraction, quality selection, and download processing.
"""

import os
import json
import tempfile
import asyncio
from typing import Dict, List, Optional, Tuple
import yt_dlp
from pathlib import Path


class VideoProcessor:
    """Handles YouTube video processing operations."""
    
    def __init__(self):
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)
        
    def get_video_info(self, url: str) -> Dict:
        """
        Extract video information and available formats from YouTube URL.
        
        Args:
            url (str): YouTube video URL
            
        Returns:
            Dict: Video information including title, thumbnail, duration, and available formats
        """
        try:
            # Configure yt-dlp options for info extraction
            cookie_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'cookies.txt')
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': cookie_path,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video information
                info = ydl.extract_info(url, download=False)
                
                # Process available formats
                formats = self._process_formats(info.get('formats', []))
                
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'duration_formatted': self._format_duration(info.get('duration', 0)),
                    'formats': formats,
                    'video_id': info.get('id', ''),
                    'uploader': info.get('uploader', 'Unknown'),
                    'view_count': info.get('view_count', 0),
                    'like_count': info.get('like_count', 0),
                    'description': info.get('description', '')[:200] + '...' if info.get('description', '') else ''
                }
                
        except Exception as e:
            raise Exception(f"Error extracting video info: {str(e)}")
    
    def _process_formats(self, formats: List[Dict]) -> List[Dict]:
        """
        Process and categorize available video formats by quality.
        
        Args:
            formats (List[Dict]): Raw format list from yt-dlp
            
        Returns:
            List[Dict]: Processed formats with quality categories
        """
        processed_formats = []
        seen_qualities = set()
        
        # Filter and process formats
        for fmt in formats:
            if not fmt.get('url') or fmt.get('filesize') == 0:
                continue
                
            # Extract quality information
            height = fmt.get('height', 0)
            width = fmt.get('width', 0)
            fps = fmt.get('fps', 0)
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            
            # Skip audio-only formats for video downloads
            if vcodec == 'none':
                continue
                
            # Create quality label
            quality_label = self._create_quality_label(height, width, fps)
            
            # Skip if we already have this quality
            if quality_label in seen_qualities:
                continue
                
            seen_qualities.add(quality_label)
            
            # Calculate file size
            filesize = fmt.get('filesize', 0)
            if not filesize:
                filesize = fmt.get('filesize_approx', 0)
            
            processed_formats.append({
                'format_id': fmt.get('format_id', ''),
                'quality': quality_label,
                'height': height,
                'width': width,
                'fps': fps,
                'filesize': filesize,
                'filesize_formatted': self._format_filesize(filesize),
                'vcodec': vcodec,
                'acodec': acodec,
                'url': fmt.get('url', ''),
                'ext': fmt.get('ext', 'mp4')
            })
        
        # Sort by quality (height) in descending order
        processed_formats.sort(key=lambda x: x['height'], reverse=True)
        
        # Add "Highest Available" option
        if processed_formats:
            highest = processed_formats[0].copy()
            highest['quality'] = 'Highest Available'
            highest['format_id'] = 'best'
            processed_formats.insert(0, highest)
        
        return processed_formats
    
    def _create_quality_label(self, height: int, width: int, fps: int) -> str:
        """
        Create a human-readable quality label.
        
        Args:
            height (int): Video height
            width (int): Video width
            fps (int): Frame rate
            
        Returns:
            str: Quality label (e.g., "1080p", "720p 60fps")
        """
        if height >= 4320:
            return f"{height//1000}K"
        elif height >= 2160:
            return "4K"
        elif height >= 1440:
            return "2K"
        elif height >= 1080:
            return "1080p"
        elif height >= 720:
            return "720p"
        elif height >= 480:
            return "480p"
        elif height >= 360:
            return "360p"
        elif height >= 240:
            return "240p"
        elif height >= 144:
            return "144p"
        else:
            return f"{height}p"
    
    def _format_duration(self, seconds: int) -> str:
        """
        Format duration in seconds to human-readable format.
        
        Args:
            seconds (int): Duration in seconds
            
        Returns:
            str: Formatted duration (e.g., "3:45", "1:23:45")
        """
        if not seconds:
            return "Unknown"
            
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _format_filesize(self, bytes_size: int) -> str:
        """
        Format file size in bytes to human-readable format.
        
        Args:
            bytes_size (int): File size in bytes
            
        Returns:
            str: Formatted file size (e.g., "15.2 MB", "1.5 GB")
        """
        if not bytes_size:
            return "Unknown"
            
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"
    
    async def download_video(self, url: str, quality: str, format_id: str = None) -> Tuple[str, str]:
        """
        Download video with specified quality.
        
        Args:
            url (str): YouTube video URL
            quality (str): Quality label for display
            format_id (str): Format ID for download (optional)
            
        Returns:
            Tuple[str, str]: (file_path, filename)
        """
        try:
            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                # Configure yt-dlp options
                ydl_opts = {
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                }
                
                # Set format based on quality selection
                if quality == "Highest Available" or format_id == "best":
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                elif format_id:
                    ydl_opts['format'] = format_id
                else:
                    # Fallback to best quality
                    ydl_opts['format'] = 'best[ext=mp4]/best'
                
                # Download the video
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                
                # Move file to downloads directory
                if os.path.exists(filename):
                    final_path = os.path.join(self.download_dir, os.path.basename(filename))
                    os.rename(filename, final_path)
                    return final_path, os.path.basename(filename)
                else:
                    raise Exception("Download failed - file not found")
                    
        except Exception as e:
            raise Exception(f"Error downloading video: {str(e)}")


# Global instance
video_processor = VideoProcessor()
