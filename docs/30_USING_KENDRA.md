# Kendra の 利用方法

このソリューションで構築したACLはBoxのメールアドレス、またはグループ名で指定することができます。

```
res = kendra.query(
    QueryText="肉じゃが",
    IndexId=os.environ['KENDRA_INDEX_ID'],
    AttributeFilter={
        "EqualsTo": {
            "Key": "_language_code",
            "Value": {
                "StringValue": "ja",
            },
        }
    },
    UserContext={
        # ACL の UserContext 指定
        # どちらかのみの指定も可能
        "UserId": "test-user@example.com",
        "Groups": ["test-group"]
    },
    PageSize=10,
)
```
