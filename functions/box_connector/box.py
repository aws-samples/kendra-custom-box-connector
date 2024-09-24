import box_sdk_gen
import boto3
from aws_lambda_powertools import Logger

ssm_client = boto3.client("ssm")
logger = Logger()


def initialize_box_client() -> box_sdk_gen.BoxClient:
    try:
        # AWS Systems Manager から Box の認証情報を取得
        response = ssm_client.get_parameter(
            Name="/kendra-box-connector/box-config", WithDecryption=True
        )
        parameter_value = response["Parameter"]["Value"]
        box_config = box_sdk_gen.JWTConfig.from_config_json_string(parameter_value)
        box_auth = box_sdk_gen.BoxJWTAuth(config=box_config)
        return box_sdk_gen.BoxClient(auth=box_auth)
    except Exception as e:
        logger.error(
            {
                "text": "Failed to initialize box_client",
                "error": str(e),
            }
        )


box_client = initialize_box_client()
