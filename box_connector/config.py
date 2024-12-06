import os
import sys
from pathlib import Path
from distutils.util import strtobool
import logging

from pythonjsonlogger import jsonlogger
from dotenv import load_dotenv


sys.path.append(str(Path(__file__).parent.resolve()))
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

# [global]
# 処理の対象とするファイルの拡張子
SUPPORT_FILE_TYPES = (
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
    "TXT",
)

# [box_crawler.py]
# TrueならDBに記録されているファイルとフォルダは処理をスキップする
SKIP_EXISTING_ITEMS = strtobool(os.environ.get("SKIP_EXISTING_ITEMS", "False"))
# 処理対象とするBoxのフォルダのID
BOX_ROOT_FOLDER_IDS = list(map(int, os.environ["BOX_ROOT_FOLDER_IDS"].split(",")))

# [s3_writer.py]
# アップロード先のS3バケット
BUCKET_NAME = os.environ["BUCKET_NAME"]
# S3にアップロードする時のKeyのPrefix
S3_DOCUMENT_KEY_PREFIX = "docs/"
# S3にメタデータをアップロードする時のSuffix
METADATA_FILE_SUFFIX = ".metadata.json"
# メタデータに埋め込まれるBoxのURLのPrefix
SOURCE_URI_PREFIX = "https://app.box.com/"


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def setup_logging(log_level=logging.INFO):
    handlers = []
    formatter = CustomJsonFormatter("%(level)s %(name)s %(message)s", json_ensure_ascii=False)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    handlers.append(handler)
    logging.basicConfig(level=log_level, handlers=handlers, force=True)


setup_logging()
