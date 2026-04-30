from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated subject of a request.

    Built from a verified access token. Domain code should depend on this
    abstraction, not on Keycloak-specific structures.
    """

    subject: str
    username: str | None = None
    email: str | None = None
    realm_roles: frozenset[str] = field(default_factory=frozenset)
    client_roles: Mapping[str, frozenset[str]] = field(default_factory=lambda: MappingProxyType({}))
    scopes: frozenset[str] = field(default_factory=frozenset)
    raw_claims: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def has_realm_role(self, role: str) -> bool:
        return role in self.realm_roles

    def has_client_role(self, client_id: str, role: str) -> bool:
        return role in self.client_roles.get(client_id, frozenset())
