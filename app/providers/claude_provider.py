from app.providers.base import BaseLLMProvider
from app.core.config import settings
from app.core.exceptions import ProviderException
from anthropic import AsyncAnthropic

class ClaudeProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def chat(self, message: str):
        try:
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role":"user","content":message}]
            )
            return response.content[0].text
        except Exception as e:
            raise ProviderException(f"Claude Error: {str(e)}")

    async def stream_chat(self, message: str):
        try:
            async with self.client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role":"user","content":message}]
            ) as stream:
                async for text in stream.text_stream:
                    yield {"event": "token", "data": text}
            yield {"event": "done", "data": "[DONE]"}
        except Exception as e:
            raise ProviderException(f"Claude Stream Error: {str(e)}")