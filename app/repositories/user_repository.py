from typing import Protocol


class UserRepository(Protocol):
    def get_or_create(self, email: str) -> int: ...
