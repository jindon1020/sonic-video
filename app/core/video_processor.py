import os
from scenedetect import detect, ContentDetector, split_video_ffmpeg
import cv2
import gc

class VideoProcessor:
    """Video processor with batch processing and memory management for large files."""
    
    # Processing limits to prevent memory overflow
    MAX_SCENES_TOTAL = 300  # Max scenes to detect (increased from 100)
    SCENES_PER_BATCH = 20   # Process scenes in batches of 20
    UNIFORM_SAMPLE = True   # Use uniform sampling instead of first-N
    
    def __init__(self, output_dir="app/static/processed/shots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def split_scenes(self, video_path):
        """
        Detects scenes with performance optimization and memory management.
        For large videos, uses uniform sampling to get representative scenes.
        """
        print(f"Analyzing scenes for: {video_path}")
        
        # Get video info first
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        cap.release()
        
        print(f"📊 视频信息: 时长={duration:.1f}s, 帧数={frame_count}, 大小={file_size_mb:.1f}MB")
        
        # Detect scenes
        scene_list = detect(video_path, ContentDetector(threshold=27.0)) 
        
        # Fallback for single-shot videos
        if not scene_list:
            print(f"ℹ️ 未检测到场景切换，将进行等距切分...")
            from scenedetect import FrameTimecode
            seg_duration = 5.0
            num_segments = int(duration // seg_duration)
            if num_segments <= 1:
                scene_list = [(FrameTimecode(0, fps), FrameTimecode(frame_count, fps))]
            else:
                for i in range(num_segments):
                    start = i * seg_duration
                    end = (i + 1) * seg_duration
                    scene_list.append((FrameTimecode(start, fps), FrameTimecode(end, fps)))
                if duration % seg_duration >= 1.0:
                    scene_list.append((FrameTimecode(num_segments * seg_duration, fps), FrameTimecode(frame_count, fps)))
        
        original_count = len(scene_list)
        print(f"🎬 检测到 {original_count} 个场景")
        
        # Apply smart sampling for large videos
        if original_count > self.MAX_SCENES_TOTAL:
            if self.UNIFORM_SAMPLE:
                # Uniform sampling - take evenly distributed scenes
                step = original_count / self.MAX_SCENES_TOTAL
                scene_list = [scene_list[int(i * step)] for i in range(self.MAX_SCENES_TOTAL)]
                print(f"⚠️ 场景过多，已均匀采样 {self.MAX_SCENES_TOTAL} 个场景 (覆盖整个视频)")
            else:
                # First-N sampling (legacy behavior)
                scene_list = scene_list[:self.MAX_SCENES_TOTAL]
                print(f"⚠️ 场景过多，仅保留前 {self.MAX_SCENES_TOTAL} 个场景")
        # Use rsplit to properly handle filenames with multiple dots (e.g., movie.720p.mp4)
        video_basename = os.path.basename(video_path)
        video_name = video_basename.rsplit('.', 1)[0] if '.' in video_basename else video_basename
        video_name_short = video_basename.split('.')[0]  # Short name for directory
        video_output_dir = os.path.join(self.output_dir, video_name_short)
        os.makedirs(video_output_dir, exist_ok=True)

        # Split all scenes at once (FFmpeg is efficient, won't cause memory issues)
        # Only batch memory-intensive operations like CLIP encoding
        print(f"🎬 正在切分 {len(scene_list)} 个场景...")
        split_video_ffmpeg(video_path, scene_list, output_dir=video_output_dir)
        
        # Collect clip info - use the full video_name as PySceneDetect does
        all_clips = []
        for i, scene in enumerate(scene_list):
            start_time = scene[0].get_seconds()
            end_time = scene[1].get_seconds()
            scene_duration = end_time - start_time
            
            if scene_duration < 1.0:
                continue
            
            # PySceneDetect uses the full filename (without extension) for output
            clip_path = os.path.join(video_output_dir, f"{video_name}-Scene-{i+1:03d}.mp4")
            
            # Verify the file exists before adding
            if os.path.exists(clip_path):
                all_clips.append({
                    "path": clip_path,
                    "start": start_time,
                    "end": end_time,
                    "duration": scene_duration
                })
            else:
                print(f"⚠️ 场景文件不存在: {clip_path}")
        
        # Memory cleanup after splitting
        gc.collect()
            
        print(f"✅ 场景切分完成: {len(all_clips)} 个有效片段")
        return all_clips

    def extract_keyframe(self, clip_path):
        """
        Extracts the middle frame of a clip for embedding.
        """
        cap = cv2.VideoCapture(clip_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count // 2)
        ret, frame = cap.read()
        if ret:
            frame_path = clip_path.replace(".mp4", ".jpg")
            cv2.imwrite(frame_path, frame)
            cap.release()
            return frame_path
        cap.release()
        return None

    def extract_thumbnail(self, video_path, output_path):
        """
        Extracts the first frame of a video as a thumbnail.
        """
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(output_path, frame)
            cap.release()
            return True
        cap.release()
        return False

    def get_video_info(self, video_path) -> dict:
        """Get video metadata for progress estimation."""
        cap = cv2.VideoCapture(video_path)
        info = {
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0,
            "size_mb": os.path.getsize(video_path) / (1024 * 1024)
        }
        cap.release()
        return info
