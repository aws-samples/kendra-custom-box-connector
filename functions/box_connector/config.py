import os


BUCKET_NAME = os.environ["BUCKET_NAME"]
SOURCE_URI_PREFIX = "https://app.box.com/"
S3_KEY_PREFIX = "docs/"
TRASHED_S3_KEY_PREFIX = "trashed/"
ACL_FILE_KEY = "acl.json"
METADATA_FILE_SUFFIX = ".metadata.json"
