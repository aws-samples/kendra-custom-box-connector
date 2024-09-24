import json

import boto3

import index
from models import ItemModel
import config


def test_folder_created():
    s3_client = boto3.client("s3")

    payload = {
        "trigger": "FOLDER.CREATED",
        "source": {
            "id": "1",
            "type": "folder",
            "name": "test-folder",
            "path_collection": {
                "entries": [
                    {"type": "folder", "id": "0", "name": "すべてのファイル"},
                ],
            },
            "owned_by": {"type": "user", "login": "test-user1@example.com"},
        },
    }

    index.process_folder_events(payload)

    obj = s3_client.get_object(Bucket=config.BUCKET_NAME, Key=config.ACL_FILE_KEY)
    acl = json.loads(obj["Body"].read().decode("utf-8"))

    # フォルダに対する ACL が作られている
    assert acl == [
        {
            "keyPrefix": f"s3://{config.BUCKET_NAME}/{config.S3_KEY_PREFIX}0/1/",
            "aclEntries": [
                {"Name": "test-user1@example.com", "Type": "USER", "Access": "ALLOW"}
            ],
        }
    ]


def test_folder_trashed_and_deleted():
    s3_client = boto3.client("s3")

    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_KEY_PREFIX + "0/1/10",
        Body=b"test-content",
    )

    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_KEY_PREFIX + "0/1/10" + config.METADATA_FILE_SUFFIX,
        Body=b"{}",
    )

    file_item = ItemModel("10")
    file_item.s3_key = config.S3_KEY_PREFIX + "0/1/10"
    file_item.source_type = "file"
    file_item.save()

    folder_item = ItemModel("1")
    folder_item.s3_key = config.S3_KEY_PREFIX + "0/1/"
    folder_item.source_type = "folder"
    folder_item.save()

    acl = [
        {
            "keyPrefix": f"s3://{config.BUCKET_NAME}/{config.S3_KEY_PREFIX}0/1/",
            "aclEntries": [
                {"Name": "test-user1@example.com", "Type": "USER", "Access": "ALLOW"},
            ],
        }
    ]

    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=config.ACL_FILE_KEY,
        Body=json.dumps(acl).encode("utf-8"),
    )

    trashed_payload = {
        "trigger": "FOLDER.TRASHED",
        "source": {
            "id": "1",
            "type": "folder",
        },
    }

    index.process_folder_events(trashed_payload)
    keys = [
        obj["Key"]
        for obj in s3_client.list_objects_v2(Bucket=config.BUCKET_NAME)["Contents"]
    ]

    # ゴミ箱にファイルが移動している
    assert keys == [
        config.ACL_FILE_KEY,
        config.TRASHED_S3_KEY_PREFIX + "0/1/10",
        config.TRASHED_S3_KEY_PREFIX + "0/1/10" + config.METADATA_FILE_SUFFIX,
    ]

    deleted_payload = {
        "trigger": "FOLDER.DELETED",
        "source": {
            "id": "1",
            "type": "folder",
        },
    }

    index.process_folder_events(deleted_payload)

    keys = [
        obj["Key"]
        for obj in s3_client.list_objects_v2(Bucket=config.BUCKET_NAME)["Contents"]
    ]

    # ゴミ箱のファイルが削除されている
    assert keys == [config.ACL_FILE_KEY]

    obj = s3_client.get_object(Bucket=config.BUCKET_NAME, Key=config.ACL_FILE_KEY)
    acl = json.loads(obj["Body"].read().decode("utf-8"))

    # フォルダに対する ACL が削除されている
    assert acl == []
