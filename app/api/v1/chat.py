from fastapi import APIRouter

from sse_starlette.sse import EventSourceResponse

from app.schemas.chat import ChatRequest
from app.schemas.response import APIResponse

from app.services.llm_service import LLMService

router = APIRouter()

service = LLMService()


@router.post("/chat")
async def chat(req: ChatRequest):

    result = await service.chat(
        message=req.message,
        provider=req.provider
    )

    return APIResponse(
        success=True,
        data={
            "content": result
        }
    )


@router.post("/chat/stream")
async def stream_chat(req: ChatRequest):

    async def event_generator():

        async for chunk in service.stream_chat(
            message=req.message,
            provider=req.provider
        ):

            yield {
                "event": "message",
                "data": chunk
            }

    return EventSourceResponse(
        event_generator()
    )