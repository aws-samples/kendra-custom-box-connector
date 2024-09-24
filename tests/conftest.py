import boto3
import pytest
from pytest_mock import MockFixture
from moto import mock_aws

from models import ItemModel, CollaborationModel
import config


@pytest.fixture(autouse=True)
def mock_box_client(mocker: MockFixture):
    mock_client = mocker.patch("index.box_client")

    mock_file = mocker.Mock()
    mock_file.content.return_value = b"test-content"
    mock_client.file.return_value = mock_file

    mock_owned_by = mocker.Mock(login="test-user1@example.com")
    mock_item = mocker.Mock(owned_by=mock_owned_by)
    mock_collaborations = [
        mocker.Mock(
            item=mocker.Mock(type="folder"),
            accessible_by=mocker.Mock(type="user", login="test-user2@example.com"),
        ),
        mocker.Mock(
            item=mocker.Mock(type="folder"), accessible_by=mocker.Mock(type="group")
        ),
    ]
    # Mock の name 属性は後から設定する必要がある
    # https://python.readthedocs.io/en/latest/library/unittest.mock.html#unittest.mock.Mock
    mock_collaborations[1].accessible_by.name = "test-group"
    mock_item.get_collaborations.return_value = mock_collaborations
    mock_folder = mocker.Mock()
    mock_folder.get.return_value = mock_item
    mock_client.folder.return_value = mock_folder

    return mock_client


@mock_aws
@pytest.fixture(autouse=True)
def mock_dynamodb():
    mock = mock_aws()
    mock.start()

    s3_client = boto3.client("s3")
    s3_client.create_bucket(Bucket=config.BUCKET_NAME)
    ItemModel.create_table()
    CollaborationModel.create_table()

    yield

    mock.stop()
