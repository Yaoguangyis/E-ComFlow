from app.providers.base import BaseLLMProvider
from app.core.config import settings
from app.core.exceptions import ProviderException
from openai import AsyncOpenAI

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat(self, message: str):
        try:
            response = await self.client.chat.completions.create(
                model="gpt-5",
                messages=[{"role":"user","content":message}]
            )
            return response.choices[0].message.content
        except Exception as e:
            raise ProviderException(f"OpenAI Error: {str(e)}")

    async def stream_chat(self, message: str):
        try:
            stream = await self.client.chat.completions.create(
                model="gpt-5",
                messages=[{"role":"user","content":message}],
                stream=True
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield {"event": "token", "data": delta}
            yield {"event": "done", "data": "[DONE]"}
        except Exception as e:
            raise ProviderException(f"OpenAI Stream Error: {str(e)}")