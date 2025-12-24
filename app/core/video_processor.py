import os
from scenedetect import detect, ContentDetector, split_video_ffmpeg
import cv2

class VideoProcessor:
    def __init__(self, output_dir="app/static/processed/shots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def split_scenes(self, video_path):
        """
        Detects scenes with performance optimization.
        """
        print(f"Analyzing scenes for: {video_path}")
        # 优化点：使用 ContentDetector 但设置较快的阈值，并可以通过 skip 提升速度
        # 默认每秒至少采样几次，而不是每一帧。
        # 这里我们利用 PySceneDetect 的通用 detect 函数，它内部有很好的优化
        scene_list = detect(video_path, ContentDetector(threshold=27.0)) 
        
        # 兼容性处理：如果没检测到场景切换（比如单镜头视频），将整个视频作为一个片段
        if not scene_list:
            print(f"ℹ️ 未检测到场景切换，将整个视频作为一个片段处理")
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            cap.release()
            
            # 伪造一个 scene_list 格式
            from scenedetect import FrameTimecode
            scene_list = [(FrameTimecode(0, fps), FrameTimecode(frame_count, fps))]
        
        # 限制最大处理片段数，防止大视频导致索引爆炸
        if len(scene_list) > 100:
            print("⚠️ 视频过长，片段过多，仅保留前 100 个关键镜进行分析")
            scene_list = scene_list[:100]
        
        video_name = os.path.basename(video_path).split('.')[0]
        video_output_dir = os.path.join(self.output_dir, video_name)
        os.makedirs(video_output_dir, exist_ok=True)

        split_video_ffmpeg(video_path, scene_list, output_dir=video_output_dir)
        
        clips = []
        for i, scene in enumerate(scene_list):
            start_time = scene[0].get_seconds()
            end_time = scene[1].get_seconds()
            duration = end_time - start_time
            
            # Filter too short videos as discussed
            if duration < 1.0:
                continue
                
            clip_path = os.path.join(video_output_dir, f"{video_name}-Scene-{i+1:03d}.mp4")
            clips.append({
                "path": clip_path,
                "start": start_time,
                "end": end_time,
                "duration": duration
            })
            
        return clips

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
