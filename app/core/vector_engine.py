import torch
import clip
from PIL import Image
import numpy as np

class VectorEngine:
    def __init__(self, model_name="ViT-B/32"):
        # 优化点：优先使用 Mac 的 MPS 加速
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
            
        print(f"🚀 VectorEngine 正在使用设备: {self.device}")
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.clips_metadata = []
        self.vectors = []

    def encode_image(self, image_path):
        # 优化点：减小输入尺寸处理压力
        image = self.preprocess(Image.open(image_path)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            image_features = self.model.encode_image(image)
        return image_features.cpu().numpy().flatten()

    def encode_text(self, text):
        text_tokens = clip.tokenize([text]).to(self.device)
        with torch.no_grad():
            text_features = self.model.encode_text(text_tokens)
        return text_features.cpu().numpy().flatten()

    def add_to_index(self, vector, metadata):
        self.vectors.append(vector)
        self.clips_metadata.append(metadata)

    def search(self, query_text, top_k=3):
        if not self.vectors:
            return []
            
        query_vec = self.encode_text(query_text)
        
        # Calculate cosine similarity
        similarities = []
        for vec in self.vectors:
            sim = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
            similarities.append(sim)
            
        indices = np.argsort(similarities)[::-1][:top_k]
        results = [
            {**self.clips_metadata[i], "score": float(similarities[i])}
            for i in indices
        ]
        return results
