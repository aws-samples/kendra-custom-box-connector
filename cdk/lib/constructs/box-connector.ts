import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as sqs from 'aws-cdk-lib/aws-sqs'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as apigateway from 'aws-cdk-lib/aws-apigateway'
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb'
import * as lambda from 'aws-cdk-lib/aws-lambda'
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources'
import * as python from '@aws-cdk/aws-lambda-python-alpha'

export interface BoxConnectorProps {
  bucket: s3.Bucket
}

export class BoxConnector extends Construct {
  function: python.PythonFunction
  queue: sqs.Queue
  deadLetterQueue: sqs.Queue

  constructor(scope: Construct, id: string, props: BoxConnectorProps) {
    super(scope, id)

    const integrationRole = new iam.Role(this, 'IntegrationRole', {
      assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
    })

    const deadLetterQueue = new sqs.Queue(this, 'DeadLetterQueue', {
      retentionPeriod: cdk.Duration.days(14),
      enforceSSL: true,
    })
    this.deadLetterQueue = deadLetterQueue

    const queue = new sqs.Queue(this, 'Queue', {
      visibilityTimeout: cdk.Duration.minutes(3),
      enforceSSL: true,
      deadLetterQueue: {
        maxReceiveCount: 2,
        queue: deadLetterQueue,
      },
    })
    this.queue = queue

    queue.grantSendMessages(integrationRole)

    const sendMessageIntegration = new apigateway.AwsIntegration({
      service: 'sqs',
      path: `${process.env.CDK_DEFAULT_ACCOUNT}/${queue.queueName}`,
      integrationHttpMethod: 'POST',
      options: {
        credentialsRole: integrationRole,
        requestParameters: {
          'integration.request.header.Content-Type': `'application/x-www-form-urlencoded'`,
        },
        requestTemplates: {
          'application/json': 'Action=SendMessage&MessageBody=$input.body',
        },
        integrationResponses: [
          {
            statusCode: '200',
          },
          {
            statusCode: '400',
          },
          {
            statusCode: '500',
          },
        ],
      },
    })

    const api = new apigateway.RestApi(this, 'RestApi', {
      restApiName: 'BoxConnector',
      cloudWatchRole: true,
      deployOptions: {
        // 実行ログの設定
        dataTraceEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        // アクセスログの設定
        accessLogDestination: new apigateway.LogGroupLogDestination(
          new logs.LogGroup(this, 'RestApiLogAccessLogGroup', {
            retention: 14,
          }),
        ),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields(),
      },
    })

    api.root.addMethod('POST', sendMessageIntegration, {
      methodResponses: [
        {
          statusCode: '400',
        },
        {
          statusCode: '200',
        },
        {
          statusCode: '500',
        },
      ],
    })

    const itemTable = new dynamodb.TableV2(this, 'ItemTable', {
      partitionKey: { name: 'item_id', type: dynamodb.AttributeType.STRING },
      globalSecondaryIndexes: [
        {
          indexName: 'key-index',
          partitionKey: {
            name: 'source_type',
            type: dynamodb.AttributeType.STRING,
          },
          sortKey: {
            name: 's3_key',
            type: dynamodb.AttributeType.STRING,
          },
          projectionType: dynamodb.ProjectionType.ALL,
        },
      ],
    })

    const collaborationTable = new dynamodb.TableV2(
      this,
      'CollaborationTable',
      {
        partitionKey: { name: 'item_id', type: dynamodb.AttributeType.STRING },
        sortKey: {
          name: 'collaboration_id',
          type: dynamodb.AttributeType.STRING,
        },
      },
    )

    const fn = new python.PythonFunction(this, 'Function', {
      entry: '../functions/box_connector',
      runtime: lambda.Runtime.PYTHON_3_12,
      memorySize: 1024,
      ephemeralStorageSize: cdk.Size.mebibytes(512),
      timeout: cdk.Duration.minutes(3),
      environment: {
        BUCKET_NAME: props.bucket.bucketName,
        ITEM_TABLE: itemTable.tableName,
        COLLABORATION_TABLE: collaborationTable.tableName,
      },
    })
    this.function = fn
    props.bucket.grantReadWrite(fn)
    itemTable.grantReadWriteData(fn)
    collaborationTable.grantReadWriteData(fn)

    const { accountId, region } = new cdk.ScopedAws(this)

    // AWS Systems Manager から Box の Config を取得できるポリシー
    const allowGetBoxConfigPolicy = new iam.ManagedPolicy(
      this,
      'AllowGetBoxConfigPolicy',
      {
        statements: [
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: ['ssm:GetParameter'],
            resources: [
              `arn:aws:ssm:${region}:${accountId}:parameter/kendra-box-connector/box-config`,
            ],
          }),
        ],
      },
    )
    fn.role?.addManagedPolicy(allowGetBoxConfigPolicy)

    fn.addEventSource(
      new lambdaEventSources.SqsEventSource(queue, { batchSize: 1 }),
    )
  }
}
