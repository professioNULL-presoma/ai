import boto3

from app.config import get_settings


class StorageError(RuntimeError):
    pass


def download_from_s3(key: str) -> tuple[bytes, str | None]:
    """S3 객체를 메모리로 받는다. (데이터, content_type) 반환."""
    settings = get_settings()
    if not settings.s3_bucket:
        raise StorageError("S3_BUCKET이 설정되지 않았습니다")

    client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )
    try:
        obj = client.get_object(Bucket=settings.s3_bucket, Key=key)
    except client.exceptions.NoSuchKey as e:
        raise StorageError(f"S3에 파일이 없습니다: {key}") from e
    except Exception as e:  # 권한·네트워크 오류
        raise StorageError(f"S3에서 파일을 받지 못했습니다: {key}") from e
    return obj["Body"].read(), obj.get("ContentType")
