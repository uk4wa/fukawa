from typing import Protocol

from pet.domain.auth import Principal


class TokenVerifierAbstract(Protocol):
    async def verify(self, raw_token: str) -> Principal: ...
