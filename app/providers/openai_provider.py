from openai import AsyncOpenAI

from app.providers.base import BaseLLMProvider
from app.core.config import settings


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):

        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY
        )

    async def chat(
        self,
        message: str
    ):

        response = await self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        return response.choices[0].message.content

    async def stream_chat(
        self,
        message: str
    ):

        stream = await self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ],
            stream=True
        )

        async for chunk in stream:

            delta = chunk.choices[0].delta.content

            if delta:

                yield delta