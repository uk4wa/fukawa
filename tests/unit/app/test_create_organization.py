from uuid import UUID

import pytest
from pytest_mock import MockerFixture

from pet.app.errors import AppErrorCode
from pet.app.usecases.organizations import (
    CreateOrganizationCmdIn,
    create_organization_cmd,
)
from pet.domain.auth import Principal
from pet.domain.models import MemberRole, Membership, Organization
from pet.domain.value_objects import PublicId


def _make_principal(subject: str = "11111111-1111-1111-1111-111111111111") -> Principal:
    return Principal(
        subject=subject,
        issuer="http://auth.test/realms/test",
        username="ukawa",
        email="ukawa@example.com",
        scopes=frozenset({"organizations:write"}),
    )


def _make_user(mocker: MockerFixture, public_id: UUID) -> object:
    user = mocker.Mock()
    user.public_id = PublicId(value=public_id)
    return user


@pytest.mark.asyncio
async def test_create_organization_cmd_creates_org_and_membership(
    mocker: MockerFixture,
) -> None:
    org_uuid = UUID("11111111-1111-1111-1111-111111111111")
    membership_uuid = UUID("22222222-2222-2222-2222-222222222222")
    user_uuid = UUID("33333333-3333-3333-3333-333333333333")

    uuids = iter([org_uuid, membership_uuid])
    principal = _make_principal()
    user = _make_user(mocker, user_uuid)

    uow = mocker.Mock()
    uow.users.get_by_auth_identity = mocker.AsyncMock(return_value=user)
    uow.orgs.create = mocker.AsyncMock()
    uow.memberships.create = mocker.AsyncMock()

    cmd = CreateOrganizationCmdIn(name="Acme", principal=principal)

    result = await create_organization_cmd(uow=uow, cmd=cmd, uuid_gen=lambda: next(uuids))

    # correct public id returned
    assert result.value == org_uuid

    # user looked up by issuer+subject
    uow.users.get_by_auth_identity.assert_awaited_once_with(
        issuer=principal.issuer,
        subject=principal.subject,
    )

    # org created with correct name and public_id
    uow.orgs.create.assert_awaited_once()
    (org_arg,), _ = uow.orgs.create.call_args
    assert isinstance(org_arg, Organization)
    assert org_arg.public_id.value == org_uuid
    assert org_arg.name.value == "Acme"

    # membership created with owner role linking org and user
    uow.memberships.create.assert_awaited_once()
    (membership_arg,), _ = uow.memberships.create.call_args
    assert isinstance(membership_arg, Membership)
    assert membership_arg.public_id.value == membership_uuid
    assert membership_arg.org_public_id.value == org_uuid
    assert membership_arg.user_public_id.value == user_uuid
    assert membership_arg.role == MemberRole.owner


@pytest.mark.asyncio
async def test_create_organization_cmd_raises_not_found_when_user_missing(
    mocker: MockerFixture,
) -> None:
    uow = mocker.Mock()
    uow.users.get_by_auth_identity = mocker.AsyncMock(return_value=None)

    cmd = CreateOrganizationCmdIn(name="Acme", principal=_make_principal())

    from pet.app.errors import AppError

    with pytest.raises(AppError) as exc_info:
        await create_organization_cmd(uow=uow, cmd=cmd)

    assert exc_info.value.code == AppErrorCode.NOT_FOUND
    uow.orgs.create.assert_not_called()
    uow.memberships.create.assert_not_called()
