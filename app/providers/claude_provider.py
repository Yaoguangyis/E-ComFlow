from anthropic import AsyncAnthropic

from app.providers.base import BaseLLMProvider
from app.core.config import settings


class ClaudeProvider(BaseLLMProvider):

    def __init__(self):

        self.client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )

    async def chat(
        self,
        message: str
    ):

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        return response.content[0].text

    async def stream_chat(
        self,
        message: str
    ):

        async with self.client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ]
        ) as stream:

            async for text in stream.text_stream:

                yield text