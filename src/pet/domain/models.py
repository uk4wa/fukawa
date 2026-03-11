from dataclasses import dataclass
from pet.domain.value_objects import PublicId, Name


@dataclass(slots=True, frozen=True)
class Organization:
    public_id: PublicId
    name: Name

    @classmethod
    def new(
        cls,
        public_id: PublicId,
        name: Name,
    ):
        return cls(
            public_id=public_id,
            name=name,
        )
