import os
from scenedetect import detect, ContentDetector, split_video_ffmpeg
import cv2
import gc

class VideoProcessor:
    """Video processor with batch processing and memory management for large files."""
    
    # Processing limits to prevent memory overflow
    MAX_SCENES_TOTAL = 800  # 提升至 800 个，覆盖更多细节
    SCENES_PER_BATCH = 20   
    UNIFORM_SAMPLE = True   
    PHYSICAL_SPLIT = False  # 关键：开启虚拟切片模式，不再物理切割文件
    
    def __init__(self, output_dir="app/static/processed/shots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def split_scenes(self, video_path):
        """
        虚拟切分逻辑：返回时间戳元数据，而不进行物理切割。
        """
        print(f"🎬 正在检测场景 (虚拟模式): {os.path.basename(video_path)}")
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        
        # 1. 检测场景
        scene_list = detect(video_path, ContentDetector(threshold=27.0)) 
        
        # 兜底：等距切分
        if not scene_list:
            from scenedetect import FrameTimecode
            seg_duration = 5.0
            num_segments = int(duration // seg_duration)
            for i in range(num_segments):
                scene_list.append((FrameTimecode(i * seg_duration, fps), FrameTimecode((i + 1) * seg_duration, fps)))
            if duration % seg_duration >= 1.0:
                scene_list.append((FrameTimecode(num_segments * seg_duration, fps), FrameTimecode(frame_count, fps)))
        
        # 2. 均匀采样
        original_count = len(scene_list)
        if original_count > self.MAX_SCENES_TOTAL:
            step = original_count / self.MAX_SCENES_TOTAL
            scene_list = [scene_list[int(i * step)] for i in range(self.MAX_SCENES_TOTAL)]

        # 3. 构造虚拟索引
        all_clips = []
        video_basename = os.path.basename(video_path)
        video_name = video_basename.rsplit('.', 1)[0]
        
        # 物理切割（仅当开关开启时，默认为 False）
        if self.PHYSICAL_SPLIT:
            video_name_short = video_basename.split('.')[0]
            video_output_dir = os.path.join(self.output_dir, video_name_short)
            os.makedirs(video_output_dir, exist_ok=True)
            split_video_ffmpeg(video_path, scene_list, output_dir=video_output_dir)

        for i, scene in enumerate(scene_list):
            start_t = scene[0].get_seconds()
            end_t = scene[1].get_seconds()
            d = end_t - start_t
            if d < 1.0: continue
            
            # 如果是虚拟模式，path 指向原视频；如果是物理模式，指向切片
            if not self.PHYSICAL_SPLIT:
                clip_path = video_path # 引用原视频
            else:
                video_name_short = video_basename.split('.')[0]
                clip_path = os.path.join(self.output_dir, video_name_short, f"{video_name}-Scene-{i+1:03d}.mp4")

            all_clips.append({
                "path": clip_path,
                "parent_path": video_path,
                "start": start_t,
                "end": end_t,
                "duration": d,
                "is_virtual": not self.PHYSICAL_SPLIT
            })
            
        print(f"✅ 虚拟切分完成: {len(all_clips)} 个索引片段")
        return all_clips

    def extract_keyframes(self, video_path, start_t, end_t, num_frames=3):
        """
        从视频的指定时间范围内提取多个关键帧（用于多帧特征聚合）。
        """
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_paths = []
        
        duration = end_t - start_t
        for i in range(1, num_frames + 1):
            sample_time = start_t + (duration * (i / (num_frames + 1)))
            frame_idx = int(sample_time * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                suffix = f"_t{int(sample_time*100)}"
                tmp_path = os.path.join(self.output_dir, f"tmp_kf_{os.path.basename(video_path)}_{suffix}.jpg")
                cv2.imwrite(tmp_path, frame)
                frame_paths.append(tmp_path)
        
        cap.release()
        return frame_paths

    def extract_keyframe(self, clip_path):
        """兼容旧版接口，取 50% 位置的单帧"""
        return self.extract_keyframes(clip_path, 0, 99999, num_frames=1)[0] if os.path.exists(clip_path) else None

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
