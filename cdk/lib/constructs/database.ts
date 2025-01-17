import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as rds from 'aws-cdk-lib/aws-rds'
import * as ec2 from 'aws-cdk-lib/aws-ec2'
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager'

export interface DatabaseProps {
  vpc: ec2.IVpc
  createBastion?: boolean
  databaseName: string
}

export class Database extends Construct implements ec2.IConnectable {
  public readonly connections: ec2.Connections
  public readonly cluster: rds.DatabaseCluster
  public readonly secret: secretsmanager.ISecret
  private readonly writerId = 'Writer'
  public readonly databaseName: string

  constructor(scope: Construct, id: string, props: DatabaseProps) {
    super(scope, id)

    this.databaseName = props.databaseName

    const cluster = new rds.DatabaseCluster(this, 'Cluster', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_16_4,
      }),
      vpc: props.vpc,
      serverlessV2MinCapacity: 0.0,
      serverlessV2MaxCapacity: 1.0,
      writer: rds.ClusterInstance.serverlessV2(this.writerId, {
        autoMinorVersionUpgrade: true,
        publiclyAccessible: false,
      }),
      defaultDatabaseName: props.databaseName,
      enableDataApi: true,
      storageEncrypted: true,
    })

    if (props.createBastion) {
      const host = new ec2.BastionHostLinux(this, 'BastionHost', {
        vpc: props.vpc,
        machineImage: ec2.MachineImage.latestAmazonLinux2023({
          cpuType: ec2.AmazonLinuxCpuType.ARM_64,
        }),
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.T4G,
          ec2.InstanceSize.NANO,
        ),
        blockDevices: [
          {
            deviceName: '/dev/sdf',
            volume: ec2.BlockDeviceVolume.ebs(8, {
              encrypted: true,
            }),
          },
        ],
      })

      new cdk.CfnOutput(this, 'PortForwardCommand', {
        value: `aws ssm start-session --region ${cdk.Stack.of(this).region} --target ${
          host.instanceId
        } --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters '{"portNumber":["${
          cluster.clusterEndpoint.port
        }"], "localPortNumber":["${cluster.clusterEndpoint.port}"], "host": ["${cluster.clusterEndpoint.hostname}"]}'`,
      })
      new cdk.CfnOutput(this, 'DatabaseSecretsCommand', {
        value: `aws secretsmanager get-secret-value --secret-id ${cluster.secret!.secretName} --region ${cdk.Stack.of(this).region}`,
      })
    }

    this.connections = cluster.connections
    this.cluster = cluster
    this.secret = cluster.secret!
  }
}
