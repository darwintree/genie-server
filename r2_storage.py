import os

import boto3


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} must be set in the environment.")
    return value


class R2Storage:
    def __init__(self) -> None:
        account_id = _get_required_env("R2_ACCOUNT_ID")
        self._bucket = _get_required_env("R2_BUCKET")
        self._client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=_get_required_env("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=_get_required_env("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
        )

    def upload_audio(
        self,
        task_id: str,
        wav_path: str,
        ogg_path: str,
    ) -> tuple[str, str]:
        wav_key = f"wav/{task_id}.wav"
        ogg_key = f"ogg/{task_id}.ogg"
        self._client.upload_file(
            wav_path,
            self._bucket,
            wav_key,
            ExtraArgs={"ContentType": "audio/wav"},
        )
        self._client.upload_file(
            ogg_path,
            self._bucket,
            ogg_key,
            ExtraArgs={"ContentType": "audio/ogg"},
        )
        return wav_key, ogg_key
