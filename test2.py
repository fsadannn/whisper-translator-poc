from queue import Queue
from threading import Thread

import speech_recognition as sr

from whispers_translate.sound_input import (
    AudioFile,
    AudioInput,
    get_default_loopback_speakers_index,
)
from whispers_translate.whisper_translate import WhisperTranslator

r = sr.Recognizer()
audio_queue = Queue()
whisper_translator = WhisperTranslator()
LANGUAGE = 'english'


def recognize_worker():
    # this runs in a background thread
    while True:
        audio = audio_queue.get()  # retrieve the next audio processing job from the main thread
        if audio is None:
            break  # stop processing if the main thread is done

        translation = whisper_translator.translate(
            audio, language=LANGUAGE, translate=True)
        print(translation)

        audio_queue.task_done()  # mark the audio processing job as completed in the queue


# start a new thread to recognize audio, while this thread focuses on listening
recognize_thread = Thread(target=recognize_worker)
recognize_thread.daemon = True
recognize_thread.start()

index, default_speakers = get_default_loopback_speakers_index()
# print(default_speakers)
m = AudioInput(index)


# m = AudioFile(
#     'D:\\musica\\Taylor Swift\\(2014.10.27) Taylor Swift - 1989 (Deluxe)\\Taylor Swift-17-I Know Places - Voice Memos.mp3', chunk_size=1024 * 1024)

with m as source:
    try:
        while True:  # repeatedly listen for phrases and put the resulting audio on the audio processing job queue
            audio_queue.put(r.listen(source, phrase_time_limit=2.0))
    except KeyboardInterrupt:  # allow Ctrl + C to shut down the program
        pass


audio_queue.put(None)  # tell the recognize_thread to stop
recognize_thread.join()  # wait for the recognize_thread to actually stop
