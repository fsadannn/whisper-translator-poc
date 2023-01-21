import audioop
import multiprocessing
import threading

import flet
import speech_recognition as sr
from flet import (
    Column,
    Container,
    Dropdown,
    ElevatedButton,
    ListView,
    Page,
    Ref,
    Row,
    Switch,
    Text,
    alignment,
    border,
    colors,
)
from flet.dropdown import Option as DropdownOption

from whispers_translate.sound_input import AudioInput
from whispers_translate.whisper_translate import WhisperTranslator

listener_thread_event = threading.Event()

list_view = Ref[ListView]()


def recognize_worker(recognize_thread_model_loaded, audio_queue, results_queue, recognize_thread_event, shared_language):
    whisper_translator = WhisperTranslator(lazy=False)
    recognize_thread_model_loaded.set()
    # this runs in a background thread
    # print('recognize_worker', flush=True)
    while True:
        audio = audio_queue.get()  # retrieve the next audio processing job from the main thread
        # print(audio, flush=True)
        if audio is None:
            audio_queue.task_done()
            results_queue.put(None)
            continue
            # break  # stop processing if the main thread is done

        if recognize_thread_event.is_set():
            audio_queue.task_done()
            continue

        LANGUAGE: str = shared_language['language']

        translation = whisper_translator.translate(
            audio, language=LANGUAGE, translate=True)
        # print(translation, flush=True)

        results_queue.put(translation)

        audio_queue.task_done()  # mark the audio processing job as completed in the queue


def listener_worker(device_index: int, audio_queue):
    # print('listener_worker', device_index)
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.non_speaking_duration = 0.3
    with AudioInput(device_index) as device:
        while True:  # repeatedly listen for phrases and put the resulting audio on the audio processing job queue
            r = recognizer.listen(device, phrase_time_limit=2.0)
            # print(r)
            audio_queue.put(r)
            if listener_thread_event.is_set():
                break


def translations_worker(results_queue):
    # print('translations_worker')

    current_text = Text('')
    list_view.current.controls.append(current_text)
    list_view.current.update()

    has_empty_translation = False

    while True:
        translation: str = results_queue.get()

        if listener_thread_event.is_set():
            continue

        if translation is None:
            continue

        if translation == '':
            if has_empty_translation:
                continue
            else:
                has_empty_translation = True
                current_text = Text('')
                list_view.current.controls.append(current_text)
                list_view.current.update()

        has_empty_translation = False

        if translation.endswith('...'):
            translation = translation[:-3]

        current_text.value = current_text.value + ' ' + translation
        current_text.update()
        list_view.current.update()

        if translation.endswith('.') or translation.endswith('?') or translation.endswith('!'):
            current_text = Text('')
            list_view.current.controls.append(current_text)
            list_view.current.update()

        # print(translation)


def main(page: Page):
    audio_queue = multiprocessing.JoinableQueue()
    results_queue = multiprocessing.Queue()

    manager = multiprocessing.Manager()
    shared_language = manager.dict()
    shared_language['language'] = 'english'

    recognize_thread_event = multiprocessing.Event()
    recognize_thread_model_loaded = multiprocessing.Event()

    listener_thread: threading.Thread = None
    recognize_thread = multiprocessing.Process(target=recognize_worker, args=(
        recognize_thread_model_loaded, audio_queue, results_queue, recognize_thread_event, shared_language))
    # print('loading model')

    recognize_thread.start()
    recognize_thread_model_loaded.wait()

    # print('model loaded successfully')

    page.theme_mode = 'dark'

    languages_dropdown = Ref[Dropdown]()
    devices_dropdown = Ref[Dropdown]()
    device_text = Ref[Text]()
    listen_switch = Ref[Switch]()

    devices = AudioInput.list_microphone_names()

    def button_clicked(e):
        device_index = 0
        current_value = devices_dropdown.current.value

        for device in devices:
            if device.name == current_value:
                device_index = device.index
                break

        with AudioInput(device_index) as device:
            data = device.stream.read(device.CHUNK * 8)

            energy = audioop.rms(data, device.SAMPLE_WIDTH)

        device_text.current.value = f"energy: {energy}"
        page.update()

    def change_language(e):
        current_value: str = languages_dropdown.current.value
        shared_language['language'] = current_value.lower()

    page.add(
        Row([
            Text('Source language: '),
            Dropdown(
                options=[DropdownOption('Spanish'), DropdownOption('English')],
                on_change=change_language, ref=languages_dropdown)
        ])
    )

    languages_dropdown.current.value = 'English'

    page.add(Dropdown(
        options=[DropdownOption(device.name) for device in devices],
        ref=devices_dropdown
    ))

    devices_dropdown.current.value = devices[0].name

    page.add(Row([
        ElevatedButton(text="Test Device", on_click=button_clicked),
        Text(ref=device_text)
    ]))

    def listen_device(e):
        nonlocal listener_thread

        if not listen_switch.current.value:
            listener_thread_event.set()
            recognize_thread_event.set()
            listener_thread.join()

            listener_thread = None

            audio_queue.put(None)
            recognize_thread_event.clear()

        listener_thread_event.clear()

        device_index = 0
        current_value = devices_dropdown.current.value

        for device in devices:
            if device.name == current_value:
                device_index = device.index
                break

        listener_thread = threading.Thread(
            target=listener_worker, args=(device_index, audio_queue,))
        listener_thread.start()

    page.add(Switch(label="Listen", value=False,
             ref=listen_switch, on_change=listen_device))

    page.add(Container(
        content=Column(
            [ListView(ref=list_view, expand=1, spacing=10, auto_scroll=True)]),
        margin=10,
        padding=10,
        alignment=alignment.center,
        border_radius=10,
        border=border.all(1, colors.BLUE_500),
        expand=True,
    ))

    page.update()

    translation_thread = threading.Thread(
        target=translations_worker, args=(results_queue,))
    translation_thread.start()


if __name__ == "__main__":
    flet.app(target=main)
