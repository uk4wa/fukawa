from dataclasses import dataclass

from pet.domain.value_objects import OrgName, PublicId


@dataclass(slots=True, frozen=True)
class Organization:
    public_id: PublicId
    name: OrgName

    @classmethod
    def new(
        cls,
        public_id: PublicId,
        name: OrgName,
    ):
        return cls(
            public_id=public_id,
            name=name,
        )
