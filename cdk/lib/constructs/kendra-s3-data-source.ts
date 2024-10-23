import { Construct } from 'constructs'
import * as s3 from 'aws-cdk-lib/aws-s3'
import * as iam from 'aws-cdk-lib/aws-iam'
import * as kendra from 'aws-cdk-lib/aws-kendra'

export interface KendraS3DataSourceProps {
  name: string
  index: kendra.CfnIndex
  bucket: s3.Bucket
}

export class KendraS3DataSource extends Construct {
  public readonly dataSource: kendra.CfnDataSource

  constructor(scope: Construct, id: string, props: KendraS3DataSourceProps) {
    super(scope, id)

    const dataSourceRole = new iam.Role(this, 'DatasourceRole', {
      assumedBy: new iam.ServicePrincipal('kendra.amazonaws.com'),
    })

    dataSourceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['kendra:BatchPutDocument', 'kendra:BatchDeleteDocument'],
        resources: [props.index.attrArn],
      }),
    )

    props.bucket.grantRead(dataSourceRole)

    this.dataSource = new kendra.CfnDataSource(this, 'Default', {
      indexId: props.index.attrId,
      name: props.name,
      type: 'S3',
      languageCode: 'ja',
      roleArn: dataSourceRole.roleArn,
      dataSourceConfiguration: {
        s3Configuration: {
          bucketName: props.bucket.bucketName,
          inclusionPrefixes: ['docs/'],
          accessControlListConfiguration: {
            keyPath: props.bucket.s3UrlForObject() + '/acl.json',
          },
        },
      },
      schedule: 'cron(0 15 * * ? *)', // 毎日0:00(JST)
    })

    this.dataSource.addDependency(props.index);
  }
}
