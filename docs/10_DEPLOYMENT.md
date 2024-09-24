# デプロイ手順

## 1. 環境の準備
デプロイには以下のソフトウェアを実行できる環境が必要です。

- AWS CDK
    - [Getting started with the AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html) のページを参考に、AWS CDK を実行できる環境を用意してください
- Docker

## 2. Box アプリケーションの作成

[MyApps](https://app.box.com/developers/console) から Box アプリケーションを作成します。

### 2.1. Create a Custom App
- `Select an app type to get started` の選択では `Custom App` を選択します。
- `App Name` や `Purpose` は自由に入力してください。
- `Authentication Method` の選択では`Server Authentication(with JWT)` を選択します。

入力後 `Create App` を押すとアプリケーションが作成されます。

### 2.2. General Settings タブ
- `Service Account Info` に表示されているメールアドレスは後ほど使用するため控えておいて下さい。

### 2.3. Configuration タブ
- `App Access Level` を `App + Enterprise Access` にします。
- `Application Scopes` では `Write all files and folders stored in Box` と `Manage webhooks` に最低限チェックします。
    - Read権限だけでも良さそうな気がしますが、`Necessary to download files and folders` とコメントがあるため。
- `Add and Manage Public Keys` で `Generate a Public/Private Keypair` を実行します。
    - ダウンロードできる `xxxx_config.json` ファイルは後ほど使用します。

設定変更後は `Save Changes` を押してください。


## 3. 認証情報のアップロード
Box の認証情報を 以下のコマンドで AWS Systems Manager Parameter Store にアップロードします。ファイル名は実際のものに合わせて変更してください。
```
aws ssm put-parameter \
--name /kendra-box-connector/box-config \
--type SecureString \
--value file://config.json
```

## 4. CDK アプリケーションのデプロイ
### 4.1. cdk.jsonのあるディレクトリで、依存モジュールをインストールします。

```
npm ci
```

### 4.2. 一度もそのリージョンで `cdk deploy` を実行したことがない場合は、初回のみ `cdk bootstrap` を実行します。
`cdk bootstrap` 実行により、AWS CDK が利用するリソースを CloudFormation スタックとしてAWSにデプロイします。

```
npx cdk bootstrap
```

### 4.3. デプロイを実行します。
```
npx cdk deploy
```

途中、下記のように表示されたら `y` と入力し、エンターキーを押してプロセスを進めてください。
```
Do you wish to deploy these changes (y/n)? y
```

デプロイが正常に完了すると、以下のように Webhook のエンドポイントが表示されるので控えて下さい。

```
 ✅  KendraBoxConnectorStack

✨  Deployment time: 72.83s

Outputs:
KendraBoxConnectorStack.BoxConnectorRestApiEndpointEF6CDB54 = https://********.execute-api.us-east-1.amazonaws.com/prod/
Stack ARN:
arn:aws:cloudformation:us-east-1:171368914135:stack/KendraBoxConnectorStack/d572d540-7662-11ef-9fee-0e10530f727b

✨  Total time: 97.21s
```

## 5. Box の Webhook 設定

### 5.1. Box アプリケーションのレビュー
先ほど作成した Box アプリケーションの `Authorization` タブを開き、`Review and Submit` ボタンを押してレビューを行います。

### 5.2. Webhook 設定
レビュー完了後、`Webhooks` タブを開き、`V2` を選択して Webhook を作成します。
- `URL Address` には CDK デプロイ後に表示された URL をコピーしてください。
- `Content Type` では Webhook の対象にするフォルダを選択します。
- 以下のイベントをトリガーに Webhook が飛ぶように設定してください。
```
FILE.TRASHED
FILE.DELETED
FILE.RESTORED
FILE.UPLOADED
FILE.MOVED
FILE.COPIED
FILE.RENAMED
FOLDER.CREATED
FOLDER.TRASHED
FOLDER.RESTORED
FOLDER.DELETED
FOLDER.MOVED
FOLDER.COPIED
FOLDER.RENAMED
COLLABORATION.CREATED
COLLABORATION.ACCEPTED
COLLABORATION.REJECTED
COLLABORATION.REMOVED
COLLABORATION.UPDATED
```

## 5.3. サービスアカウントへのフォルダ共有設定
Webhook の対象にしたフォルダに Lambda がアクセスできるように、手順2.2 で設定したメールアドレスに対してフォルダの共有設定を行ってください。
権限は最低限の `Viewer` で動作します。
