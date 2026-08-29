import os
from queue import Full
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from wrapper import GenieWrapper


class CreateTaskRequest(BaseModel):
    character_name: str
    reference_audio_id: str
    reference_audio_text: str
    text: str


class CreateTaskResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    status: str
    pending: int
    save_path: str | None = None
    save_path_compressed: str | None = None
    wav_expires_at: str | None = None
    ogg_expires_at: str | None = None
    error: str | None = None


def _client_ip(request: Request) -> str:
    forwarded_ip = request.headers.get("x-client-ip")
    if forwarded_ip:
        return forwarded_ip
    return request.client.host if request.client else "unknown"


wrapper = GenieWrapper()
limiter = Limiter(key_func=_client_ip, headers_enabled=True)
app = FastAPI(title="Genie TTS Server", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
BASE_STATIC_URL = os.getenv("BASE_STATIC_URL", "").rstrip("/")
if not BASE_STATIC_URL:
    raise ValueError("BASE_STATIC_URL must be set in the environment.")


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/tasks", response_model=CreateTaskResponse)
@limiter.limit("100/day")
def create_task(
    request: Request,
    response: Response,
    body: CreateTaskRequest,
) -> CreateTaskResponse:
    """Create a background TTS synthesis task."""
    try:
        task_id = wrapper.create_tts_task(
            character_name=body.character_name,
            reference_audio_id=body.reference_audio_id,
            reference_audio_text=body.reference_audio_text,
            text=body.text,
        )
    except Full as exc:
        raise HTTPException(
            status_code=503,
            detail="task queue is full",
            headers={"Retry-After": "60"},
        ) from exc
    return CreateTaskResponse(task_id=task_id)


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Query the current status of a TTS task."""
    status = wrapper.get_task_status(task_id)
    if status["status"] == "not_found":
        raise HTTPException(
            status_code=404,
            detail={
                "status": status["status"],
                "pending": status["pending"],
            },
        )
    if status.get("save_path"):
        status["save_path"] = (
            f"{BASE_STATIC_URL}/{quote(status['save_path'], safe='/')}"
        )
    if status.get("save_path_compressed"):
        status["save_path_compressed"] = (
            f"{BASE_STATIC_URL}/{quote(status['save_path_compressed'], safe='/')}"
        )
    return TaskStatusResponse(**status)


@app.get("/health")
def health() -> dict[str, str]:
    """Basic health endpoint for readiness probes."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
