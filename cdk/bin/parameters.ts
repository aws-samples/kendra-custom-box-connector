import * as events from 'aws-cdk-lib/aws-events'

export interface AppParameters {
  // Event Handlerの起動スケジュール
  eventHandlerSchedule: events.Schedule
  // Kendra data sourceの自動同期スケジュール
  dataSourceSyncSchedule: string
  // Kendraのエディション
  kendraEdition: 'ENTERPRISE_EDITION' | 'DEVELOPER_EDITION'
  // Kendraのインデックス名
  kendraIndexName: string
  // Kendraのデータソース名
  kendraDataSourceName: string
  // NAT Gatewayの代わりにt4g.nanoのNATインスタンスを利用する
  // vpcIdの指定とは併用できない
  cheapVpc?: boolean
  // 既存のVPCを利用する
  vpcId?: string
  // Auroraに作成されるデータベース名
  databaseName: string
  // VPC内に踏み台用のEC2インスタンスを生成する
  createBastion: boolean
  // 処理対象とするBoxのフォルダのID
  boxRootFolderIds: number[]
  // この回数処理に失敗したWebhookはDLQに送られる
  maxReceiveCount: number
}

export const devParameters: AppParameters = {
  eventHandlerSchedule: events.Schedule.cron({ minute: '0', hour: '16' }),
  dataSourceSyncSchedule: 'cron(0 17 * * ? *)',
  kendraEdition: 'DEVELOPER_EDITION',
  kendraIndexName: 'KendraIndex',
  kendraDataSourceName: 'BoxSyncedS3Bucket',
  cheapVpc: false,
  databaseName: 'box',
  createBastion: false,
  boxRootFolderIds: [283097226402],
  maxReceiveCount: 2,
}
