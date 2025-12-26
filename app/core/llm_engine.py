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

    async def generate_visual_script(self, lyric, intent, library_context=None, video_description=None):
        """
        将歌词和意图转化为具体的视觉描述词
        library_context: 素材库的自动视觉摘要
        video_description: 视频素材的人工描述背景（如电影简介、影评）
        """
        library_info = f"\n【素材库视觉摘要】：{library_context}\n" if library_context else ""
        theme_info = f"\n【视频素材背景知识】：{video_description}\n" if video_description else ""
        
        prompt = f"""
        你是一位顶级视频剪辑导演。当前你正在处理一个重要的剪辑任务，请结合【剧本核心背景】和【当前素材库视觉概况】来构思镜头。

        【极其重要 - 剧本核心背景】：{video_description if video_description else "未提供，请根据素材内容自行推断"}
        （注：这是该视频素材的真实故事背景，如影评或简介，是你的创作灵魂，请务必作为首选创作依据）

        【当前素材库视觉概况】：{library_context if library_context else "正在识别中"}
        （注：这是素材库中可用的视觉元素，作为你的画面参考）

        【歌词内容】：{lyric}
        【剪辑意图】：{intent}

        任务要求：
        1. 逻辑对齐：结合【剧本核心背景】深度解读歌词。如果背景说是赛车电影，即便歌词很抽象，也要构思与赛车、速度、竞技相关的镜头。
        2. 视觉自洽：确保构思的画面在【素材库视觉概况】中具有可行性。
        3. 检索词精练：提供极其具体的英文检索词。

        输出格式：
        {{
            "reasoning": "中文，解释你如何根据【剧本核心背景】来解读这句歌词并转化为特定镜头",
            "visual_prompt": "英文，精简的视觉检索词，不超过 30 个单词"
        }}
        """
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的短视频导演。你需要根据视频素材库背后的故事背景来调整你的创作逻辑。请直接输出 JSON。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" } 
        )
        
        data = json.loads(response.choices[0].message.content.strip())
        if 'visual_prompt' in data:
            words = data['visual_prompt'].split()
            if len(words) > 60:
                data['visual_prompt'] = " ".join(words[:60])
        return data

    async def analyze_video_library(self, image_paths):
        """
        利用 Qwen-VL 模型对素材库的关键采样帧进行多图综合分析，生成全局调性报告。
        """
        import base64
        
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

        # 构建多图输入
        content = [{"type": "text", "text": "你是一个资深的素材库分析师。请分析以下这组来自同一视频（或素材库）的关键采样帧，并总结出该素材库的【核心视觉元素】、【主要场景类型】、【画面主色调】以及【动作风格】。这将作为后续 AI 剪辑导演的参考。请用一两句话简练概括。"}]
        
        # 限制图片数量，避免 Token 过多
        sampled_paths = image_paths[:8] 
        for img_path in sampled_paths:
            base64_image = encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        try:
            response = self.client.chat.completions.create(
                model="qwen-vl-plus", # 使用视觉大模型
                messages=[{"role": "user", "content": content}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ 素材库视觉分析失败: {e}")
            return "分析失败，请按照通用电影感风格构思。"

    async def align_lyrics(self, whisper_segments, manual_lyrics):
        """
        利用 LLM 对齐：将 Whisper 抓取到的时间戳段落与精准的歌词文本进行配对校准。
        """
        prompt = f"""
        任务：歌词文本与时间戳强制对齐
        背景：Whisper 在带背景音乐的情况下识别歌词非常不准确，会有很多错别字和幻听。
        
        【原始精准歌词】：
        {manual_lyrics}
        
        【Whisper 识别出的带时间戳草稿】：
        {json.dumps(whisper_segments, ensure_ascii=False)}
        
        任务要求：
        1. 请参考【原始精准歌词】，纠正【草稿段落】中的文字。
        2. 保持时间戳不变，只修改文字内容。
        3. 如果 Whisper 将一句精准歌词拆分成了多个时间段，请合理分配文字。
        4. 结果必须覆盖整首歌的时间线。
        
        输出格式：纯 JSON 数组
        [
            {{"start": 0.0, "end": 5.0, "text": "校准后的第一句"}},
            ...
        ]
        """
        
        response = self.client.chat.completions.create(
            model="qwen-turbo", # 使用 turbo 模型处理长文本更经济高效
            messages=[
                {"role": "system", "content": "你是一个专业的歌词校准器。请直接输出 JSON 存储的结果。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" } # 某些情况下可能需要强制结构
        )
        
        # 处理结果可能直接是 JSON 数组字符串
        content = response.choices[0].message.content.strip()
        try:
            # 兼容模型可能多包了一层 root 或直接返回数组
            data = json.loads(content)
            if isinstance(data, dict) and "segments" in data:
                return data["segments"]
            if isinstance(data, list):
                return data
            return data # 灵活处理
        except:
            return whisper_segments # 失败回退
