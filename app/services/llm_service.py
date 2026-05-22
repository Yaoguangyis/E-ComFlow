from app.providers.factory import ProviderFactory


class LLMService:

    async def chat(
        self,
        message: str,
        provider: str
    ):

        llm_provider = ProviderFactory.create(
            provider
        )

        result = await llm_provider.chat(
            message
        )

        return result

    async def stream_chat(
        self,
        message: str,
        provider: str
    ):

        llm_provider = ProviderFactory.create(
            provider
        )

        async for chunk in llm_provider.stream_chat(
            message
        ):

            yield chunk