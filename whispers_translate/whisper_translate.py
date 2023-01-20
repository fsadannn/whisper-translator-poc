import os
import tempfile
from typing import Optional

# import numpy as np
import speech_recognition as sr
import torch
import whisper


class WhisperTranslator:
    __slots__ = ('model',)

    def __init__(self, model="base"):
        device = None

        if torch.cuda.is_available():
            device = torch.cuda.device(0)

        self.model: whisper.Whisper = whisper.load_model(
            model, device=device)

    def translate(self, audio_data: sr.AudioData, language: Optional[str] = None, translate=False, show_dict=False, **transcribe_options):
        """ Performs speech recognition on ``audio_data`` (an ``AudioData`` instance), using Whisper.

            The recognition language is determined by ``language``, an uncapitalized full language name like "english" or "chinese". See the full language list at https://github.com/openai/whisper/blob/main/whisper/tokenizer.py

             If show_dict is true, returns the full dict response from Whisper, including the detected language. Otherwise returns only the transcription.

            You can translate the result to english with Whisper by passing translate=True
        """
        try:
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            f.write(audio_data.get_wav_data())
            f.flush()
            result = self.model.transcribe(
                f.name,
                language=language,
                task="translate" if translate else None,
                fp16=torch.cuda.is_available(),
                **transcribe_options
            )
        finally:
            f.close()
            try:
                os.remove(f.name)
            except:
                pass

        # data = np.frombuffer(audio_data.get_raw_data(), np.int16).flatten().astype(
        #     np.float32) / 32768.0

        # # if audio_data.
        # chunk_length = len(data) // 2

        # data = data.reshape((chunk_length, 2))
        # data = data.mean(axis=1)

        # result = self.model.transcribe(
        #     data,
        #     language=language,
        #     task="translate" if translate else None,
        #     fp16=torch.cuda.is_available(),
        #     **transcribe_options
        # )

        # print("WhisperTranslator.translate",result)

        if show_dict:
            return result
        else:
            return result["text"]

    def translate_file(self, path: str, language: Optional[str] = None, translate=False, show_dict=False, **transcribe_options):
        """ Performs speech recognition on ``audio_data`` (an ``AudioData`` instance), using Whisper.

            The recognition language is determined by ``language``, an uncapitalized full language name like "english" or "chinese". See the full language list at https://github.com/openai/whisper/blob/main/whisper/tokenizer.py

             If show_dict is true, returns the full dict response from Whisper, including the detected language. Otherwise returns only the transcription.

            You can translate the result to english with Whisper by passing translate=True
        """

        result = self.model.transcribe(
            path,
            language=language,
            task="translate" if translate else None,
            fp16=torch.cuda.is_available(),
            **transcribe_options
        )

        if show_dict:
            return result
        else:
            return result["text"]
