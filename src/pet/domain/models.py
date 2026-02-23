from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, frozen=True)
class Organization:
    public_id: UUID
    name: str

    @classmethod
    def new(
        cls,
        public_id: UUID,
        name: str,
    ):
        return cls(
            public_id=public_id,
            name=name,
        )
