import os
import sys


def setup():
    os.environ["FOLDER_ID"] = "283097226402"
    os.environ["ITEM_TABLE"] = (
        "KendraBoxConnectorStack-BoxConnectorItemTable550E7BA6-15NOEHTFPPSEB"
    )
    os.environ["COLLABORATION_TABLE"] = (
        "KendraBoxConnectorStack-BoxConnectorCollaborationTable23481A2E-PZWUPYCNAW63"
    )
    os.environ["BUCKET_NAME"] = "kendraboxconnectorstack-bucket83908e77-wmq1avpnapu1"
    os.environ["KENDRA_INDEX_ID"] = "b071afa9-377f-46a8-b2b1-1ab73704f351"

    box_connector_dir = os.path.join(
        os.path.dirname(__file__), "../functions/box_connector"
    )
    sys.path.append(box_connector_dir)
