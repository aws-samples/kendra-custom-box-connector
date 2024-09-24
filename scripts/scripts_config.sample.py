import os
import sys


def setup():
    # インポート対象の Box のフォルダ ID
    os.environ["FOLDER_ID"] = "1234"

    # DynamoDB のテーブル名
    os.environ["ITEM_TABLE"] = "KendraBoxConnectorStack-BoxConnectorItemTable****"
    os.environ["COLLABORATION_TABLE"] = (
        "KendraBoxConnectorStack-BoxConnectorCollaborationTable****"
    )

    # S3 のバケット名
    os.environ["BUCKET_NAME"] = "kendraboxconnectorstack-bucket****"

    # Kendra の Index 名
    os.environ["KENDRA_INDEX_ID"] = "****"

    # 以下は変更不要
    box_connector_dir = os.path.join(
        os.path.dirname(__file__), "../functions/box_connector"
    )
    sys.path.append(box_connector_dir)
