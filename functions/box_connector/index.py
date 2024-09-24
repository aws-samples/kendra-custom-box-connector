import os
import json
import traceback
from typing import List

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
import boto3

import models
from box import box_client
from acl import Acl
from models import ItemModel, CollaborationModel
import config


os.environ["POWERTOOLS_SERVICE_NAME"] = "box_connector"
logger = Logger()

s3_client = boto3.client("s3")
kendra_client = boto3.client("kendra")
ssm_client = boto3.client("ssm")


class ProcessingFailed(Exception):
    def __init__(self):
        message = "The processing failed."
        super().__init__(message)


def handler(event: SQSEvent, context: LambdaContext):
    for record in event["Records"]:
        payload = None
        try:
            payload = json.loads(record["body"])
            logger.info(payload)
            event_group, _ = payload["trigger"].split(".")

            if event_group == "FILE":
                process_file_events(payload)
            elif event_group == "FOLDER":
                process_folder_events(payload)
            elif event_group == "COLLABORATION":
                process_collaboration_events(payload)

        except models.ItemModel.DoesNotExist:
            logger.warning(f"Item record not found in the database, skipping.")
            continue

        except Exception as e:
            logger.error(
                {
                    "text": "Error processing payload",
                    "payload": payload,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            raise ProcessingFailed()


def process_file_events(payload: dict):
    trigger = payload["trigger"]

    if trigger == "FILE.TRASHED":
        item = ItemModel.get(payload["source"]["id"])
        trash_or_restore_file(item, is_trashed=True)

    elif trigger == "FILE.DELETED":
        item = ItemModel.get(payload["source"]["id"])
        delete_file(item)
        acl = Acl()
        acl.delete_key_prefix(item.s3_key)
        acl.save()

    elif trigger == "FILE.RESTORED":
        item = ItemModel.get(payload["source"]["id"])
        trash_or_restore_file(item, is_trashed=False)

    elif trigger == "FILE.UPLOADED":
        try:
            item = ItemModel.get(payload["source"]["id"])
        except ItemModel.DoesNotExist:
            # DB にアイテム情報がない（初回アップロード時）
            item = ItemModel(payload["source"]["id"])
            item.source_type = payload["source"]["type"]
            item.s3_key = construct_s3_key(payload["source"])
            item.name = payload["source"]["name"]
            owned_by_name, owned_by_type = get_accessible_name_and_type(
                payload["source"]["owned_by"]
            )
            item.owner_name = owned_by_name
            item.owner_type = owned_by_type

            item.save()

            # メタデータを保存
            save_metadata(item)

            # ファイルに持ち主がアクセスできるように設定
            acl = Acl()
            acl.add_entry(item.s3_key, item.owner_name, item.owner_type)

            # Collaborationsがアクセスできるように設定
            for collaboration in CollaborationModel.query(item.item_id):
                acl.add_entry(
                    item.s3_key,
                    collaboration.accessible_name,
                    collaboration.accessible_type,
                )

            acl.save()

        save_file(item)

    elif trigger == "FILE.MOVED":
        item = ItemModel.get(payload["source"]["id"])

        new_s3_path = construct_s3_key(payload["source"])

        # ファイルとメタデータを移動
        move_object(item.s3_key, new_s3_path)
        move_object(
            item.s3_key + config.METADATA_FILE_SUFFIX,
            new_s3_path + config.METADATA_FILE_SUFFIX,
        )

        # DB に保存されている S3 Key も変更しておく
        item.s3_key = new_s3_path
        item.save()

    elif trigger == "FILE.COPIED":
        # 新しくコピーされたファイルに対して UPLOADED イベントが発生する
        pass

    elif trigger == "FILE.RENAMED":
        item = ItemModel.get(payload["source"]["id"])
        item.name = payload["source"]["name"]
        item.save()


def process_folder_events(payload: dict):
    trigger = payload["trigger"]

    if trigger == "FOLDER.CREATED":
        # フォルダ情報を DB に保存
        item = ItemModel(payload["source"]["id"])
        item.source_type = payload["source"]["type"]
        item.s3_key = construct_s3_key(payload["source"])
        item.name = payload["source"]["name"]
        (
            owner_name,
            owner_type,
        ) = get_accessible_name_and_type(payload["source"]["owned_by"])
        item.owner_name = owner_name
        item.owner_type = owner_type
        item.save()

        # フォルダに持ち主がアクセスできるように設定
        acl = Acl()
        acl.add_entry(item.s3_key, item.owner_name, item.owner_type)

        # Collaborationsがアクセスできるように設定
        for collaboration in CollaborationModel.query(item.item_id):
            acl.add_entry(
                item.s3_key,
                collaboration.accessible_name,
                collaboration.accessible_type,
            )

        acl.save()

    elif trigger == "FOLDER.TRASHED":
        # フォルダ情報を DB から取得
        item = ItemModel.get(payload["source"]["id"])

        # フォルダの S3 Key から始まるフォルダを取得
        for folder_item in ItemModel.key_index.query(
            "folder", ItemModel.s3_key.startswith(item.s3_key)
        ):
            # フォルダ内のフォルダをゴミ箱に移す
            folder_item.s3_key = item.s3_key.replace(
                config.S3_KEY_PREFIX, config.TRASHED_S3_KEY_PREFIX, 1
            )
            folder_item.save()

        # フォルダの S3 Key から始まるファイルを取得
        for file_item in ItemModel.key_index.query(
            "file", ItemModel.s3_key.startswith(item.s3_key)
        ):
            # フォルダ内のファイルをゴミ箱に移す
            trash_or_restore_file(file_item, is_trashed=True)

        # フォルダをゴミ箱に移動
        item.s3_key = item.s3_key.replace(
            config.S3_KEY_PREFIX, config.TRASHED_S3_KEY_PREFIX, 1
        )
        item.save()

    elif trigger == "FOLDER.RESTORED":
        # "FOLDER.TRASHED" の逆を行う
        # （ゴミ箱にあるフォルダやファイルを元に位置に戻す）
        item = ItemModel.get(payload["source"]["id"])

        for folder_item in ItemModel.key_index.query(
            "folder", ItemModel.s3_key.startswith(item.s3_key)
        ):
            folder_item.s3_key = item.s3_key.replace(
                config.TRASHED_S3_KEY_PREFIX, config.S3_KEY_PREFIX, 1
            )
            folder_item.save()

        for file_item in ItemModel.key_index.query(
            "file", ItemModel.s3_key.startswith(item.s3_key)
        ):
            trash_or_restore_file(file_item, is_trashed=False)

        item.s3_key = item.s3_key.replace(
            config.TRASHED_S3_KEY_PREFIX, config.S3_KEY_PREFIX, 1
        )
        item.save()

    elif trigger == "FOLDER.DELETED":
        acl = Acl()

        # フォルダ情報を DB から取得
        item = ItemModel.get(payload["source"]["id"])

        # フォルダの S3 Key から始まるフォルダを取得
        for folder_item in ItemModel.key_index.query(
            "folder", ItemModel.s3_key.startswith(item.s3_key)
        ):
            # DB の情報と ACL を削除する
            folder_item.delete()
            acl.delete_key_prefix(folder_item.s3_key)

        # フォルダの S3 Key から始まるファイルを取得
        for file_item in ItemModel.key_index.query(
            "file", ItemModel.s3_key.startswith(item.s3_key)
        ):
            # ファイルと ACL を削除
            delete_file(file_item)
            acl.delete_key_prefix(file_item.s3_key)

        # フォルダ情報と ACL を削除
        item.delete()
        acl.delete_key_prefix(item.s3_key)
        acl.save()

    elif trigger == "FOLDER.MOVED":
        acl = Acl()

        item = ItemModel.get(payload["source"]["id"])
        old_s3_key = item.s3_key
        new_s3_key = construct_s3_key(payload["source"])
        item.s3_key = new_s3_key
        acl.update_key_prefix(old_s3_key, new_s3_key)

        for folder_item in ItemModel.key_index.query(
            "folder", ItemModel.s3_key.startswith(old_s3_key)
        ):
            folder_old_s3_key = folder_item.get_s3_path()
            folder_new_s3_key = folder_old_s3_key.replace(old_s3_key, new_s3_key, 1)
            acl.update_key_prefix(folder_old_s3_key, folder_new_s3_key)
            folder_item.save()

        for file_item in ItemModel.key_index.query(
            "file", ItemModel.s3_key.startswith(item.s3_key)
        ):
            file_old_s3_key = file_item.get_s3_path()
            file_new_s3_key = file_old_s3_key.replace(old_s3_key, new_s3_key, 1)

            move_object(file_old_s3_key, file_new_s3_key)

            acl.update_key_prefix(file_old_s3_key, file_new_s3_key)
            file_item.save()

        item.save()
        acl.save()

    elif trigger == "FOLDER.COPIED":
        pass

    elif trigger == "FOLDER.RENAMED":
        item = ItemModel.get(payload["source"]["id"])
        item.name = payload["source"]["name"]
        item.save()


def process_collaboration_events(payload: dict):
    trigger = payload["trigger"]
    if trigger == "COLLABORATION.CREATED":
        pass

    elif trigger == "COLLABORATION.ACCEPTED":
        accessible_name, accessible_type = get_accessible_name_and_type(
            payload["source"]["accessible_by"]
        )

        collaboration = CollaborationModel(
            payload["source"]["item"]["id"], payload["source"]["id"]
        )
        collaboration.accessible_name = accessible_name
        collaboration.accessible_type = accessible_type
        collaboration.save()

        try:
            item = ItemModel.get(payload["source"]["item"]["id"])
        except models.ItemModel.DoesNotExist:
            # フォルダ作成と同時にコラボレーションの設定をすると先にコラボレーションのイベントが到着する場合がある
            return

        acl = Acl()
        acl.add_entry(item.s3_key, accessible_name, accessible_type)
        acl.save()

    elif trigger == "COLLABORATION.REMOVED":
        collaboration = CollaborationModel(
            payload["source"]["item"]["id"], payload["source"]["id"]
        )
        collaboration.delete()

        acl = Acl()
        accessible_name, accessible_type = get_accessible_name_and_type(
            payload["source"]["accessible_by"]
        )
        item = ItemModel.get(payload["source"]["item"]["id"])
        acl.delete_entry(item.s3_key, accessible_name, accessible_type)
        acl.save()

    elif trigger == "COLLABORATION.UPDATED":
        pass


def trash_or_restore_file(item: ItemModel, is_trashed: bool):
    if is_trashed:
        prefix_to_replace = config.S3_KEY_PREFIX
        prefix_to_set = config.TRASHED_S3_KEY_PREFIX
    else:
        prefix_to_replace = config.TRASHED_S3_KEY_PREFIX
        prefix_to_set = config.S3_KEY_PREFIX

    new_s3_key = item.s3_key.replace(prefix_to_replace, prefix_to_set, 1)
    move_object(item.s3_key, new_s3_key)
    move_object(
        item.s3_key + config.METADATA_FILE_SUFFIX,
        new_s3_key + config.METADATA_FILE_SUFFIX,
    )

    item.s3_key = new_s3_key
    item.save()


def construct_s3_key(source_dict: dict):
    folder_ids: List[str] = []

    for e in source_dict["path_collection"]["entries"]:
        if e["type"] == "folder":
            folder_ids.append(e["id"])

    s3_path = config.S3_KEY_PREFIX + "/".join(folder_ids) + "/" + source_dict["id"]
    if source_dict["type"] == "folder":
        s3_path += "/"

    return s3_path


def get_accessible_name_and_type(accessible_dict: dict) -> (str, str):
    if accessible_dict["type"] == "user":
        return accessible_dict["login"].replace(" ", "+"), accessible_dict["type"]
    return accessible_dict["name"], accessible_dict["type"]


def save_file(source: ItemModel) -> None:
    file_content = box_client.downloads.download_file(source.item_id).read()
    s3_client.put_object(
        Bucket=config.BUCKET_NAME, Key=source.s3_key, Body=file_content
    )


def save_metadata(source: ItemModel):
    data = {
        "DocumentId": source.item_id,
        "Attributes": {
            "_source_uri": f"{config.SOURCE_URI_PREFIX}file/{source.item_id}",
        },
        "Title": source.name,
    }

    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=source.s3_key + config.METADATA_FILE_SUFFIX,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def delete_file(source: ItemModel):
    delete_object(source.s3_key)
    delete_object(source.s3_key + config.METADATA_FILE_SUFFIX)
    source.delete()


def move_object(key_from: str, key_to: str):
    s3_client.copy_object(
        Bucket=config.BUCKET_NAME,
        Key=key_to,
        CopySource={"Bucket": config.BUCKET_NAME, "Key": key_from},
    )
    s3_client.delete_object(Bucket=config.BUCKET_NAME, Key=key_from)


def delete_object(key: str) -> None:
    s3_client.delete_object(Bucket=config.BUCKET_NAME, Key=key)
