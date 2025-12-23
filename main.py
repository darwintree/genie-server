import genie_tts as genie
import os

# (Optional) You can set the number of cached character models and reference audios.
os.environ['Max_Cached_Character_Models'] = '3'
os.environ['Max_Cached_Reference_Audio'] = '3'

def main():
    genie.load_character(
        character_name="はづき",  # Replace with your character name
        onnx_model_dir=r"./models/はづき",  # Replace with the folder containing the ONNX model
        language="jp",  # Replace with language code, e.g., 'en', 'zh', 'jp'
    )

    genie.set_reference_audio(
        character_name="はづき",  # Use the same character name as above
        audio_path=r"./tmp_references/special_communications/490300191/4903001910010.ogg",  # Replace with path to your reference audio file
        audio_text="お誕生日おめでとうございます、プロデューサーさん♪",  # Replace with the text corresponding to the reference audio
    )

    genie.tts(
        character_name='はづき',  # Use the same character name
        text="私の誕生日もお祝いしてくださるなんて\nプロデューサーさんはマメですね～",  # Replace with the text you want to synthesize
        play=False,  # Whether to play the audio immediately
        split_sentence=True,  # Whether to split sentences before TTS
        save_path="./output/example.wav",  # Replace with path to save the audio file
    )


if __name__ == "__main__":
    main()
