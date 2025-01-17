import os

from peewee import *


db = PostgresqlDatabase(
    os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
)


class BaseModel(Model):
    class Meta:
        database = db


class File(BaseModel):
    id = BigIntegerField(primary_key=True)
    name = CharField()
    parent_id = CharField(null=True)
    owner_type = CharField()
    owner_name = CharField()
    created_at = DateTimeField()
    last_updated_at = DateTimeField()
    is_trashed = BooleanField()
    is_deleted = BooleanField()
    file_needs_update = BooleanField()
    metadata_needs_update = BooleanField()


class Folder(BaseModel):
    id = BigIntegerField(primary_key=True)
    name = CharField()
    parent_id = CharField(null=True)
    owner_type = CharField()
    owner_name = CharField()


class Collaboration(BaseModel):
    id = BigIntegerField(primary_key=True)
    item_id = BigIntegerField()
    item_type = CharField()
    accessible_type = CharField()
    accessible_name = CharField()
    status = CharField()
