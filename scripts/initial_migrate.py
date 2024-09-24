import os
import box_sdk_gen

import scripts_config

scripts_config.setup()

from box_connector.box import initialize_box_client
from box_connector.models import ItemModel, CollaborationModel
from box_connector.acl import Acl
from box_connector import index
from box_connector import config as connector_config

box_client = initialize_box_client()


def fetch_existing_items():
    items = {}
    last_evaluated_key = None

    while True:
        result = ItemModel.scan(limit=1000, last_evaluated_key=last_evaluated_key)

        for item in result:
            items[item.item_id] = item

        if not result.last_evaluated_key:
            return items

        last_evaluated_key = result.last_evaluated_key


def process_box_items(folder_id, limit=1000):
    file_data_list = []
    offset = 0
    fields = ["id", "type", "name", "item_collection", "path_collection", "owned_by"]

    while True:
        box_items = [
            i
            for i in box_client.folders.get_folder_items(
                folder_id, limit=limit, offset=offset, fields=fields
            ).entries
        ]

        if not box_items:
            break

        for box_item in box_items:
            if isinstance(box_item, box_sdk_gen.schemas.folder_mini.FolderMini):
                process_folder(box_item)
                process_box_items(box_item.id)

            elif isinstance(box_item, box_sdk_gen.schemas.file_full.FileFull):
                process_file(box_item)

        # limit より取得できた item 数 が少なかったらループを抜ける
        if len(box_items) < limit:
            break

        offset += limit

    return file_data_list


def process_folder(folder: box_sdk_gen.schemas.folder_mini.FolderMini):
    item = ItemModel(folder.id)
    item.source_type = folder.type
    s3_key = (
        connector_config.S3_KEY_PREFIX
        + "/".join([e["id"] for e in folder.path_collection["entries"]])
    ) + f"/{folder.id}/"
    item.s3_key = s3_key
    item.name = folder.name
    owned_by_name, owned_by_type = index.get_accessible_name_and_type(folder.owned_by)
    item.owner_name = owned_by_name
    item.owner_type = owned_by_type
    item.save()

    # フォルダに持ち主がアクセスできるように設定
    acl = Acl()
    acl.add_entry(item.s3_key, item.owner_name, item.owner_type)

    # Collaborationsがアクセスできるように設定
    for box_collaboration in box_client.list_collaborations.get_folder_collaborations(
        folder.id
    ).entries:
        accessible_name, accessible_type = index.get_accessible_name_and_type(
            box_collaboration.accessible_by.__dict__
        )

        if "@boxdevedition.com" in accessible_name:
            continue

        acl.add_entry(
            item.s3_key,
            accessible_name,
            accessible_type,
        )

        collaboration = CollaborationModel(item.item_id, box_collaboration.id)
        collaboration.accessible_name = accessible_name
        collaboration.accessible_type = accessible_type
        collaboration.save()

    acl.save()


def process_file(file: box_sdk_gen.schemas.file_full.FileFull):
    item = ItemModel(file.id)
    item.source_type = file.type
    s3_key = (
        connector_config.S3_KEY_PREFIX
        + "/".join([e.id for e in file.path_collection.entries])
        + f"/{file.id}"
    )
    item.s3_key = s3_key
    item.name = file.name
    owned_by_name, owned_by_type = index.get_accessible_name_and_type(
        file.owned_by.__dict__
    )
    item.owner_type = owned_by_type
    item.owner_name = owned_by_name
    item.save()

    # メタデータを保存
    index.save_metadata(item)

    # ファイルに持ち主がアクセスできるように設定
    acl = Acl()
    acl.add_entry(item.s3_key, item.owner_name, item.owner_type)

    # Collaborationsがアクセスできるように設定
    for box_collaboration in box_client.list_collaborations.get_file_collaborations(
        file.id
    ).entries:
        accessible_name, accessible_type = index.get_accessible_name_and_type(
            box_collaboration.accessible_by.__dict__
        )

        if "@boxdevedition.com" in accessible_name:
            continue

        acl.add_entry(
            item.s3_key,
            accessible_name,
            accessible_type,
        )

        collaboration = CollaborationModel(item.item_id, box_collaboration.id)
        collaboration.accessible_name = accessible_name
        collaboration.accessible_type = accessible_type
        collaboration.save()

    acl.save()
    index.save_file(item)


def main():
    process_box_items(os.environ["FOLDER_ID"])


if __name__ == "__main__":
    main()
