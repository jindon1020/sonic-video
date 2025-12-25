"""
Image Processor for handling static images and Apple Live Photos.

Live Photo consists of:
- A HEIC/JPG image (the still frame)
- A MOV video file (the motion content, typically 1.5-3 seconds)

For web playback, we convert Live Photos to short video clips.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from PIL import Image
import cv2


class ImageProcessor:
    """Handles static images and Apple Live Photos for the video editing pipeline."""
    
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.gif'}
    LIVE_PHOTO_VIDEO_EXTENSIONS = {'.mov', '.mp4'}
    
    def __init__(self, output_dir: str = "app/static/processed/images"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def is_supported_image(self, filename: str) -> bool:
        """Check if file is a supported image format."""
        ext = Path(filename).suffix.lower()
        return ext in self.SUPPORTED_IMAGE_EXTENSIONS
    
    def is_live_photo_video(self, filename: str) -> bool:
        """Check if file could be a Live Photo video component."""
        ext = Path(filename).suffix.lower()
        return ext in self.LIVE_PHOTO_VIDEO_EXTENSIONS
    
    def convert_heic_to_jpg(self, heic_path: str) -> str:
        """
        Convert HEIC/HEIF image to JPEG for broader compatibility.
        Uses PIL with pillow-heif plugin or sips (macOS).
        """
        output_path = heic_path.rsplit('.', 1)[0] + '_converted.jpg'
        
        # Try using sips on macOS (built-in and fast)
        try:
            subprocess.run(
                ['sips', '-s', 'format', 'jpeg', heic_path, '--out', output_path],
                check=True, capture_output=True
            )
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Fallback: try pillow-heif
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
            img = Image.open(heic_path)
            img.convert('RGB').save(output_path, 'JPEG', quality=95)
            return output_path
        except ImportError:
            print("⚠️ pillow-heif not installed. Run: pip install pillow-heif")
            return heic_path
        except Exception as e:
            print(f"⚠️ HEIC conversion failed: {e}")
            return heic_path
    
    def create_video_from_image(
        self,
        image_path: str,
        duration: float = 3.0,
        output_path: Optional[str] = None,
        add_motion: bool = True
    ) -> str:
        """
        Create a video clip from a static image.
        
        Args:
            image_path: Path to the source image
            duration: Duration of the output video in seconds
            output_path: Optional output path
            add_motion: Whether to add subtle Ken Burns effect (zoom/pan)
        
        Returns:
            Path to the generated video
        """
        if output_path is None:
            base_name = Path(image_path).stem
            output_path = os.path.join(self.output_dir, f"{base_name}_video.mp4")
        
        # Handle HEIC conversion
        if Path(image_path).suffix.lower() in {'.heic', '.heif'}:
            image_path = self.convert_heic_to_jpg(image_path)
        
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")
        
        height, width = img.shape[:2]
        
        # Target video dimensions (maintain aspect, max 1080p)
        max_dim = 1920
        if width > max_dim or height > max_dim:
            scale = max_dim / max(width, height)
            width = int(width * scale)
            height = int(height * scale)
            img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
        
        # Ensure even dimensions for H.264
        width = width - (width % 2)
        height = height - (height % 2)
        img = cv2.resize(img, (width, height))
        
        fps = 30
        frame_count = int(duration * fps)
        
        # Video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        if add_motion:
            # Ken Burns effect: subtle zoom-in over duration
            start_scale = 1.0
            end_scale = 1.08  # 8% zoom
            
            for i in range(frame_count):
                progress = i / frame_count
                scale = start_scale + (end_scale - start_scale) * progress
                
                # Calculate crop region for zoom effect
                new_w = int(width / scale)
                new_h = int(height / scale)
                x1 = (width - new_w) // 2
                y1 = (height - new_h) // 2
                x2 = x1 + new_w
                y2 = y1 + new_h
                
                # Crop and resize back
                cropped = img[y1:y2, x1:x2]
                frame = cv2.resize(cropped, (width, height), interpolation=cv2.INTER_LANCZOS4)
                out.write(frame)
        else:
            # Static video - just repeat the frame
            for _ in range(frame_count):
                out.write(img)
        
        out.release()
        
        # Re-encode with H.264 for better compatibility
        final_output = output_path.replace('.mp4', '_h264.mp4')
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', output_path,
                '-c:v', 'libx264', '-preset', 'fast',
                '-crf', '23', '-pix_fmt', 'yuv420p',
                final_output
            ], check=True, capture_output=True)
            os.remove(output_path)
            os.rename(final_output, output_path)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Keep the mp4v version if ffmpeg fails
            pass
        
        return output_path
    
    def process_live_photo(
        self,
        image_path: str,
        video_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Process Apple Live Photo (image + video pair).
        
        Combines the still image and motion video into a seamless clip.
        
        Args:
            image_path: Path to the still image (HEIC/JPG)
            video_path: Path to the motion video (MOV)
            output_path: Optional output path
        
        Returns:
            Path to the processed video
        """
        if output_path is None:
            base_name = Path(image_path).stem
            output_path = os.path.join(self.output_dir, f"{base_name}_live.mp4")
        
        # The MOV file IS the Live Photo video - we just need to convert it
        # to a more compatible format (H.264 MP4)
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', video_path,
                '-c:v', 'libx264', '-preset', 'fast',
                '-crf', '23', '-pix_fmt', 'yuv420p',
                '-an',  # Remove audio (Live Photos have motion audio we don't need)
                output_path
            ], check=True, capture_output=True)
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"⚠️ Live Photo conversion failed: {e}")
            # Fallback: copy the MOV as-is
            shutil.copy(video_path, output_path.replace('.mp4', '.mov'))
            return output_path.replace('.mp4', '.mov')
    
    def auto_detect_live_photo_pair(
        self,
        files: List[str]
    ) -> List[Dict]:
        """
        Automatically detect Live Photo pairs from a list of files.
        
        Live Photos typically have matching filenames:
        - IMG_1234.HEIC (still image)
        - IMG_1234.MOV (motion video)
        
        Args:
            files: List of file paths
        
        Returns:
            List of detected pairs with metadata
        """
        # Group files by base name
        file_groups = {}
        for f in files:
            path = Path(f)
            base_name = path.stem
            ext = path.suffix.lower()
            
            if base_name not in file_groups:
                file_groups[base_name] = {'image': None, 'video': None}
            
            if ext in self.SUPPORTED_IMAGE_EXTENSIONS:
                file_groups[base_name]['image'] = f
            elif ext in self.LIVE_PHOTO_VIDEO_EXTENSIONS:
                file_groups[base_name]['video'] = f
        
        results = []
        for base_name, group in file_groups.items():
            if group['image'] and group['video']:
                # This is likely a Live Photo pair
                results.append({
                    'type': 'live_photo',
                    'image': group['image'],
                    'video': group['video'],
                    'base_name': base_name
                })
            elif group['image']:
                # Standalone image
                results.append({
                    'type': 'image',
                    'image': group['image'],
                    'base_name': base_name
                })
            elif group['video']:
                # Standalone video - not handled by ImageProcessor
                results.append({
                    'type': 'video',
                    'video': group['video'],
                    'base_name': base_name
                })
        
        return results
    
    def extract_thumbnail(
        self,
        image_path: str,
        output_path: str,
        max_size: Tuple[int, int] = (300, 300)
    ) -> bool:
        """
        Generate a thumbnail from an image.
        
        Args:
            image_path: Source image path
            output_path: Output thumbnail path
            max_size: Maximum thumbnail dimensions
        
        Returns:
            True if successful
        """
        try:
            # Handle HEIC
            if Path(image_path).suffix.lower() in {'.heic', '.heif'}:
                image_path = self.convert_heic_to_jpg(image_path)
            
            img = Image.open(image_path)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.convert('RGB').save(output_path, 'JPEG', quality=85)
            return True
        except Exception as e:
            print(f"⚠️ Thumbnail generation failed: {e}")
            return False
    
    def get_image_info(self, image_path: str) -> Dict:
        """
        Get metadata about an image file.
        
        Returns:
            Dictionary with image metadata
        """
        try:
            if Path(image_path).suffix.lower() in {'.heic', '.heif'}:
                converted = self.convert_heic_to_jpg(image_path)
                img = Image.open(converted)
            else:
                img = Image.open(image_path)
            
            return {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': os.path.getsize(image_path)
            }
        except Exception as e:
            return {'error': str(e)}
