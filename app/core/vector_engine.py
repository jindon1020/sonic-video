import torch
import clip
from PIL import Image
import numpy as np
import gc

class VectorEngine:
    """CLIP-based vector engine with batch processing and memory management."""
    
    # Batch size for encoding - lower = less memory, slower
    BATCH_SIZE = 10
    
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
        self._encoding_count = 0

    def encode_image(self, image_path):
        """Encode a single image and manage memory."""
        image = self.preprocess(Image.open(image_path)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            image_features = self.model.encode_image(image)
        
        # Memory cleanup after every N encodings
        self._encoding_count += 1
        if self._encoding_count % self.BATCH_SIZE == 0:
            self._clear_cache()
            
        return image_features.cpu().numpy().flatten()

    def encode_images_batch(self, image_paths: list) -> list:
        """
        Encode multiple images in batches to manage memory.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of feature vectors
        """
        all_features = []
        
        for i in range(0, len(image_paths), self.BATCH_SIZE):
            batch_paths = image_paths[i:i + self.BATCH_SIZE]
            batch_images = []
            
            for path in batch_paths:
                try:
                    img = self.preprocess(Image.open(path)).unsqueeze(0)
                    batch_images.append(img)
                except Exception as e:
                    print(f"⚠️ 无法加载图片 {path}: {e}")
                    continue
            
            if batch_images:
                batch_tensor = torch.cat(batch_images, dim=0).to(self.device)
                with torch.no_grad():
                    features = self.model.encode_image(batch_tensor)
                all_features.extend(features.cpu().numpy())
                
                # Clear GPU cache after each batch
                del batch_tensor
                self._clear_cache()
        
        return all_features

    def encode_text(self, text):
        # 防御性处理：CLIP 仅支持 77 个 token，过长会崩溃。
        # 此处强制截断字符串到约 230 个字符，以确保安全。
        if len(text) > 230:
            text = text[:230].rsplit(' ', 1)[0] # 尽量在单词边界截断
            
        with torch.no_grad():
            try:
                text_tokens = clip.tokenize([text]).to(self.device)
            except RuntimeError:
                # 如果还是过长（例如全是短单词），则进行极端截断
                text_tokens = clip.tokenize([text[:100]]).to(self.device)
                
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

    def encode_images_and_average(self, image_paths: list):
        """
        对多张图片提取特征并计算平均向量 (Mean Pooling)
        """
        if not image_paths:
            return None
            
        vectors = []
        for img_path in image_paths:
            vec = self.encode_image(img_path)
            if vec is not None:
                vectors.append(torch.tensor(vec))
        
        if not vectors:
            return None
            
        # 聚合（平均值）
        avg_vec = torch.stack(vectors).mean(dim=0)
        # 归一化
        avg_vec = avg_vec / avg_vec.norm(dim=-1, keepdim=True)
        return avg_vec.cpu().numpy().flatten()

    def reset(self):
        """Reset the index and free memory."""
        self.vectors.clear()
        self.clips_metadata.clear()
        self._encoding_count = 0
        self._clear_cache()
        print("🗑️ VectorEngine 索引已重置，内存已清理")

    def _clear_cache(self):
        """Clear GPU/MPS cache and run garbage collection."""
        if self.device == "mps":
            torch.mps.empty_cache()
        elif self.device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()

    def get_memory_stats(self) -> dict:
        """Get current memory usage stats for debugging."""
        return {
            "vectors_count": len(self.vectors),
            "encoding_count": self._encoding_count,
            "device": self.device
        }
