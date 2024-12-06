import os
import sys
from pathlib import Path

import boto3
import pytest
from pytest_mock import MockFixture
from moto import mock_aws


sys.path.append(str((Path(__file__).parent.parent / "box_connector").resolve()))


@pytest.fixture(autouse=True)
def mock_box_client(mocker: MockFixture):
    mock_file = mocker.Mock()
    mock_file.read.return_value = b"test-content"

    mock_download = mocker.patch("event_handler.box_client.downloads.download_file")
    mock_download.return_value = mock_file


@mock_aws
@pytest.fixture(autouse=True)
def mock_dynamodb():
    mock = mock_aws()
    mock.start()

    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs")

    s3_client.create_bucket(
        Bucket=os.environ["BUCKET_NAME"],
        CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
    )
    sqs_client.create_queue(QueueName=os.environ["SQS_QUEUE_NAME"])

    yield

    mock.stop()
