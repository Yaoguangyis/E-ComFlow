from pydantic import BaseModel


class ChatRequest(BaseModel):

    message: str

    provider: str = "qwen"