import json

import boto3
from moto import mock_aws

import index
from models import ItemModel
import config


@mock_aws
def test_file_uploaded():
    s3_client = boto3.client("s3")

    payload = {
        "trigger": "FILE.UPLOADED",
        "source": {
            "id": "10",
            "type": "file",
            "name": "test.txt",
            "path_collection": {
                "entries": [
                    {"type": "folder", "id": "0", "name": "すべてのファイル"},
                    {"type": "folder", "id": "1", "name": "test-folder"},
                ],
            },
            "owned_by": {"type": "user", "login": "test-user1@example.com"},
        },
    }

    index.process_file_events(payload)

    # ファイルがアップロードされている
    res_1 = s3_client.get_object(
        Bucket=config.BUCKET_NAME, Key=config.S3_KEY_PREFIX + "0/1/10"
    )
    file_content = res_1["Body"].read().decode("utf-8")
    assert file_content == "test-content"

    # メタデータがアップロードされている
    res_2 = s3_client.get_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_KEY_PREFIX + "0/1/10" + config.METADATA_FILE_SUFFIX,
    )
    metadata = json.loads(res_2["Body"].read().decode("utf-8"))
    assert metadata == {
        "DocumentId": "10",
        "Attributes": {"_source_uri": config.SOURCE_URI_PREFIX + "file/10"},
        "Title": "test.txt",
    }


@mock_aws
def test_file_trashed():
    s3_client = boto3.client("s3")

    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_KEY_PREFIX + "0/1/10",
        Body=b"test-content",
    )

    source = ItemModel("10")
    source.source_type = "file"
    source.s3_key = config.S3_KEY_PREFIX + "0/1/10"
    source.name = "test.txt"
    source.save()

    metadata = {
        "DocumentId": "10",
        "Attributes": {"_source_uri": config.SOURCE_URI_PREFIX + "file/10"},
        "Title": "test.txt",
    }

    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_KEY_PREFIX + "0/1/10" + config.METADATA_FILE_SUFFIX,
        Body=json.dumps(metadata).encode("utf-8"),
    )

    payload = {
        "trigger": "FILE.TRASHED",
        "source": {
            "id": "10",
            "type": "file",
            "name": "test.txt",
        },
    }

    index.process_file_events(payload)

    # ファイルがゴミ箱に移動している
    res_1 = s3_client.get_object(
        Bucket=config.BUCKET_NAME, Key=config.TRASHED_S3_KEY_PREFIX + "0/1/10"
    )
    file_content = res_1["Body"].read().decode("utf-8")
    assert file_content == "test-content"

    # メタデータがゴミ箱に移動している
    res_2 = s3_client.get_object(
        Bucket=config.BUCKET_NAME,
        Key=config.TRASHED_S3_KEY_PREFIX + "0/1/10" + config.METADATA_FILE_SUFFIX,
    )
    assert metadata == json.loads(res_2["Body"].read().decode("utf-8"))
