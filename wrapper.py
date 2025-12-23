import genie_tts as genie
import os
import time
from downloader import download_and_convert_m4a_to_ogg

# (Optional) You can set the number of cached character models and reference audios.
os.environ['Max_Cached_Character_Models'] = '3'
os.environ['Max_Cached_Reference_Audio'] = '3'

class GenieWrapper:
    def __init__(self):
        self.model_base_dir = "./models"
        self.tmp_reference_dir = "./tmp_references"
        self.reference_resource_server = "https://service.sc-viewer.top/convert/direct"
        self.output_dir = "./output"
        pass
    
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
    
    def _load_character(self, character_name: str):
        onnx_model_dir = self._get_model_path(character_name)
        language = "jp"
        genie.load_character(
            character_name=character_name,
            onnx_model_dir=onnx_model_dir,
            language=language,
        )

    def _get_task_id(self, character_name: str):
        random_suffix = os.urandom(4).hex()
        timestamp = int(time.time())
        return f"{character_name}_{timestamp}_{random_suffix}"
        
    def _get_output_save_path(self, task_id: str):
        return f"{self.output_dir}/{task_id}.wav"

    def create_tts_task(self, character_name: str, reference_audio_id: str, reference_audio_text: str, text: str):
        # has cache, so don't worry if called multiple times

        audio_path = self._get_reference_audio_path(reference_audio_id)

        save_path = self._get_output_save_path(character_name)

        self._load_character(character_name)
        
        genie.set_reference_audio(
            character_name=character_name,
            audio_path=audio_path,
            audio_text=reference_audio_text,
        )
        
        genie.tts(
            character_name=character_name,
            text=text,
            play=False,
            split_sentence=True,
            save_path=save_path,
        )
        
        return save_path
    
    def get_task_status(self, task_id: str):
        # Dummy implementation for now
        return {
            "status": "completed",
            "pending": 0,
        }