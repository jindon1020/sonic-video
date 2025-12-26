from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip
import os

class Editor:
    def __init__(self, output_path="app/static/processed/final_video.mp4"):
        self.output_path = output_path
        # 标准 1080p 横屏尺寸
        self.target_width = 1920
        self.target_height = 1080

    def _resize_clip_to_target(self, clip):
        """
        统一视频尺寸，采用中心填充裁剪（Crop-to-fill），彻底消除嵌套黑边。
        """
        clip_w, clip_h = clip.size
        target_w, target_h = self.target_width, self.target_height
        target_aspect = target_w / target_h
        clip_aspect = clip_w / clip_h
        
        # 调整大小
        if clip_aspect > target_aspect:
            # 素材太宽，按高度缩放
            scale = target_h / clip_h
            new_w = int(clip_w * scale)
            resized = clip.resized((new_w, target_h))
            # 裁剪宽度
            x_offset = (new_w - target_w) // 2
            return resized.cropped(x1=x_offset, x2=x_offset + target_w, y1=0, y2=target_h)
        else:
            # 素材太窄（竖屏），按宽度缩放
            scale = target_w / clip_w
            new_h = int(clip_h * scale)
            resized = clip.resized((target_w, new_h))
            # 裁剪高度
            y_offset = (new_h - target_h) // 2
            return resized.cropped(x1=0, x2=target_w, y1=y_offset, y2=y_offset + target_h)

    def _add_subtitle(self, clip, text):
        """
        为片段添加电影感字幕：底部居中，带半透明黑色背景遮罩
        """
        if not text:
            return clip
            
        font_size = 48
        # macOS 上的标准中文名可能是 "PingFang-SC-Regular" 或者直接用字体库路径
        font_list = ["PingFang-SC-Regular", "Heiti-SC-Light", "Arial-Unicode-MS", "Helvetica"]
        
        txt_clip = None
        for font in font_list:
            try:
                txt_clip = TextClip(
                    text=text,
                    font=font,
                    font_size=font_size,
                    color='white',
                    method='caption',
                    size=(self.target_width * 0.8, None),
                    text_align='center'
                ).with_duration(clip.duration)
                if txt_clip: break
            except:
                continue
                
        if not txt_clip:
            try:
                txt_clip = TextClip(
                    text=text,
                    font_size=font_size,
                    color='white',
                    method='caption',
                    size=(self.target_width * 0.8, None),
                    text_align='center'
                ).with_duration(clip.duration)
            except:
                return clip

        try:
            # 文字背景（黑色半透明）
            bg_width = self.target_width
            bg_height = txt_clip.h + 40
            bg_clip = ColorClip(
                size=(bg_width, bg_height),
                color=(0,0,0)
            ).with_opacity(0.5).with_duration(clip.duration)
            
            # 位置计算
            y_pos = self.target_height - bg_height - 60
            
            # 组合
            result = CompositeVideoClip([
                clip,
                bg_clip.with_position(('center', y_pos)),
                txt_clip.with_position(('center', y_pos + 20))
            ])
            return result
        except Exception as e:
            print(f"⚠️ 字幕复叠失败: {e}")
            return clip

    def assemble(self, clip_configs, audio_path):
        """
        clip_configs: list of { "path": ..., "target_duration": ..., "text": ... }
        audio_path: 背景音乐路径
        """
        final_clips = []
        
        audio = AudioFileClip(audio_path)
        target_total_duration = audio.duration
        
        print(f"🎬 开始合成任务: 目标总长={target_total_duration:.2f}s")

        for config in clip_configs:
            try:
                # 检查是否是虚拟切片
                is_virtual = config.get("is_virtual", False)
                path = config["path"]
                
                if is_virtual:
                    # 虚拟切片：从原视频动态截取
                    clip = VideoFileClip(path).subclipped(config["start"], config["end"])
                else:
                    # 物理切片
                    clip = VideoFileClip(path)
                
                # 统一尺寸
                clip = self._resize_clip_to_target(clip)
                
                # 确保时长精确匹配目标
                target_d = config.get("target_duration", clip.duration)
                if clip.duration > target_d:
                    clip = clip.subclipped(0, target_d)
                else:
                    # 此时 main.py 会提供下一个镜头来补位，不再重复 LOOP
                    pass
                
                # 添加字幕
                clip = self._add_subtitle(clip, config.get("text", ""))
                
                final_clips.append(clip)
            except Exception as e:
                print(f"⚠️ 处理片段 {config['path']} 出错: {e}")

        if not final_clips:
            raise ValueError("未能找到任何匹配的视频片段。")

        # 拼接视频
        video = concatenate_videoclips(final_clips, method="chain")
        
        # 再次确保最终视频时长不超过音频时长
        final_duration = min(video.duration, target_total_duration)
        video = video.subclipped(0, final_duration)
        
        # 合并音轨
        final_video = video.with_audio(audio.subclipped(0, final_duration))
        
        try:
            print(f"💾 正在写入文件: {self.output_path}...")
            final_video.write_videofile(
                self.output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                threads=4, 
                logger=None
            )
            print("✅ 合成成功")
            return self.output_path
        finally:
            if final_video: final_video.close()
            for c in final_clips: c.close()
            audio.close()
