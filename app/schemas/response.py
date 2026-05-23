from pydantic import BaseModel

class APIResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None