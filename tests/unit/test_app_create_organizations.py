import pytest
from pytest_mock import MockFixture

from pet.app.organizations import create_organization_cmd, CreateOrganizationCmdIn
from uuid import UUID


@pytest.mark.asyncio
async def test_1(mocker: MockFixture):

    uuid = UUID("11111111-1111-1111-1111-111111111111")

    cmd = CreateOrganizationCmdIn(name="Alice")

    uow = mocker.Mock()
    uow.orgs.create = mocker.Mock()

    result = await create_organization_cmd(
        uow=uow,
        cmd=cmd,
        uuid_gen=lambda: uuid,
    )

    uow.orgs.create.assert_called_once()
    (args,), _ = uow.orgs.create.call_args

    assert args.public_id == uuid
    assert args.name == cmd.name
    assert result.val == uuid
