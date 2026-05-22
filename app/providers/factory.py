from app.providers.qwen_provider import QwenProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.claude_provider import ClaudeProvider


class ProviderFactory:

    @staticmethod
    def create(provider: str):

        if provider == "qwen":
            return QwenProvider()

        if provider == "openai":
            return OpenAIProvider()

        if provider == "claude":
            return ClaudeProvider()

        raise ValueError(
            f"unsupported provider: {provider}"
        )