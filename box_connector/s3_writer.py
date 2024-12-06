import json
import logging

import boto3

import config
from box import box_client
from models import File, Folder, Collaboration
import utils


logger = logging.getLogger("s3_writer")
s3_client = boto3.client("s3")


def write_files() -> None:
    for file in File.select().where(File.file_needs_update):
        if file.is_trashed:
            _delete_file_and_metadata(file)
            file.file_needs_update = False
            file.metadata_needs_update = False
            file.save()
        if file.is_deleted:
            file.delete()
        else:
            _save_file(file)
            file.file_needs_update = False
            file.save()

    for file in File.select().where(File.metadata_needs_update):
        _save_metadata(file)
        file.metadata_needs_update = False
        file.save()


def _save_file(file: File) -> None:
    file_content = box_client.downloads.download_file(file.id).read()
    key = config.S3_DOCUMENT_KEY_PREFIX + str(file.id)
    s3_client.put_object(Bucket=config.BUCKET_NAME, Key=key, Body=file_content)
    logger.info(f"Upload file to s3://{config.BUCKET_NAME}/{key}")


def _save_metadata(file: File) -> None:
    data = {
        "DocumentId": str(file.id),
        "Attributes": {
            "_created_at": file.created_at.isoformat(),
            "_last_updated_at": file.last_updated_at.isoformat(),
            "_source_uri": f"{config.SOURCE_URI_PREFIX}file/{file.id}",
        },
        "Title": file.name,
        "ContentType": _get_document_type(file.name),
        "AccessControlList": _get_access_control_list(file),
    }
    key = config.S3_DOCUMENT_KEY_PREFIX + str(file.id) + config.METADATA_FILE_SUFFIX
    s3_client.put_object(
        Bucket=config.BUCKET_NAME,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
    )
    logger.info(f"Upload metadata to s3://{config.BUCKET_NAME}/{key}")


def _delete_file_and_metadata(file: File) -> None:
    s3_client.delete_object(
        Bucket=config.BUCKET_NAME, Key=config.S3_DOCUMENT_KEY_PREFIX + str(file.id)
    )
    s3_client.delete_object(
        Bucket=config.BUCKET_NAME,
        Key=config.S3_DOCUMENT_KEY_PREFIX + str(file.id) + config.METADATA_FILE_SUFFIX,
    )


def _remove_duplicates(list_of_dicts: list[dict]) -> list[dict]:
    unique_dicts = {json.dumps(d, sort_keys=True) for d in list_of_dicts}
    return [json.loads(d) for d in unique_dicts]


def _get_access_control_list(file: File) -> list[dict]:
    access_control_list = [
        {"Name": file.owner_name, "Type": file.owner_type.upper(), "Access": "ALLOW"}
    ]

    for collaboration in Collaboration.select().where(Collaboration.item_id == file.id):
        access_control_list.append(
            {
                "Name": collaboration.accessible_name,
                "Type": collaboration.accessible_type,
                "Access": "ALLOW",
            }
        )

    current_folder_id = file.parent_id

    while True:
        folder = Folder.get_or_none(Folder.id == current_folder_id)
        if not folder:
            break

        access_control_list.append(
            {
                "Name": folder.owner_name,
                "Type": folder.owner_type.upper(),
                "Access": "ALLOW",
            }
        )

        for collaboration in Collaboration.select().where(
            Collaboration.item_id == current_folder_id
        ):
            access_control_list.append(
                {
                    "Name": collaboration.accessible_name,
                    "Type": collaboration.accessible_type,
                    "Access": "ALLOW",
                }
            )

        if current_folder_id in config.BOX_ROOT_FOLDER_IDS:
            break

        current_folder_id = folder.parent_id

    return _remove_duplicates(access_control_list)


def _get_document_type(name: str) -> str:
    # https://docs.aws.amazon.com/kendra/latest/dg/index-document-types.html
    ext = utils.get_ext(name)

    if ext in (
        "PDF",
        "HTML",
        "XML",
        "XSLT",
        "MD",
        "CSV",
        "XLS",
        "XLSX",
        "JSON",
        "RTF",
        "PPT",
        "PPTX",
        "DOC",
        "DOCX",
    ):
        return ext

    return "TXT"
