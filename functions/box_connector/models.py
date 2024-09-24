import os

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection


class KeyIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "key-index"
        projection = AllProjection()

    source_type = UnicodeAttribute(hash_key=True)
    s3_key = UnicodeAttribute(range_key=True)


class ItemModel(Model):
    class Meta:
        table_name = os.environ["ITEM_TABLE"]

    item_id = UnicodeAttribute(hash_key=True)

    source_type = UnicodeAttribute(null=False)
    s3_key = UnicodeAttribute()

    name = UnicodeAttribute(null=True)
    owner_name = UnicodeAttribute(null=True)
    owner_type = UnicodeAttribute(null=True)

    key_index = KeyIndex()


class CollaborationModel(Model):
    class Meta:
        table_name = os.environ["COLLABORATION_TABLE"]

    item_id = UnicodeAttribute(hash_key=True)
    collaboration_id = UnicodeAttribute(range_key=True)

    accessible_name = UnicodeAttribute(null=False)
    accessible_type = UnicodeAttribute(null=False)
