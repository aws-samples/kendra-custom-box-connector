import * as cdk from 'aws-cdk-lib'
import { Construct } from 'constructs'
import * as s3 from 'aws-cdk-lib/aws-s3'
import { BoxConnector } from './constructs/box-connector'
import { KendraIndex } from './constructs/kendra-index'
import { KendraS3DataSource } from './constructs/kendra-s3-data-source'
import { AppParameters } from '../bin/parameters'

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

    const kendraIndex = new KendraIndex(this, 'KendraIndex', {
      name: props.parameters.kendraIndexName,
    })

    const bucket = new s3.Bucket(this, 'Bucket', {
      enforceSSL: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    })

    new BoxConnector(this, 'BoxConnector', {
      bucket,
    })

    new KendraS3DataSource(this, 'KendraS3DataSource', {
      name: props.parameters.kendraDataSourceName,
      index: kendraIndex.index,
      bucket: bucket,
    })
  }
}
