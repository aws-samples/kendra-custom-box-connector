import json

import boto3
from botocore import exceptions

import config


s3_client = boto3.client("s3")

"""
こういうファイルだよ
[
    {
        "keyPrefix": "s3://bucketName/soumu/",
        "aclEntries": [
            {
                "Name": "soumu_group",
                "Type": "GROUP",
                "Access": "ALLOW"
            }
        ]
    },
    ...
]
"""


class Acl:
    def __init__(self):
        try:
            obj = s3_client.get_object(
                Bucket=config.BUCKET_NAME,
                Key=config.ACL_FILE_KEY,
            )
            acl_json = obj["Body"]
            self.json_hash = hash(acl_json)
            self.acl = json.load(acl_json)
        except exceptions.ClientError:
            self.json_hash = -1
            self.acl = []

    @staticmethod
    def _key_prefix(s3_key: str) -> str:
        # ACL の KeyPrefix の形式 (s3://~) に合わせる
        # ファイルがゴミ箱にある場合は、通常ある場所への ACL を操作する
        return f"s3://{config.BUCKET_NAME}/{s3_key}".replace(
            config.TRASHED_S3_KEY_PREFIX, config.S3_KEY_PREFIX, 1
        )

    def add_entry(self, s3_key: str, name: str, type_: str, access: str = "ALLOW"):
        key_prefix = self._key_prefix(s3_key)
        type_ = type_.upper()
        new_entry = {"Name": name, "Type": type_, "Access": access}
        opposite_access = "DENY" if access == "ALLOW" else "ALLOW"

        for item in self.acl:
            if item["keyPrefix"] == key_prefix:
                for entry in item["aclEntries"]:
                    if entry["Name"] == name and entry["Type"] == type_:
                        if entry["Access"] != access:
                            entry["Access"] = access
                        return
                    elif (
                        entry["Name"] == name
                        and entry["Type"] == type_
                        and entry["Access"] == opposite_access
                    ):
                        item["aclEntries"].remove(entry)
                        item["aclEntries"].append(new_entry)
                        return
                item["aclEntries"].append(new_entry)
                return

        self.acl.append({"keyPrefix": key_prefix, "aclEntries": [new_entry]})

    def delete_entry(self, s3_key: str, name: str, type_: str, access: str = "ALLOW"):
        key_prefix = self._key_prefix(s3_key)
        type_ = type_.upper()
        entry_to_delete = {"Name": name, "Type": type_, "Access": access}

        for item in self.acl:
            if item["keyPrefix"] == key_prefix:
                item["aclEntries"] = [
                    entry for entry in item["aclEntries"] if entry != entry_to_delete
                ]
                break

    def delete_key_prefix(self, s3_key: str):
        key_prefix = self._key_prefix(s3_key)
        self.acl = [item for item in self.acl if item["keyPrefix"] != key_prefix]

    def update_key_prefix(self, old_s3_key: str, new_s3_key: str):
        old_key_prefix = self._key_prefix(old_s3_key)
        new_key_prefix = self._key_prefix(new_s3_key)

        for item in self.acl:
            if item["keyPrefix"] == old_key_prefix:
                item["keyPrefix"] = new_key_prefix
                return

    def save(self):
        acl_json = json.dumps(self.acl).encode("utf-8")
        if hash(acl_json) == self.json_hash:
            return

        s3_client.put_object(
            Bucket=config.BUCKET_NAME,
            Key=config.ACL_FILE_KEY,
            Body=json.dumps(self.acl, ensure_ascii=False, indent=2).encode("utf-8"),
        )
