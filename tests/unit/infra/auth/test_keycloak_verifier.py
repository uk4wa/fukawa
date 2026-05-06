from pet.infra.auth.keycloak_verifier import _build_principal


def test_build_principal_extracts_keycloak_client_roles() -> None:
    principal = _build_principal(
        {
            "sub": "af37292c-3bfd-4d2e-89f3-673be75b5931",
            "iss": "http://auth.localhost:8080/realms/ukawa-pet",
            "preferred_username": "ukawa",
            "email": "ukawa@example.com",
            "scope": "openid orgs:write profile email",
            "resource_access": {
                "pet-backend": {
                    "roles": [
                        "orgs:write",
                    ],
                },
            },
        }
    )

    assert principal.subject == "af37292c-3bfd-4d2e-89f3-673be75b5931"
    assert principal.scopes == frozenset({"openid", "orgs:write", "profile", "email"})
    assert principal.client_roles["pet-backend"] == frozenset({"orgs:write"})
