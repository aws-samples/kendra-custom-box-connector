# 初期インポート

初期インポートにはECSタスクを起動します。CDKデプロイを行う際にECSタスクを起動するコマンドが表示されます。

```
KendraBoxConnectorStack.BoxConnectorCrawlerCommand**** = aws ecs run-task \
    --cluster KendraBoxConnectorStack-BoxConnectorCluster**** \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-****],securityGroups=[sg-****]}" \
    --task-definition KendraBoxConnectorStackBoxConnectorTaskDefinition**** \
    --overrides '{"containerOverrides":[{"name":"box-connector","command":["box_crawler.py"],"environment":[{"name":"SKIP_EXISTING_ITEMS","value":"True"}]}]}'
```

`{"name":"SKIP_EXISTING_ITEMS","value":"True"}` この値を `True` にすると、DBに記録されているファイルはスキップされます。
全てのファイルをインポートしなおすには `False` にしてください。
