import json
import os
import time
import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initializes MinIO buckets if they do not exist and sets public view/download policies."

    def handle(self, *args, **options):
        endpoint_url = os.environ.get('AWS_ENDPOINT', getattr(settings, 'AWS_S3_ENDPOINT_URL', 'http://rheuma-minio:7000'))
        access_key = os.environ.get('MINIO_ROOT_USER', getattr(settings, 'AWS_ACCESS_KEY_ID', 'minioadmin'))
        secret_key = os.environ.get('MINIO_ROOT_PASSWORD', getattr(settings, 'AWS_SECRET_ACCESS_KEY', 'minioadmin'))
        region = os.environ.get('AWS_REGION', getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'))
        default_bucket = os.environ.get('AWS_BUCKET_NAME', getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'patient-reports'))

        self.stdout.write(f"Connecting to MinIO at {endpoint_url}...")

        s3_client = None
        for attempt in range(1, 10):
            try:
                s3_client = boto3.client(
                    's3',
                    endpoint_url=endpoint_url,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=region,
                    config=Config(signature_version='s3v4')
                )
                s3_client.list_buckets()
                break
            except Exception as err:
                self.stdout.write(f"Waiting for MinIO (attempt {attempt}/10): {err}")
                time.sleep(2)

        if not s3_client:
            self.stderr.write(self.style.ERROR("Failed to connect to MinIO after multiple retries."))
            return

        # Map of buckets and public view/download policy requirement
        buckets = {
            'clinic-logos': True,
            'doctor-photos': True,
            'doctor-signatures': True,
            'lab-reports': False,
            'prescriptions': False,
            'patient-documents': False,
            default_bucket: False,
        }

        try:
            response = s3_client.list_buckets()
            existing_buckets = [b['Name'] for b in response.get('Buckets', [])]
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error listing MinIO buckets: {e}"))
            return

        for bucket_name, is_public in buckets.items():
            if not bucket_name:
                continue

            if bucket_name not in existing_buckets:
                self.stdout.write(f"Creating bucket '{bucket_name}'...")
                try:
                    s3_client.create_bucket(Bucket=bucket_name)
                    self.stdout.write(self.style.SUCCESS(f"Successfully created bucket '{bucket_name}'."))
                except ClientError as ce:
                    if ce.response.get('Error', {}).get('Code') in ['BucketAlreadyOwnedByYou', 'BucketAlreadyExists']:
                        self.stdout.write(f"Bucket '{bucket_name}' already exists.")
                    else:
                        self.stderr.write(self.style.ERROR(f"Failed to create bucket '{bucket_name}': {ce}"))
            else:
                self.stdout.write(f"Bucket '{bucket_name}' already exists. Skipping creation.")

            # Apply public view/download policy for public buckets
            if is_public:
                public_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PublicRead",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                try:
                    s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(public_policy))
                    self.stdout.write(self.style.SUCCESS(f"Applied public view/download policy to bucket '{bucket_name}'."))
                except Exception as pe:
                    self.stderr.write(self.style.ERROR(f"Failed to set policy for bucket '{bucket_name}': {pe}"))

        self.stdout.write(self.style.SUCCESS("MinIO bucket setup completed successfully!"))
