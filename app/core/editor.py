from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, ColorClip
import os

class Editor:
    def __init__(self, output_path="app/static/processed/final_video.mp4", config=None):
        self.output_path = output_path
        if config:
            self.target_width = config.get("advanced", "output_width", 1920)
            self.target_height = config.get("advanced", "output_height", 1080)
            self.output_fps = config.get("advanced", "output_fps", 24)
        else:
            self.target_width = 1920
            self.target_height = 1080
            self.output_fps = 24

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

    def _add_subtitle(self, clip, text, visual_description=None):
        """
        为片段添加电影感字幕：
        - 底部：歌词 (text)
        - 左上角：画面描述 (visual_description)
        """
        if not text and not visual_description:
            return clip
            
        # 尝试使用的字体列表
        font_list = ["PingFang-SC-Regular", "Heiti-SC-Light", "Arial-Unicode-MS", "Helvetica", "Sans"]
        
        elements = [clip]

        # 1. 处理底部歌词
        if text:
            # 去掉可能的特殊符号
            clean_text = text.replace('"', '').replace("'", "").strip()
            txt_clip = None
            for font in font_list:
                try:
                    txt_clip = TextClip(
                        text=clean_text,
                        font=font,
                        font_size=54,
                        color='white',
                        method='caption',
                        text_align='center',
                        size=(self.target_width * 0.8, None)
                    ).with_duration(clip.duration)
                    if txt_clip: break
                except Exception as e:
                    continue
            
            if txt_clip:
                # 歌词背景
                bg_h = txt_clip.h + 40
                lyric_bg = ColorClip(
                    size=(self.target_width, bg_h),
                    color=(0,0,0)
                ).with_opacity(0.4).with_duration(clip.duration)
                
                y_pos = self.target_height - bg_h - 60
                elements.append(lyric_bg.with_position(('center', y_pos)))
                elements.append(txt_clip.with_position(('center', y_pos + 20)))

        # 2. 处理左上角画面描述 (视觉打标 - 调试版)
        if visual_description:
            tag_text = visual_description
            tag_clip = None
            for font in font_list:
                try:
                    tag_clip = TextClip(
                        text=tag_text,
                        font=font,
                        font_size=28, # 稍微减小字体
                        color='white',
                        method='caption',
                        text_align='left',
                        size=(self.target_width * 0.45, None)
                    ).with_duration(clip.duration)
                    if tag_clip: break
                except:
                    continue
            
            if tag_clip:
                # 标签背景：支持多行，使用半透明灰色，更有科技感
                tag_bg = ColorClip(
                    size=(tag_clip.w + 40, tag_clip.h + 20),
                    color=(20, 20, 20)
                ).with_opacity(0.6).with_duration(clip.duration)
                
                elements.append(tag_bg.with_position((40, 40)))
                elements.append(tag_clip.with_position((60, 50)))

        try:
            return CompositeVideoClip(elements)
        except Exception as e:
            print(f"⚠️ 视频合成组件失败 (可能是字体或 ImageMagick 问题): {e}")
            return clip

    def assemble(self, clip_configs, audio_path):
        """
        clip_configs: list of { "path": ..., "target_duration": ..., "text": ..., "visual_description": ... }
        audio_path: 背景音乐路径
        """
        final_clips = []
        
        # 预加载音频
        from moviepy import AudioFileClip
        audio = AudioFileClip(audio_path)
        target_total_duration = audio.duration
        
        print(f"🎬 开始合成任务: 目标总长={target_total_duration:.2f}s")

        for config in clip_configs:
            try:
                # 检查是否是虚拟切片
                is_virtual = config.get("is_virtual", False)
                path = config["path"]
                
                if not os.path.exists(path):
                    print(f"⚠️ 文件不存在，跳过: {path}")
                    continue

                if is_virtual:
                    # 虚拟切片：从原视频动态截取
                    # MoviePy 2.0 使用 subclipped
                    raw_clip = VideoFileClip(path)
                    start_t = max(0, config.get("start", 0))
                    end_t = min(config.get("end", raw_clip.duration), raw_clip.duration)
                    clip = raw_clip.subclipped(start_t, end_t)
                else:
                    # 物理切片
                    clip = VideoFileClip(path)
                
                # 统一尺寸 (此方法内部已处理 resize 和 crop)
                clip = self._resize_clip_to_target(clip)
                
                # 确保时长精确匹配目标
                target_d = config.get("target_duration", clip.duration)
                if clip.duration > target_d:
                    # 使用 min 确保 target_d 不会因浮点数误差超过时长
                    clip = clip.subclipped(0, min(target_d, clip.duration))
                
                # 添加字幕和打标
                clip = self._add_subtitle(
                    clip, 
                    config.get("text", ""), 
                    config.get("visual_description")
                )
                
                final_clips.append(clip)
            except Exception as e:
                print(f"⚠️ 处理片段 {config['path']} 出错: {e}")
                import traceback
                traceback.print_exc()

        if not final_clips:
            audio.close()
            raise ValueError("未能找到任何匹配的视频片段。")

        # 1. 拼接视频 (采用视频决定总长模式)
        video = concatenate_videoclips(final_clips, method="compose")
        video_total_duration = video.duration
        
        print(f"🎬 视频拼接完成: 总长={video_total_duration:.2f}s")

        # 2. 对齐音频：音频长度以视频总长为准
        # 如果音频比视频长，截取前段；如果短，循环或保持静默
        if audio.duration > video_total_duration:
            final_audio = audio.subclipped(0, video_total_duration)
        else:
            final_audio = audio # 或者可以考虑循环 audio.loop(duration=video_total_duration)
            
        # 3. 电影感处理：末尾 2 秒淡出 (Fade Out to Black)
        fade_duration = 2.0
        if video_total_duration > fade_duration:
            # 视频黑场淡出
            from moviepy.video.fx import FadeOut
            from moviepy.audio.fx import AudioFadeOut
            video = video.with_effects([FadeOut(fade_duration)])
            # 音频音量淡出
            final_audio = final_audio.with_effects([AudioFadeOut(fade_duration)])

        # 4. 合并音轨
        final_video = video.with_audio(final_audio)
        
        try:
            print(f"Writing video: {self.output_path} (FPS={self.output_fps})...")
            final_video.write_videofile(
                self.output_path,
                fps=self.output_fps,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                logger=None
            )
            print("✅ 电影 MV 制作成功")
            return self.output_path
        finally:
            final_video.close()
            for c in final_clips: c.close()
            audio.close()
