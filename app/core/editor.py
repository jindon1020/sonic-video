from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
import os

class Editor:
    def __init__(self, output_path="app/static/processed/final_video.mp4"):
        self.output_path = output_path

    def assemble(self, clip_configs, audio_path):
        """
        clip_configs: list of { "path": ..., "duration": ..., "start": ... }
        audio_path: path to the background music
        """
        final_clips = []
        for config in clip_configs:
            clip = VideoFileClip(config["path"])
            final_clips.append(clip)
            
        if not final_clips:
            raise ValueError("未能找到任何匹配的视频片段，请尝试更换意图描述或上传更多视频。")
            
        video = None
        audio = None
        final_video = None
        
        try:
            print(f"🎬 开始合成任务: 片段数量={len(final_clips)}, 音频={audio_path}")
            video = concatenate_videoclips(final_clips, method="compose")
            audio = AudioFileClip(audio_path)
            
            print(f"⌛ 原始视频总长: {video.duration:.2f}s, 原始音频总长: {audio.duration:.2f}s")
            
            # 使用较短的时间确保不越界
            final_duration = min(video.duration, audio.duration)
            print(f"✂️ 目标合成长度定为: {final_duration:.2f}s (取音视频最小值)")
            
            # 必须分别对音视频进行 subclipped (MoviePy 2.0+)
            print("🛠️ 正在进行时间轴对齐与裁剪...")
            final_video_clip = video.subclipped(0, final_duration)
            final_audio_clip = audio.subclipped(0, final_duration)
            
            print("🎵 正在合并音轨...")
            final_video = final_video_clip.with_audio(final_audio_clip)
            
            print(f"💾 正在写入文件: {self.output_path} (限制线程=2)...")
            final_video.write_videofile(
                self.output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                threads=2, 
                logger=None # 减少输出波动
            )
            print("✅ 合成成功结束")
            return self.output_path
        except Exception as e:
            print(f"❌ 合成阶段抛出异常: {str(e)}")
            raise e
        finally:
            print("🧹 正在清理内存资源...")
            if video: video.close()
            if audio: audio.close()
            if final_video: final_video.close()
            for c in final_clips: 
                try: c.close()
                except: pass
            print("♻️ 资源清理完毕")
