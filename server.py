from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from pathlib import Path

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
    error: str | None = None


wrapper = GenieWrapper()
app = FastAPI(title="Genie TTS Server", version="0.1.0")
BASE_STATIC_URL = os.getenv("BASE_STATIC_URL", "").rstrip("/")


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/tasks", response_model=CreateTaskResponse)
def create_task(request: CreateTaskRequest) -> CreateTaskResponse:
    """Create a background TTS synthesis task."""
    task_id = wrapper.create_tts_task(
        character_name=request.character_name,
        reference_audio_id=request.reference_audio_id,
        reference_audio_text=request.reference_audio_text,
        text=request.text,
    )
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
    if BASE_STATIC_URL:
        if status.get("save_path"):
            status["save_path"] = f"{BASE_STATIC_URL}/{Path(status['save_path']).name}"
        if status.get("save_path_compressed"):
            status["save_path_compressed"] = (
                f"{BASE_STATIC_URL}/{Path(status['save_path_compressed']).name}"
            )
    return TaskStatusResponse(**status)


app.mount(
    "/static",
    StaticFiles(directory=wrapper.output_dir, check_dir=True),
    name="static",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Basic health endpoint for readiness probes."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
