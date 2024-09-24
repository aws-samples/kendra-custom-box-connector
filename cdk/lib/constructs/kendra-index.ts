import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as kendra from 'aws-cdk-lib/aws-kendra'

export interface KendraIndexProps {
  name: string
  edition?: string
}

export class KendraIndex extends Construct {
  index: kendra.CfnIndex
  constructor(scope: Construct, id: string, props: KendraIndexProps) {
    super(scope, id)

    const indexRole = new iam.Role(this, 'KendraIndexRole', {
      assumedBy: new iam.ServicePrincipal('kendra.amazonaws.com'),
    })

    indexRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
        conditions: {
          StringEquals: {
            'cloudwatch:namespace': 'AWS/Kendra',
          },
        },
      }),
    )

    const { accountId, region } = new cdk.ScopedAws(this)

    indexRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['logs:DescribeLogGroups', 'logs:CreateLogGroup'],
        resources: [
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/kendra/*`,
        ],
      }),
    )

    indexRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:DescribeLogStreams',
          'logs:CreateLogStream',
          'logs:PutLogEvents',
        ],
        resources: [
          `arn:aws:logs:${region}:${accountId}:log-group:/aws/kendra/*:log-stream:*`,
        ],
      }),
    )

    this.index = new kendra.CfnIndex(this, 'Default', {
      name: props.name,
      edition: props.edition || 'DEVELOPER_EDITION',
      roleArn: indexRole.roleArn,
    })
  }
}
