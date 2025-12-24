import whisper
import librosa
import numpy as np
import torch

class AudioProcessor:
    def __init__(self, model_size="base"):
        # 优化点：支持 Mac MPS
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"🎙️ AudioProcessor 正在使用设备: {self.device}")
        self.model = whisper.load_model(model_size, device=self.device)

    def transcribe_with_timestamps(self, audio_path):
        """
        Transcribes audio and returns segments with timestamps.
        """
        result = self.model.transcribe(audio_path, verbose=False)
        return result['segments']

    def analyze_beats(self, audio_path):
        """
        Extracts beats (BPM) and beat timestamps.
        """
        y, sr = librosa.load(audio_path)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        # tempo is deprecated in newer librosa, handled as scalar or list
        if isinstance(tempo, np.ndarray):
            tempo = tempo[0]
            
        return {
            "tempo": float(tempo),
            "beat_times": beat_times.tolist()
        }
