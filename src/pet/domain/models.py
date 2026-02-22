from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Organization:
    name: str

    @classmethod
    def new(cls, name: str):
        return cls(name=name)
