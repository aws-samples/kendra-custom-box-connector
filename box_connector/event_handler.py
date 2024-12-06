import os
import json
import traceback
import logging

from dateutil import parser
from datetime import timezone
from typing import Callable

import boto3

import s3_writer
from models import db, File, Folder, Collaboration
import utils


logger = logging.getLogger("event_handler")
sqs_client = boto3.client("sqs")
s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")


class ProcessingFailed(Exception):
    def __init__(self):
        message = "The processing failed."
        super().__init__(message)


def consume_messages() -> None:
    queue_url = sqs_client.get_queue_url(
        QueueName=os.environ["SQS_QUEUE_NAME"],
    )["QueueUrl"]

    count = 0

    while True:
        res = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)

        if "Messages" not in res:
            break

        for message in res["Messages"]:
            receipt_handle = message["ReceiptHandle"]
            payload = json.loads(message["Body"])

            try:
                logger.debug(payload)
                event_group, _ = payload["trigger"].split(".")

                if event_group == "FILE":
                    process_file_events(payload)
                elif event_group == "FOLDER":
                    process_folder_events(payload)
                elif event_group == "COLLABORATION":
                    process_collaboration_events(payload)

                sqs_client.delete_message(
                    QueueUrl=queue_url, ReceiptHandle=receipt_handle
                )
                count += 1

            except Exception as e:
                logger.error(
                    {
                        "text": "Error processing payload",
                        "payload": payload,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }
                )

    if count > 0:
        logger.info(f"{str(count)} messages have been completed.")
    else:
        logger.info("There were no messages.")


def _trash_file(file: File) -> None:
    # Trash されたら S3 から削除する
    # Restore されたら Box から再度ダウンロードする
    file.is_trashed = True
    file.file_needs_update = True
    file.metadata_needs_update = True


def _delete_item(file: File) -> None:
    file.is_deleted = True
    file.file_needs_update = True
    file.metadata_needs_update = True


def _restore_item(file: File) -> None:
    file.is_trashed = False
    file.file_needs_update = True
    file.metadata_needs_update = True


def _mark_item_metadata_needs_update(file: File) -> None:
    file.metadata_needs_update = True


def process_file_events(payload: dict) -> None:
    trigger = payload["trigger"]

    if trigger == "FILE.TRASHED":
        file = File.get_or_none(File.id == payload["source"]["id"])
        if file:
            _trash_file(file)
            file.save()

    elif trigger == "FILE.DELETED":
        file = File.get_or_none(File.id == payload["source"]["id"])
        if file:
            _delete_item(file)
            file.save()

    elif trigger == "FILE.RESTORED":
        file = File.get_or_none(File.id == payload["source"]["id"])
        if file:
            _restore_item(file)
            file.save()

    elif trigger == "FILE.UPLOADED":
        name = payload["source"]["name"]
        if not utils.is_support_file(name):
            return

        owner_type, owner_name = _get_accessible_type_and_name(
            payload["source"]["owned_by"]
        )

        data = {
            "id": payload["source"]["id"],
            "name": name,
            "parent_id": payload["source"]["parent"]["id"],
            "owner_type": owner_type,
            "owner_name": owner_name,
            "created_at": parser.parse(payload["source"]["created_at"]).astimezone(
                timezone.utc
            ),
            "last_updated_at": parser.parse(
                payload["source"]["modified_at"]
            ).astimezone(timezone.utc),
            "is_trashed": False,
            "is_deleted": False,
            "file_needs_update": True,
            "metadata_needs_update": True,
        }

        query = File.insert(data).on_conflict(conflict_target=[File.id], update=data)
        query.execute()

    elif trigger == "FILE.MOVED":
        file = File.get_or_none(File.id == payload["source"]["id"])
        if file:
            file.parent_id = payload["source"]["parent"]["id"]
            file.metadata_needs_update = True
            file.save()

    elif trigger == "FILE.COPIED":
        # 新しくコピーされたファイルに対して UPLOADED イベントが発生する
        pass

    elif trigger == "FILE.RENAMED":
        file = File.get_or_none(File.id == payload["source"]["id"])
        if file:
            file.name = payload["source"]["name"]
            file.metadata_needs_update = True
            file.save()


def _update_folder_recursively(folder_id: int, function: Callable) -> None:
    folder = Folder.get(Folder.id == folder_id)

    for sub_folder in Folder.select().where(Folder.parent_id == folder.id):
        _update_folder_recursively(sub_folder.id, function)

    for file in File.select().where(File.parent_id == folder.id):
        function(file)
        file.save()


def process_folder_events(payload: dict) -> None:
    trigger = payload["trigger"]

    if trigger == "FOLDER.CREATED":
        owner_type, owner_name = _get_accessible_type_and_name(
            payload["source"]["owned_by"]
        )

        try:
            parent_id = payload["source"]["parent"]["id"]
        except KeyError:
            parent_id = None

        data = {
            "id": payload["source"]["id"],
            "name": payload["source"]["name"],
            "parent_id": parent_id,
            "owner_type": owner_type,
            "owner_name": owner_name,
        }

        query = Folder.insert(data).on_conflict(
            conflict_target=[Folder.id], update=data
        )
        query.execute()

    elif trigger == "FOLDER.TRASHED":
        _update_folder_recursively(payload["source"]["id"], _trash_file)

    elif trigger == "FOLDER.DELETED":
        _update_folder_recursively(payload["source"]["id"], _delete_item)

    elif trigger == "FOLDER.RESTORED":
        _update_folder_recursively(payload["source"]["id"], _restore_item)

    elif trigger == "FOLDER.MOVED":
        folder = Folder.get(Folder.id == payload["source"]["id"])
        folder.parent_id = payload["source"]["parent"]["id"]
        folder.save()
        # 子アイテムの ACL を作成し直す
        _update_folder_recursively(
            payload["source"]["id"], _mark_item_metadata_needs_update
        )

    elif trigger == "FOLDER.COPIED":
        pass

    elif trigger == "FOLDER.RENAMED":
        folder = Folder.get(Folder.id == payload["source"]["id"])
        folder.name = payload["source"]["name"]
        folder.save()


def process_collaboration_events(payload: dict) -> None:
    trigger = payload["trigger"]
    if trigger == "COLLABORATION.CREATED":
        # ユーザーに招待している段階でメールアドレスが確定していないので何もしない
        pass

    elif trigger == "COLLABORATION.ACCEPTED":
        collaboration_id = payload["source"]["id"]
        item_id = payload["source"]["item"]["id"]
        item_type = payload["source"]["item"]["type"]

        if item_type == 'file':
            if not utils.is_support_file(payload["source"]["item"]["name"]):
                return

        accessible_type, accessible_name = _get_accessible_type_and_name(
            payload["source"]["accessible_by"]
        )

        data = {
            "id": collaboration_id,
            "item_id": item_id,
            "item_type": item_type,
            "accessible_type": accessible_type,
            "accessible_name": accessible_name,
            "status": payload["source"]["status"],
        }

        query = Collaboration.insert(data).on_conflict(
            conflict_target=[Collaboration.id], update=data
        )
        query.execute()

        if item_type == "file":
            file = File.get_or_none(File.id == item_id)
            if file:
                _mark_item_metadata_needs_update(file)
                file.save()
        else:
            _update_folder_recursively(item_id, _mark_item_metadata_needs_update)

    elif trigger == "COLLABORATION.REMOVED":
        collaboration = Collaboration.get(Collaboration.id == payload["source"]["id"])

        if collaboration.item_type == "file":
            file = File.get(File.id == collaboration.item_id)
            if file:
                _mark_item_metadata_needs_update(file)
                file.save()
        else:
            _update_folder_recursively(
                collaboration.item_id, _mark_item_metadata_needs_update
            )

        collaboration.delete()

    elif trigger == "COLLABORATION.UPDATED":
        # どのロールも読み取り権限はあるので考慮しない
        pass


def _get_accessible_type_and_name(accessible_dict: dict) -> (str, str):
    if accessible_dict["type"] == "user":
        return accessible_dict["type"], accessible_dict["login"].replace(" ", "+")
    return accessible_dict["type"], accessible_dict["name"]


def main() -> None:
    db.connect()
    db.create_tables([File, Folder, Collaboration])
    consume_messages()
    s3_writer.write_files()


if __name__ == "__main__":
    main()
