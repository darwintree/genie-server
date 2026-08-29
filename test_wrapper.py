import tempfile
import threading
import unittest
from collections import deque
from pathlib import Path
from queue import Full
from unittest.mock import Mock, call, patch

from r2_storage import R2Storage
from wrapper import GenieWrapper, TaskRecord


class CompressionTest(unittest.TestCase):
    @patch("wrapper.AudioSegment.from_file")
    def test_compresses_to_ogg_opus(self, from_file: Mock) -> None:
        wrapper = object.__new__(GenieWrapper)

        wrapper._compress_wav_to_ogg("task.wav", "task.ogg")

        from_file.assert_called_once_with("task.wav", format="wav")
        from_file.return_value.export.assert_called_once_with(
            "task.ogg",
            format="ogg",
            codec="libopus",
            bitrate="48k",
        )


class ProcessTaskTest(unittest.TestCase):
    def test_uploads_both_formats_before_removing_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / "task.wav"
            ogg_path = Path(directory) / "task.ogg"
            wrapper = object.__new__(GenieWrapper)
            wrapper._storage = Mock()
            wrapper._storage.upload_audio.return_value = (
                "wav/task.wav",
                "ogg/task.ogg",
            )
            wrapper._get_reference_audio_path = Mock(return_value="reference.ogg")
            wrapper._load_character = Mock()
            wrapper._compress_wav_to_ogg = Mock(
                side_effect=lambda _wav, ogg: Path(ogg).write_bytes(b"ogg")
            )
            task: TaskRecord = {
                "task_id": "task",
                "character_name": "character",
                "reference_audio_id": "reference",
                "reference_audio_text": "reference text",
                "text": "text",
                "wav_path": str(wav_path),
                "ogg_path": str(ogg_path),
                "wav_key": None,
                "ogg_key": None,
                "status": "running",
                "error": None,
            }

            def write_wav(**kwargs: object) -> None:
                Path(str(kwargs["save_path"])).write_bytes(b"wav")

            with (
                patch("wrapper.genie.set_reference_audio"),
                patch("wrapper.genie.tts", side_effect=write_wav),
            ):
                wrapper._process_task(task)

            self.assertEqual(
                wrapper._storage.upload_audio.call_args,
                call("task", str(wav_path), str(ogg_path)),
            )
            self.assertEqual(task["wav_key"], "wav/task.wav")
            self.assertEqual(task["ogg_key"], "ogg/task.ogg")
            self.assertFalse(wav_path.exists())
            self.assertFalse(ogg_path.exists())


class TaskQueueTest(unittest.TestCase):
    def test_rejects_tasks_when_pending_queue_is_full(self) -> None:
        wrapper = object.__new__(GenieWrapper)
        wrapper.output_dir = Path("output")
        wrapper._tasks = {}
        wrapper._queue = deque(["existing"])
        wrapper._lock = threading.Lock()
        wrapper._condition = threading.Condition(wrapper._lock)
        wrapper._max_pending_tasks = 1

        with self.assertRaises(Full):
            wrapper.create_tts_task("character", "reference", "reference text", "text")

        self.assertEqual(list(wrapper._queue), ["existing"])
        self.assertEqual(wrapper._tasks, {})


class R2StorageTest(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "R2_ACCOUNT_ID": "account",
            "R2_BUCKET": "audio",
            "R2_ACCESS_KEY_ID": "key",
            "R2_SECRET_ACCESS_KEY": "secret",
        },
    )
    @patch("r2_storage.boto3.client")
    def test_upload_audio_sets_keys_and_content_types(self, boto_client: Mock) -> None:
        client = boto_client.return_value
        storage = R2Storage()

        keys = storage.upload_audio("task", "task.wav", "task.ogg")

        boto_client.assert_called_once_with(
            service_name="s3",
            endpoint_url="https://account.r2.cloudflarestorage.com",
            aws_access_key_id="key",
            aws_secret_access_key="secret",
            region_name="auto",
        )
        self.assertEqual(keys, ("wav/task.wav", "ogg/task.ogg"))
        self.assertEqual(
            client.upload_file.call_args_list,
            [
                call(
                    "task.wav",
                    "audio",
                    "wav/task.wav",
                    ExtraArgs={"ContentType": "audio/wav"},
                ),
                call(
                    "task.ogg",
                    "audio",
                    "ogg/task.ogg",
                    ExtraArgs={"ContentType": "audio/ogg"},
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
