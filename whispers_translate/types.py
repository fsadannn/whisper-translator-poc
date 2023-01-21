from abc import abstractmethod
from typing import Protocol


class AudioDataP(Protocol):
    @abstractmethod
    def get_wav_data(self) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def get_raw_data(self) -> bytes:
        raise NotImplementedError
