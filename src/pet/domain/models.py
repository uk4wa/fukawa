from dataclasses import dataclass, field

from pet.domain.value_objects import Name, PublicId


@dataclass(slots=True, frozen=True)
class Organization:
    public_id: PublicId
    name: Name = field(compare=False)

    @classmethod
    def create(
        cls,
        public_id: PublicId,
        name: Name,
    ):
        return cls(
            public_id=public_id,
            name=name,
        )
