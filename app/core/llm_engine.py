from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

class LLMEngine:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY not found. Please set it in .env file.")
        
        # 阿里云百炼使用 OpenAI 兼容接口
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        # 使用 qwen-plus 模型，针对复杂指令理解效果极佳
        self.model_name = "qwen-plus"

    async def generate_visual_script(self, lyric, intent):
        """
        将歌词和意图转化为具体的视觉描述词 (Visual Prompts)
        使用 Qwen 系列模型进行深度意图解析
        """
        prompt = f"""
        你是一位顶级视频剪辑导演。请根据提供的【歌词内容】和【剪辑意图】，构思一个电影级的视觉画面。
        
        【歌词】：{lyric}
        【意图】：{intent}
        
        任务要求：
        1. 深度解析：理解歌词的情绪（如：孤独、赛博、治愈）并将其与意图（如：阳光、Vlog）融合。
        2. 视觉转化：将其转化为一个具体的、写实的镜头描述。
        3. 检索关键词（关键）：提供 10-15 个具体的英文词。
           - 必须包含：基础环境（如 ocean, sun, beach, forest, urban）、主体（person, travel）、光影（golden hour, cinematic light）、动作。
           - 避免抽象概念（如 "loneliness"），要用具体的视觉元素体现（如 "empty bench, gray sky"）。
        
        关键约束（极其重要）：
        - "visual_prompt" 必须极其简练，总长度绝对不能超过 50 个单词。
        
        输出格式（必须是纯 JSON，不要包含 Markdown 代码块）：
        {{
            "reasoning": "中文，20-30字，解释你的导演意图和镜头设计逻辑",
            "visual_prompt": "英文，具体的、包含环境实景词的检索词段落"
        }}
        """
        
        # 移除兜底逻辑，强制要求调用成功
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的短视频导演。你需要严格遵守字数限制。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" } # 强制 JSON 输出
        )
        
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        
        # 二次保险：如果模型输出还是太长，强制截断前 60 个词，避免 CLIP 报错崩溃
        if 'visual_prompt' in data:
            words = data['visual_prompt'].split()
            if len(words) > 60:
                data['visual_prompt'] = " ".join(words[:60])
                
        return data
