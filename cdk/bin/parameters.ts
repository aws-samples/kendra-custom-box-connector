import * as cdk from 'aws-cdk-lib'

export interface AppParameters {
  // Lambda にマウントする一時ディスクのサイズ
  ephemeralStorageSize: cdk.Size
  // Kendra data source の自動同期スケジュール
  dataSourceSyncSchedule: string
  // Kendra のエディション
  kendraEdition: 'ENTERPRISE_EDITION' | 'DEVELOPER_EDITION'
  // Kendra のインデックス名
  kendraIndexName: string
  // Kendra のデータソース名
  kendraDataSourceName: string
}

export const devParameters: AppParameters = {
  ephemeralStorageSize: cdk.Size.mebibytes(512),
  dataSourceSyncSchedule: 'cron(0 15 * * ? *)',
  kendraEdition: 'DEVELOPER_EDITION',
  kendraIndexName: 'KendraIndex',
  kendraDataSourceName: 'BoxSyncedS3Bucket',
}
