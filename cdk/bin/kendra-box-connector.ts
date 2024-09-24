#!/usr/bin/env node
import 'source-map-support/register'
import * as cdk from 'aws-cdk-lib'
import { KendraBoxConnectorStack } from '../lib/kendra-box-connector-stack'
import { devParameters } from './parameters'

const app = new cdk.App()
new KendraBoxConnectorStack(app, 'KendraBoxConnectorStack', {
  parameters: devParameters,
})
