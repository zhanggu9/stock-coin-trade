import json
import os


def secret_values(keys: tuple[str, ...], arn_env: str) -> dict[str, str]:
    direct = {key: os.environ.get(key) for key in keys}
    if all(direct.values()):
        return direct

    secret_arn = os.environ.get(arn_env)
    if not secret_arn:
        raise RuntimeError(f"{arn_env} 또는 로컬 환경변수 {', '.join(keys)}가 필요합니다.")

    import boto3
    payload = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    values = json.loads(payload["SecretString"])
    missing = [key for key in keys if not values.get(key)]
    if missing:
        raise RuntimeError(f"Secret JSON 키 누락: {', '.join(missing)}")
    return {key: values[key] for key in keys}
