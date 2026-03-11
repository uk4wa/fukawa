import pytest
from pytest_mock import MockerFixture

from pet.app.organizations import (
    create_organization_cmd,
    CreateOrganizationCmdIn,
)
from pet.domain.models import Organization as OrganizationORM
from uuid import UUID


@pytest.mark.asyncio
async def test_create_organization_cmd_creates_domain_org_and_returns_public_id(
    mocker: MockerFixture,
):

    uuid = UUID("11111111-1111-1111-1111-111111111111")

    cmd = CreateOrganizationCmdIn(name="Alice")

    uow = mocker.Mock()

    result = await create_organization_cmd(
        uow=uow,
        cmd=cmd,
        uuid_gen=lambda: uuid,
    )

    uow.orgs.create.assert_called_once()
    (args,), _ = uow.orgs.create.call_args

    assert isinstance(args, OrganizationORM)
    assert args.public_id.value == uuid
    assert args.name.value == cmd.name
    assert result.val == uuid
