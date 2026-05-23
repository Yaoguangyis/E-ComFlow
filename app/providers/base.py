from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(self, message: str):
        pass

    @abstractmethod
    async def stream_chat(self, message: str):
        pass