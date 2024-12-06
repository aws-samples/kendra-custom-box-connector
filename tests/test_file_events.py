import os
import json

import boto3

from box_connector import event_handler, config


def test_file_uploaded():
    s3_client = boto3.client("s3")
    sqs_client = boto3.client("sqs")

    queue_url = sqs_client.get_queue_url(
        QueueName=os.environ["SQS_QUEUE_NAME"],
    )["QueueUrl"]

    payload = {
        "trigger": "FILE.UPLOADED",
        "source": {
            "id": "10",
            "type": "file",
            "name": "test.txt",
            "parent": {"id": 100},
            "created_at": "2012-12-12T10:53:43-08:00",
            "modified_at": "2012-12-12T10:53:43-08:00",
            "owned_by": {"type": "user", "login": "test-user1@example.com"},
        },
    }

    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload),
    )

    event_handler.main()

    # ファイルがアップロードされている
    res_1 = s3_client.get_object(
        Bucket=config.BUCKET_NAME, Key=config.S3_DOCUMENT_KEY_PREFIX + "10"
    )
    file_content = res_1["Body"].read().decode("utf-8")
    assert file_content == "test-content"

    # メタデータがアップロードされている
    res_2 = s3_client.get_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_DOCUMENT_KEY_PREFIX + "10" + config.METADATA_FILE_SUFFIX,
    )
    metadata = json.loads(res_2["Body"].read().decode("utf-8"))
    assert metadata == {
        "DocumentId": "10",
        "Attributes": {
            "_created_at": "2012-12-12T18:53:43",
            "_last_updated_at": "2012-12-12T18:53:43",
            "_source_uri": config.SOURCE_URI_PREFIX + "file/10",
        },
        "Title": "test.txt",
        "ContentType": "TXT",
        "AccessControlList": [
            {"Access": "ALLOW", "Name": "test-user1@example.com", "Type": "USER"}
        ],
    }
