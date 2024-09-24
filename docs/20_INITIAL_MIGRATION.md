# 初期マイグレード

CDK アプリケーションをデプロイする前のファイルやフォルダは、初期マイグレードを行うことで Kendra や S3 にインポートされます。

## 1. Rye をインストールする
[レポジトリ](https://github.com/astral-sh/rye) を参考に Rye をインストールします。

## 2. 依存パッケージをインストールする
`pyproject.toml` があるディレクトリで以下のコマンドを実行します。

```
rye sync
```

## 3. スクリプトの設定を行う
`./scripts/scripts_config.sample.py` を `./scripts/scripts_config.py` にリネームし、各環境変数を設定します。

設定値は AWS Console から調べることができます。

## 4. 実行
以下のコマンドで初期マイグレードを実行します。

```
rye run ./scripts/initial_migrate.py
```

マイグレード後は自動スケジュールで Kendra に同期されるまで待つか、手動で Kendra のデータソースの Sync を実行してください。
