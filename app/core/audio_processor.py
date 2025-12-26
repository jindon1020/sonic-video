import whisper
import librosa
import numpy as np
import torch
import os

class AudioProcessor:
    def __init__(self, model_size="base"):
        # 优先使用 MPS 加速
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
            
        print(f"🎙️ AudioProcessor 正在使用设备: {self.device}")
        self.model = whisper.load_model(model_size, device=self.device)

    def transcribe_with_timestamps(self, audio_path, manual_lyrics=None):
        """
        Transcribe audio and optionally align with manual lyrics.
        """
        print(f"正在转录音频: {audio_path}")
        result = self.model.transcribe(audio_path, verbose=False)
        segments = result['segments']
        
        # 将 Whisper 格式转换为内部格式
        formatted_segments = []
        for s in segments:
            formatted_segments.append({
                'start': s['start'],
                'end': s['end'],
                'text': s['text'].strip()
            })
            
        return formatted_segments

    def analyze_beats(self, audio_path):
        """
        Analyze beats and tempo using librosa.
        """
        try:
            # 这里的加载可能因为 ffmpeg 报错，使用 try-except
            y, sr = librosa.load(audio_path)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            return {
                "tempo": float(tempo),
                "beat_times": librosa.frames_to_time(beat_frames, sr=sr).tolist()
            }
        except Exception as e:
            print(f"⚠️ 节奏分析失败: {e}")
            return {"tempo": 120.0, "beat_times": []}

    def calibrate_with_manual_lyrics(self, whisper_segments, manual_lyrics):
        """
        利用大模型将 Whisper 的时间戳与手动输入的精准歌词进行对齐。
        此功能在 llm_engine 中调用更合适，但在处理器中预留逻辑。
        """
        # 如果提供了手动歌词，我们将 Whisper 结果视为索引参考
        # 实际对齐逻辑将在 main.py 配合 LLM 完成
        return whisper_segments
