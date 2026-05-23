from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from app.schemas.chat import ChatRequest
from app.schemas.response import APIResponse
from app.services.llm_service import LLMService

router = APIRouter()

def get_llm_service():
    return LLMService()

@router.post("/chat")
async def chat(
    req: ChatRequest,
    service: LLMService = Depends(get_llm_service)
):
    result = await service.chat(message=req.message, provider=req.provider)
    return APIResponse(success=True, data={"content": result})

@router.post("/chat/stream")
async def stream_chat(
    req: ChatRequest,
    service: LLMService = Depends(get_llm_service)
):
    async def event_generator():
        async for chunk in service.stream_chat(req.message, req.provider):
            yield chunk
    return EventSourceResponse(event_generator())