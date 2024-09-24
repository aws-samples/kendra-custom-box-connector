import os

import boto3
import scripts_config

scripts_config.setup()
kendra = boto3.client("kendra")

res = kendra.query(
    QueryText="肉じゃが",
    IndexId=os.environ["KENDRA_INDEX_ID"],
    AttributeFilter={
        "EqualsTo": {
            "Key": "_language_code",
            "Value": {
                "StringValue": "ja",
            },
        }
    },
    UserContext={
        # ACL の UserContext 指定
        # どちらかのみの指定も可能
        "UserId": "test-user@example.com",
        "Groups": ["test-group"],
    },
    PageSize=10,
)

for item in res["ResultItems"]:
    print(item)
