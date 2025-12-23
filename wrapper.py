import genie_tts as genie
import os
import time
import threading
from collections import deque
from typing import Deque, Dict, Literal, Optional, TypedDict

TaskState = Literal["pending", "running", "completed", "failed"]
TaskQueryState = Literal["pending", "running", "completed", "failed", "not_found"]


class TaskRecord(TypedDict):
    task_id: str
    character_name: str
    reference_audio_id: str
    reference_audio_text: str
    text: str
    save_path: str
    status: TaskState
    error: Optional[str]


class TaskStatus(TypedDict, total=False):
    status: TaskQueryState
    pending: int
    save_path: str
    error: Optional[str]
from downloader import download_and_convert_m4a_to_ogg

# (Optional) You can set the number of cached character models and reference audios.
os.environ['Max_Cached_Character_Models'] = '3'
os.environ['Max_Cached_Reference_Audio'] = '3'

class GenieWrapper:
    def __init__(self) -> None:
        self.model_base_dir = "./models"
        self.tmp_reference_dir = "./tmp_references"
        self.reference_resource_server = "https://service.sc-viewer.top/convert/direct"
        self.output_dir = "./output"
        self._tasks: Dict[str, TaskRecord] = {}
        self._queue: Deque[str] = deque()
        self._lock: threading.Lock = threading.Lock()
        self._condition: threading.Condition = threading.Condition(self._lock)
        self._worker: threading.Thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
    
    def _get_model_path(self, character_name: str) -> str:
        return f"{self.model_base_dir}/{character_name}"
    
    def _get_resource_url(self, resource_audio_id: str) -> str:
        return f"{self.reference_resource_server}/{resource_audio_id}.m4a"
    
    def _get_reference_audio_path(self, resource_audio_id: str) -> str:
        audio_path = f"{self.tmp_reference_dir}/{resource_audio_id}.ogg"
        if os.path.exists(audio_path):
            return audio_path
        # download and convert
        url = self._get_resource_url(resource_audio_id)
        download_and_convert_m4a_to_ogg(url, audio_path)
        return audio_path
    
    def _load_character(self, character_name: str) -> None:
        onnx_model_dir = self._get_model_path(character_name)
        language = "jp"
        genie.load_character(
            character_name=character_name,
            onnx_model_dir=onnx_model_dir,
            language=language,
        )

    def _get_task_id(self, character_name: str) -> str:
        random_suffix = os.urandom(4).hex()
        timestamp = int(time.time())
        return f"{character_name}_{timestamp}_{random_suffix}"
        
    def _get_output_save_path(self, task_id: str) -> str:
        return f"{self.output_dir}/{task_id}.wav"

    def _process_task(self, task: TaskRecord) -> None:
        audio_path = self._get_reference_audio_path(task["reference_audio_id"])
        self._load_character(task["character_name"])
        genie.set_reference_audio(
            character_name=task["character_name"],
            audio_path=audio_path,
            audio_text=task["reference_audio_text"],
        )
        genie.tts(
            character_name=task["character_name"],
            text=task["text"],
            play=False,
            split_sentence=True,
            save_path=task["save_path"],
        )

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._queue:
                    self._condition.wait()
                task_id = self._queue.popleft()
                task = self._tasks.get(task_id)
                if not task:
                    continue
                task["status"] = "running"
            try:
                self._process_task(task)
                with self._lock:
                    task["status"] = "completed"
            except Exception as exc:
                with self._lock:
                    task["status"] = "failed"
                    task["error"] = str(exc)

    def create_tts_task(self, character_name: str, reference_audio_id: str, reference_audio_text: str, text: str) -> str:
        task_id = self._get_task_id(character_name)
        save_path = self._get_output_save_path(task_id)
        task: TaskRecord = {
            "task_id": task_id,
            "character_name": character_name,
            "reference_audio_id": reference_audio_id,
            "reference_audio_text": reference_audio_text,
            "text": text,
            "save_path": save_path,
            "status": "pending",
            "error": None,
        }
        with self._condition:
            self._tasks[task_id] = task
            self._queue.append(task_id)
            self._condition.notify()
        return task_id
    
    def get_task_status(self, task_id: str) -> TaskStatus:
        with self._lock:
            task = self._tasks.get(task_id)
            pending = len(self._queue)
            if not task:
                not_found: TaskStatus = {
                    "status": "not_found",
                    "pending": pending,
                }
                return not_found
            return {
                "status": task["status"],
                "pending": pending,
                "save_path": task.get("save_path"),
                "error": task.get("error"),
            }
