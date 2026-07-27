from typing import Protocol


class JtiGenerator(Protocol):
    def __call__(self) -> str: ...
