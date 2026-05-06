from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    issuer: str

    username: str
    email: str

    first_name: str | None = None
    last_name: str | None = None

    scopes: frozenset[str] = field(default_factory=frozenset)
    realm_roles: frozenset[str] = field(default_factory=frozenset)
    client_roles: Mapping[str, frozenset[str]] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    raw_claims: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def has_realm_role(self, role: str) -> bool:
        return role in self.realm_roles

    def has_client_role(self, client_id: str, role: str) -> bool:
        return role in self.client_roles.get(client_id, frozenset())
