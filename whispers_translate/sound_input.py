try:
    import pyaudiowpatch as pyaudio
    _IS_WINDOWS = True
except ImportError:
    import pyaudio
    _IS_WINDOWS = False

import audioop
from dataclasses import dataclass
from typing import List

import speech_recognition as sr
from pydub import AudioSegment


@dataclass
class DeviceInfo:
    name: str
    index: int


class AudioInput(sr.AudioSource):
    """
    Creates a new ``AudioInput`` instance, which represents a physical microphone on the computer or loopback dev. Subclass of ``AudioSource``.

    This will throw an ``AttributeError`` if you don't have PyAudio 0.2.11 or later installed.
    For loopback on windows use pyaudiowpatch

    If ``device_index`` is unspecified or ``None``, the default microphone is used as the audio source. Otherwise, ``device_index`` should be the index of the device to use for audio input.

    A device index is an integer between 0 and ``pyaudio.get_device_count() - 1`` (assume we have used ``import pyaudio`` beforehand) inclusive. It represents an audio device such as a microphone or speaker. See the `PyAudio documentation <http://people.csail.mit.edu/hubert/pyaudio/docs/>`__ for more details.

    The microphone audio is recorded in chunks of ``chunk_size`` samples, at a rate of ``sample_rate`` samples per second (Hertz). If not specified, the value of ``sample_rate`` is determined automatically from the system's microphone settings.

    Higher ``sample_rate`` values result in better audio quality, but also more bandwidth (and therefore, slower recognition). Additionally, some CPUs, such as those in older Raspberry Pi models, can't keep up if this value is too high.

    Higher ``chunk_size`` values help avoid triggering on rapidly changing ambient noise, but also makes detection less sensitive. This value, generally, should be left at its default.
    """

    def __init__(self, device_index=None, sample_rate=None, chunk_size=1024):
        assert device_index is None or isinstance(
            device_index, int), "Device index must be None or an integer"
        assert sample_rate is None or (isinstance(
            sample_rate, int) and sample_rate > 0), "Sample rate must be None or a positive integer"
        assert isinstance(
            chunk_size, int) and chunk_size > 0, "Chunk size must be a positive integer"

        audio = pyaudio.PyAudio()
        channels = 1
        try:
            count = audio.get_device_count()  # obtain device count
            if device_index is not None:  # ensure device index is in range
                assert 0 <= device_index < count, "Device index out of range ({} devices available; device index should be between 0 and {} inclusive)".format(
                    count, count - 1)

            device_info = audio.get_device_info_by_index(
                device_index) if device_index is not None else audio.get_default_input_device_info()

            if sample_rate is None:  # automatically set the sample rate to the hardware's default sample rate if not specified
                assert isinstance(device_info.get("defaultSampleRate"), (float, int)
                                  ) and device_info["defaultSampleRate"] > 0, "Invalid device info returned from PyAudio: {}".format(device_info)
                sample_rate = int(device_info["defaultSampleRate"])

            channels = device_info["maxInputChannels"]
        except Exception as e:
            raise e
        finally:
            audio.terminate()

        self.device_index = device_index
        self.format = pyaudio.paInt16  # 16-bit int sampling
        self.SAMPLE_WIDTH = pyaudio.get_sample_size(
            self.format)  # size of each sample
        self.CHANNELS = channels
        self.SAMPLE_RATE = sample_rate  # sampling rate in Hertz
        self.CHUNK = chunk_size  # number of frames stored in each buffer

        self.audio = None
        self.stream = None

    @staticmethod
    def list_microphone_names() -> List[DeviceInfo]:
        """
        Returns a list of the names of all available microphones. For microphones where the name can't be retrieved, the list entry contains ``None`` instead.

        The index of each microphone's name in the returned list is the same as its device index when creating a ``Microphone`` instance - if you want to use the microphone at index 3 in the returned list, use ``Microphone(device_index=3)``.
        """
        audio = pyaudio.PyAudio()
        try:
            result: List[DeviceInfo] = []
            for i in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(i)

                if device_info['maxInputChannels'] == 0:
                    continue
                result.append(DeviceInfo(
                    name=device_info['name'], index=device_info['index']))

        finally:
            audio.terminate()
        return result

    @staticmethod
    def list_working_microphones():
        """
        Returns a dictionary mapping device indices to microphone names, for microphones that are currently hearing sounds. When using this function, ensure that your microphone is unmuted and make some noise at it to ensure it will be detected as working.

        Each key in the returned dictionary can be passed to the ``Microphone`` constructor to use that microphone. For example, if the return value is ``{3: "HDA Intel PCH: ALC3232 Analog (hw:1,0)"}``, you can do ``Microphone(device_index=3)`` to use that microphone.
        """
        audio = pyaudio.PyAudio()
        try:
            result = {}
            for device_index in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(device_index)
                device_name = device_info.get("name")
                assert isinstance(device_info.get("defaultSampleRate"), (float, int)
                                  ) and device_info["defaultSampleRate"] > 0, "Invalid device info returned from PyAudio: {}".format(device_info)
                try:
                    # read audio
                    pyaudio_stream = audio.open(
                        input_device_index=device_index, channels=1, format=pyaudio.paInt16,
                        rate=int(device_info["defaultSampleRate"]), input=True
                    )
                    try:
                        buffer = pyaudio_stream.read(1024)
                        if not pyaudio_stream.is_stopped():
                            pyaudio_stream.stop_stream()
                    finally:
                        pyaudio_stream.close()
                except Exception:
                    continue

                # compute RMS of debiased audio
                energy = -audioop.rms(buffer, 2)
                energy_bytes = chr(energy & 0xFF) + chr((energy >> 8) & 0xFF) if bytes is str else bytes(
                    [energy & 0xFF, (energy >> 8) & 0xFF])  # Python 2 compatibility
                debiased_energy = audioop.rms(audioop.add(
                    buffer, energy_bytes * (len(buffer) // 2), 2), 2)

                if debiased_energy > 30:  # probably actually audio
                    result[device_index] = device_name
        finally:
            audio.terminate()
        return result

    def __enter__(self):
        assert self.stream is None, "This audio source is already inside a context manager"
        self.audio = pyaudio.PyAudio()
        try:
            self.stream = AudioInput.AudioInputStream(
                self.audio.open(
                    input_device_index=self.device_index, channels=self.CHANNELS, format=self.format,
                    rate=self.SAMPLE_RATE, frames_per_buffer=self.CHUNK, input=True,
                ),
                self.SAMPLE_WIDTH,
                channels=self.CHANNELS,
            )
        except Exception as e:
            self.audio.terminate()
            raise e

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stream.close()
        finally:
            self.stream = None
            self.audio.terminate()

    class AudioInputStream(object):
        def __init__(self, pyaudio_stream, sample_width: int, channels: int = 1):
            self.pyaudio_stream = pyaudio_stream
            self.channels = channels
            self.sample_width = sample_width

        def read(self, size):
            buffer = self.pyaudio_stream.read(
                size, exception_on_overflow=False)
            if self.channels > 1:
                buffer = audioop.tomono(
                    buffer, self.sample_width, 0.5, 0.5)

            return buffer

        def close(self):
            try:
                # sometimes, if the stream isn't stopped, closing the stream throws an exception
                if not self.pyaudio_stream.is_stopped():
                    self.pyaudio_stream.stop_stream()
            finally:
                self.pyaudio_stream.close()


def get_default_loopback_speakers_index() -> int:
    p = pyaudio.PyAudio()
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)

    default_speakers = p.get_device_info_by_index(
        wasapi_info["defaultOutputDevice"])

    if not default_speakers["isLoopbackDevice"]:
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break

    p.terminate()

    return default_speakers['index'], default_speakers


class AudioFile(sr.AudioSource):

    def __init__(self, path: str, chunk_size=1024):

        self.sound: AudioSegment = AudioSegment.from_file(path)
        # self.sound.set_channels(1)
        self.raw_data = self.sound._data

        # self.raw_data = np.frombuffer(sound._data, np.int16)

        self.SAMPLE_WIDTH = self.sound.sample_width
        self.CHANNELS = self.sound.channels
        self.SAMPLE_RATE = self.sound.frame_rate  # sampling rate in Hertz
        # number of frames stored in each buffer
        self.CHUNK = chunk_size
        self.stream = None
        self._current_position = 0

    def __enter__(self):
        assert self.stream is None, "This audio source is already inside a context manager"

        self.stream = AudioFile.FileInputStream(
            self.raw_data, self.SAMPLE_WIDTH, self.CHANNELS, self._current_position)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._current_position = self.stream._current_position
        # print(self._current_position, len(self.raw_data))
        self.stream = None
        return None

    class FileInputStream(object):
        def __init__(self, data, sample_width: int, channels: int = 1, current_position=0):
            self.pyaudio_stream = data
            self.channels = channels
            self.sample_width = sample_width
            self._current_position = current_position

        def read(self, size):
            buffer = self.pyaudio_stream[self._current_position:self._current_position + size]
            if self.channels > 1:
                buffer = audioop.tomono(
                    buffer, self.sample_width, 0.5, 0.5)

            self._current_position += size

            return buffer

        def close(self):
            pass
