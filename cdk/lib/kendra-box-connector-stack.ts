import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as s3 from 'aws-cdk-lib/aws-s3'
import { BoxConnector } from './constructs/box-connector'
import { KendraIndex } from './constructs/kendra-index'
import { KendraS3DataSource } from './constructs/kendra-s3-data-source'
import { AppParameters } from '../bin/parameters'
import * as ec2 from 'aws-cdk-lib/aws-ec2'
import { Database } from './constructs/database'

interface KendraBoxConnectorStackProps extends cdk.StackProps {
  parameters: AppParameters
}

export class KendraBoxConnectorStack extends cdk.Stack {
  constructor(
    scope: Construct,
    id: string,
    props: KendraBoxConnectorStackProps,
  ) {
    super(scope, id, props)

    let vpc: ec2.IVpc
    if (props.parameters.vpcId != null) {
      vpc = ec2.Vpc.fromLookup(this, 'Vpc', { vpcId: props.parameters.vpcId })
    } else {
      vpc = new ec2.Vpc(this, 'Vpc', {
        ...(props.parameters.cheapVpc
          ? {
              natGatewayProvider: ec2.NatProvider.instanceV2({
                instanceType: ec2.InstanceType.of(
                  ec2.InstanceClass.T4G,
                  ec2.InstanceSize.NANO,
                ),
              }),
              natGateways: 1,
            }
          : {}),
        maxAzs: 2,
        subnetConfiguration: [
          {
            subnetType: ec2.SubnetType.PUBLIC,
            name: 'Public',
            mapPublicIpOnLaunch: false,
          },
          {
            subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
            name: 'Private',
          },
        ],
      })
    }

    const kendraIndex = new KendraIndex(this, 'KendraIndex', {
      name: props.parameters.kendraIndexName,
      edition: props.parameters.kendraEdition,
    })

    const bucket = new s3.Bucket(this, 'Bucket', {
      enforceSSL: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    })

    const database = new Database(this, 'Database', {
      vpc,
      databaseName: props.parameters.databaseName,
      createBastion: props.parameters.createBastion,
    })

    new BoxConnector(this, 'BoxConnector', {
      vpc,
      bucket,
      database,
      eventHandlerSchedule: props.parameters.eventHandlerSchedule,
      boxRootFolderIds: props.parameters.boxRootFolderIds,
      maxReceiveCount: props.parameters.maxReceiveCount,
    })

    new KendraS3DataSource(this, 'KendraS3DataSource', {
      name: props.parameters.kendraDataSourceName,
      index: kendraIndex.index,
      bucket: bucket,
      dataSourceSyncSchedule: props.parameters.dataSourceSyncSchedule,
    })
  }
}
