from __future__ import division

import audioop
import multiprocessing
import threading
from multiprocessing.managers import DictProxy
from multiprocessing.synchronize import Event as MultiprocessingEvent

import flet
import speech_recognition as sr
from flet import (
    Column,
    Container,
    Dropdown,
    ElevatedButton,
    IconButton,
    ListView,
    Page,
    Ref,
    Row,
    Slider,
    Switch,
    Text,
    alignment,
    border,
    colors,
    icons,
)
from flet.dropdown import Option as DropdownOption

from whispers_translate.sound_input import AudioInput
from whispers_translate.whisper_translate import WhisperTranslator

IS_DEV_UI = False


def recognize_worker(
    recognize_thread_model_loaded: MultiprocessingEvent,
    audio_queue: multiprocessing.JoinableQueue,
    results_queue: multiprocessing.Queue,
    recognize_thread_event: MultiprocessingEvent,
    shared_language: DictProxy
):
    whisper_translator = WhisperTranslator(lazy=False)
    recognize_thread_model_loaded.set()

    while True:
        audio = audio_queue.get()  # retrieve the next audio processing job from the main thread

        if audio is None:
            audio_queue.task_done()
            results_queue.put(None)
            continue

        if recognize_thread_event.is_set():
            audio_queue.task_done()
            continue

        LANGUAGE: str = shared_language['language']

        translation = whisper_translator.translate(
            audio, language=LANGUAGE, translate=True)

        results_queue.put(translation)

        audio_queue.task_done()  # mark the audio processing job as completed in the queue


def listener_worker(device_index: int, audio_queue: multiprocessing.JoinableQueue, listener_thread_event: threading.Event, shared_data: DictProxy):
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.non_speaking_duration = 0.3
    phrase_time_limit = shared_data['phrase_time_limit']

    with AudioInput(device_index) as device:
        while True:  # repeatedly listen for phrases and put the resulting audio on the audio processing job queue
            r = recognizer.listen(device, phrase_time_limit=phrase_time_limit)
            audio_queue.put(r)
            if listener_thread_event.is_set():
                break


def translations_worker(results_queue: multiprocessing.Queue, list_view: Ref[ListView], listener_thread_event: threading.Event):
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


def main(page: Page):
    audio_queue = multiprocessing.JoinableQueue()
    results_queue = multiprocessing.Queue()

    manager = multiprocessing.Manager()
    shared_data = manager.dict()
    shared_data['language'] = 'english'
    shared_data['phrase_time_limit'] = 2.0

    recognize_thread_event = multiprocessing.Event()
    recognize_thread_model_loaded = multiprocessing.Event()

    if not IS_DEV_UI:
        recognize_thread = multiprocessing.Process(target=recognize_worker, args=(
            recognize_thread_model_loaded, audio_queue, results_queue, recognize_thread_event, shared_data))
        recognize_thread.start()
        recognize_thread_model_loaded.wait()

    listener_thread: threading.Thread = None
    listener_thread_event = threading.Event()

    page.theme_mode = 'dark'

    languages_dropdown = Ref[Dropdown]()
    devices_dropdown = Ref[Dropdown]()
    device_text = Ref[Text]()
    listen_switch = Ref[Switch]()
    list_view = Ref[ListView]()
    phrase_time_limit_slider = Ref[Slider]()
    phrase_time_limit_text = Ref[Text]()

    devices = AudioInput.list_microphone_names()

    def test_device(e):
        device_index = 0
        current_value = devices_dropdown.current.value

        for device in devices:
            if device.name == current_value:
                device_index = device.index
                break

        def _test_device(device_index: int, device_text: Ref[Text], page: Page):
            with AudioInput(device_index) as device:
                data = device.stream.read(device.CHUNK * 4)

                energy = audioop.rms(data, device.SAMPLE_WIDTH)

            device_text.current.value = f"energy: {energy}"
            page.update()

        t = threading.Thread(target=_test_device, args=(
            device_index, device_text, page))
        t.start()

    def change_language(e):
        current_value: str = languages_dropdown.current.value

        if current_value == 'Automatic':
            shared_data['language'] = None
            return

        shared_data['language'] = current_value.lower()

    page.add(
        Row([
            Text('Source language: '),
            Dropdown(
                options=[
                    DropdownOption('Spanish'),
                    DropdownOption('English'),
                    DropdownOption('Japanese'),
                    DropdownOption('Automatic')
                ],
                on_change=change_language, ref=languages_dropdown)
        ])
    )

    languages_dropdown.current.value = 'English'

    def stop_listening(e):
        if not listen_switch.current.value:
            return

        listen_switch.current.value = False
        listen_switch.current.on_change(None)
        listen_switch.current.update()

    def reload_devices(e):
        nonlocal devices
        devices = AudioInput.list_microphone_names()
        current_value = devices_dropdown.current.value
        devices_dropdown.current.options = [
            DropdownOption(device.name) for device in devices]
        devices_dropdown.current.value = current_value
        devices_dropdown.current.update()

        stop_listening(None)

    page.add(Row([
        Dropdown(
            options=[DropdownOption(device.name) for device in devices],
            ref=devices_dropdown, expand=True, on_change=stop_listening),
        IconButton(icons.REFRESH, on_click=reload_devices)
    ])
    )

    devices_dropdown.current.value = devices[0].name

    page.add(Row([
        ElevatedButton(text="Test Device", on_click=test_device),
        Text(ref=device_text)
    ]))

    def listen_device(e):
        nonlocal listener_thread

        if not listen_switch.current.value:
            listener_thread_event.set()
            recognize_thread_event.set()
            if not IS_DEV_UI:
                listener_thread.join()

            listener_thread = None

            audio_queue.put(None)
            recognize_thread_event.clear()

            return

        listener_thread_event.clear()

        device_index = 0
        current_value = devices_dropdown.current.value

        for device in devices:
            if device.name == current_value:
                device_index = device.index
                break

        if not IS_DEV_UI:
            listener_thread = threading.Thread(
                target=listener_worker, args=(device_index, audio_queue, listener_thread_event, shared_data))
            listener_thread.start()

    def end_phrase_time_limit(e):
        value: float = phrase_time_limit_slider.current.value
        shared_data['phrase_time_limit'] = value
        phrase_time_limit_text.current.value = f'Phrase time limit: {value:2.1f}s'
        phrase_time_limit_text.current.update()

    page.add(
        Row([
            Switch(label="Listen", value=False,
                   ref=listen_switch, on_change=listen_device),
            Row([
                Text('Phrase time limit', ref=phrase_time_limit_text),
                Slider(label="Phrase time limit {value}s", min=1.0, max=30.0,
                       divisions=29 * 2, on_change_start=stop_listening, on_change_end=end_phrase_time_limit, ref=phrase_time_limit_slider),
            ])

        ], alignment='spaceBetween')
    )

    phrase_time_limit_slider.current.value = 2.0
    phrase_time_limit_slider.current.on_change_end(None)

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

    if not IS_DEV_UI:
        translation_thread = threading.Thread(
            target=translations_worker, args=(results_queue, list_view, listener_thread_event))
        translation_thread.start()


if __name__ == "__main__":
    flet.app(target=main)
