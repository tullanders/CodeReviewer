from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CodeFile:
    path: str
    content: str
    language: str


class BaseRetriever(ABC):
    @abstractmethod
    def fetch(self, url: str) -> list[CodeFile]:
        pass
