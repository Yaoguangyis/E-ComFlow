from app.providers.base import BaseLLMProvider
from app.core.config import settings
from app.core.exceptions import ProviderException
from openai import AsyncOpenAI

class QwenProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    async def chat(self, message: str):
        try:
            response = await self.client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role":"user","content":message}]
            )
            return response.choices[0].message.content
        except Exception as e:
            raise ProviderException(f"Qwen Error: {str(e)}")

    async def stream_chat(self, message: str):
        try:
            stream = await self.client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role":"user","content":message}],
                stream=True
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield {"event": "token", "data": delta}
            yield {"event": "done", "data": "[DONE]"}
        except Exception as e:
            raise ProviderException(f"Qwen Stream Error: {str(e)}")

a = QwenProvider()