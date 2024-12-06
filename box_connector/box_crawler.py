import box_sdk_gen
import logging
from typing import Union

import config
from box import box_client
import event_handler
import s3_writer
from models import db, File, Folder, Collaboration

logger = logging.getLogger("box_crawler")

FOLDER_FIELDS = [
    "id",
    "type",
    "name",
    "item_collection",
    "owned_by",
    "parent",
    "created_at",
    "modified_at",
]


def crawl_folder(folder_id, limit=1000) -> None:
    offset = 0

    while True:
        items = [
            i
            for i in box_client.folders.get_folder_items(
                folder_id, limit=limit, offset=offset, fields=FOLDER_FIELDS
            ).entries
        ]

        if not items:
            break

        for item in items:
            if isinstance(item, box_sdk_gen.schemas.folder_mini.FolderMini):
                process_folder(item)
                crawl_folder(item.id)

            elif isinstance(item, box_sdk_gen.schemas.file_full.FileFull):
                process_file(item)

        # limit より取得できた item 数 が少なかったらループを抜ける
        if len(items) < limit:
            break

        offset += limit


def process_folder(
    folder: Union[
        box_sdk_gen.schemas.FolderMini,
        box_sdk_gen.schemas.FolderFull,
    ],
) -> None:
    if config.SKIP_EXISTING_ITEMS and Folder.get_or_none(Folder.id == folder.id):
        return

    event_handler.process_folder_events(
        {"trigger": "FOLDER.CREATED", "source": folder.to_dict()}
    )
    for collaboration in box_client.list_collaborations.get_folder_collaborations(
        folder.id
    ).entries:
        if collaboration.item.id == folder.id:
            process_collaboration(collaboration)


def process_file(file: box_sdk_gen.schemas.FileFull) -> None:
    if config.SKIP_EXISTING_ITEMS and File.get_or_none(File.id == file.id):
        return

    event_handler.process_file_events(
        {"trigger": "FILE.UPLOADED", "source": file.to_dict()}
    )
    for collaboration in box_client.list_collaborations.get_file_collaborations(
        file.id
    ).entries:
        if collaboration.item.id == file.id:
            process_collaboration(collaboration)


def process_collaboration(collaboration: box_sdk_gen.schemas.Collaboration) -> None:
    if collaboration.status != "accepted":
        return
    event_handler.process_collaboration_events(
        {"trigger": "COLLABORATION.ACCEPTED", "source": collaboration.to_dict()}
    )


def main() -> None:
    db.connect()
    db.create_tables([File, Folder, Collaboration])

    for folder_id in config.BOX_ROOT_FOLDER_IDS:
        root_folder = box_client.folders.get_folder_by_id(
            folder_id, fields=FOLDER_FIELDS
        )
        process_folder(root_folder)
        crawl_folder(root_folder.id)

    s3_writer.write_files()


if __name__ == "__main__":
    main()
