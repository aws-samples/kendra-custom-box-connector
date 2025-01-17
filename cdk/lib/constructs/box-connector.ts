import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as ec2 from 'aws-cdk-lib/aws-ec2'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as sqs from 'aws-cdk-lib/aws-sqs'
import * as logs from 'aws-cdk-lib/aws-logs'
import * as apigateway from 'aws-cdk-lib/aws-apigateway'
import * as ecs from 'aws-cdk-lib/aws-ecs'
import * as python from '@aws-cdk/aws-lambda-python-alpha'
import { Database } from './database'
import * as events from 'aws-cdk-lib/aws-events'
import * as targets from 'aws-cdk-lib/aws-events-targets'

export interface BoxConnectorProps {
  vpc: ec2.IVpc
  bucket: s3.Bucket
  database: Database
  maxReceiveCount: number
  eventHandlerSchedule: events.Schedule
  boxRootFolderIds: number[]
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
      fifo: true,
      retentionPeriod: cdk.Duration.days(14),
      enforceSSL: true,
    })
    this.deadLetterQueue = deadLetterQueue

    const queue = new sqs.Queue(this, 'Queue', {
      fifo: true,
      contentBasedDeduplication: true,
      visibilityTimeout: cdk.Duration.seconds(30),
      enforceSSL: true,
      deadLetterQueue: {
        maxReceiveCount: props.maxReceiveCount,
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
          'application/json':
            'Action=SendMessage&MessageGroupId=Box&MessageBody=$input.body',
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

    const { accountId, region } = new cdk.ScopedAws(this)

    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc: props.vpc,
    })

    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      'TaskDefinition',
      {
        cpu: 1024,
        memoryLimitMiB: 2048,
        runtimePlatform: { cpuArchitecture: ecs.CpuArchitecture.X86_64 },
      },
    )

    taskDefinition.addContainer('BoxConnector', {
      containerName: 'box-connector',
      image: ecs.ContainerImage.fromAsset('../box_connector'),
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: 'log',
      }),
      secrets: {
        DB_USER: ecs.Secret.fromSecretsManager(
          props.database.secret,
          'username',
        ),
        DB_PASSWORD: ecs.Secret.fromSecretsManager(
          props.database.secret,
          'password',
        ),
      },
      environment: {
        DB_HOST: props.database.cluster.clusterEndpoint.hostname,
        DB_PORT: props.database.cluster.clusterEndpoint.port.toString(),
        DB_NAME: props.database.databaseName,
        BUCKET_NAME: props.bucket.bucketName,
        SQS_QUEUE_NAME: queue.queueName,
        BOX_ROOT_FOLDER_IDS: props.boxRootFolderIds.join(','),
      },
    })

    const securityGroup = new ec2.SecurityGroup(this, 'SecurityGroup', {
      vpc: props.vpc,
      description: 'BoxConnector security group',
      allowAllOutbound: true,
    })

    props.database.connections.allowFrom(
      securityGroup,
      ec2.Port.tcp(props.database.cluster.clusterEndpoint.port),
      'Allow from fargate cluster',
    )
    props.bucket.grantReadWrite(taskDefinition.taskRole)
    queue.grantConsumeMessages(taskDefinition.taskRole)

    // AWS Systems ManagerからBoxのConfigを取得できるポリシー
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

    taskDefinition.taskRole.addManagedPolicy(allowGetBoxConfigPolicy)

    new events.Rule(this, 'Rule', {
      schedule: props.eventHandlerSchedule,
      targets: [
        new targets.EcsTask({
          cluster,
          taskDefinition,
          subnetSelection: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
          securityGroups: [securityGroup],
        }),
      ],
    })

    new cdk.CfnOutput(this, 'CrawlerCommand', {
      value: `aws ecs run-task \\
    --cluster ${cluster.clusterName} \\
    --launch-type FARGATE \\
    --network-configuration "awsvpcConfiguration={subnets=[${props.vpc.privateSubnets[0].subnetId}],securityGroups=[${securityGroup.securityGroupId}]}" \\
    --task-definition ${taskDefinition.family} \\
    --overrides '{"containerOverrides":[{"name":"box-connector","command":["box_crawler.py"],"environment":[{"name":"SKIP_EXISTING_ITEMS","value":"True"}]}]}'`,
      description: 'ECS Run Task command for crawling Box',
    })
  }
}
