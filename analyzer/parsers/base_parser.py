from abc import ABC, abstractmethod


class BaseParser(ABC):

    @abstractmethod
    def parse_file(self, file_path: str) -> dict:
        """
        Parse a source file and return a standardized analysis.
        """
        pass
