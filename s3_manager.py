"""
AWS S3 Manager for Liquidation Blitz application.
Handles uploading/downloading PDFs and CSV catalogs to/from S3.
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from pathlib import Path
from typing import Optional, List
import logging
import requests
from io import BytesIO
import hashlib

from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3Manager:
    """Manages AWS S3 operations for PDF and catalog files."""

    def __init__(self):
        """Initialize S3 client with credentials from config."""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
            logger.info(f"S3 Manager initialized")
            logger.info(f"  - PDFs bucket: {Config.AWS_BUCKET_PDFS}")
            logger.info(f"  - Images bucket: {Config.AWS_BUCKET_IMAGES}")
            logger.info(f"  - Catalog bucket: {Config.AWS_BUCKET_CATALOG}")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise

    def upload_pdf_to_s3(self, pdf_path: str, batch_number: str) -> str:
        """
        Upload PDF report to S3 and return public URL.

        Args:
            pdf_path: Local path to PDF file
            batch_number: Batch/lot number for naming

        Returns:
            Public URL to the uploaded PDF

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ClientError: If S3 upload fails
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # S3 key (path in bucket)
        s3_key = f"{Config.S3_PDF_PREFIX}batch-{batch_number}.pdf"

        try:
            # Upload file (public access controlled by bucket policy)
            self.s3_client.upload_file(
                str(pdf_file),
                Config.AWS_BUCKET_PDFS,
                s3_key,
                ExtraArgs={
                    'ContentType': 'application/pdf'
                }
            )

            # Generate public URL
            public_url = f"https://{Config.AWS_BUCKET_PDFS}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"PDF uploaded successfully: {public_url}")

            return public_url

        except ClientError as e:
            logger.error(f"Failed to upload PDF to S3: {e}")
            raise

    def download_catalog_from_s3(self, local_path: Optional[str] = None) -> str:
        """
        Download existing catalog CSV from S3.

        Args:
            local_path: Optional local path to save file.
                       If None, saves to temp directory.

        Returns:
            Local path to downloaded catalog file

        Raises:
            ClientError: If S3 download fails
        """
        if local_path is None:
            local_path = str(Config.TEMP_DIR / Config.CATALOG_FILENAME)

        # S3 key for catalog
        s3_key = f"{Config.S3_CATALOG_PREFIX}{Config.CATALOG_FILENAME}"

        try:
            self.s3_client.download_file(
                Config.AWS_BUCKET_CATALOG,
                s3_key,
                local_path
            )
            logger.info(f"Catalog downloaded from S3: {local_path}")
            return local_path

        except ClientError as e:
            # If file doesn't exist in S3, return path anyway (will create new)
            if e.response['Error']['Code'] == '404':
                logger.warning(f"Catalog not found in S3, will create new one")
                return local_path
            else:
                logger.error(f"Failed to download catalog from S3: {e}")
                raise

    def upload_catalog_to_s3(self, csv_path: str) -> str:
        """
        Upload updated catalog CSV to S3 and return public URL.

        Args:
            csv_path: Local path to CSV file

        Returns:
            Public URL to the uploaded catalog

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ClientError: If S3 upload fails
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # S3 key for catalog
        s3_key = f"{Config.S3_CATALOG_PREFIX}{Config.CATALOG_FILENAME}"

        try:
            # Upload file (public access controlled by bucket policy)
            self.s3_client.upload_file(
                str(csv_file),
                Config.AWS_BUCKET_CATALOG,
                s3_key,
                ExtraArgs={
                    'ContentType': 'text/csv'
                }
            )

            # Generate public URL
            public_url = f"https://{Config.AWS_BUCKET_CATALOG}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"Catalog uploaded successfully: {public_url}")

            return public_url

        except ClientError as e:
            logger.error(f"Failed to upload catalog to S3: {e}")
            raise

    def upload_image_to_s3(self, image_url: str, batch_number: str, item_index: int) -> Optional[str]:
        """
        Download image from URL and upload to S3.

        Args:
            image_url: Source image URL
            batch_number: Batch/lot number for organizing
            item_index: Index of item in batch for unique naming

        Returns:
            Public URL to uploaded image on S3, or None if failed
        """
        try:
            # Download image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            # Get image content
            image_data = response.content

            # Generate unique filename using hash to avoid duplicates
            image_hash = hashlib.md5(image_data).hexdigest()[:12]

            # Determine file extension
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            ext = '.jpg'
            if 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'webp' in content_type:
                ext = '.webp'

            # S3 key (path in bucket)
            s3_key = f"{Config.S3_IMAGES_PREFIX}batch-{batch_number}/item-{item_index}_{image_hash}{ext}"

            # Upload to S3 (public access controlled by bucket policy)
            self.s3_client.put_object(
                Bucket=Config.AWS_BUCKET_IMAGES,
                Key=s3_key,
                Body=image_data,
                ContentType=content_type
            )

            # Generate public URL
            public_url = f"https://{Config.AWS_BUCKET_IMAGES}.s3.{Config.AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"Image uploaded: {s3_key}")

            return public_url

        except Exception as e:
            logger.warning(f"Failed to upload image from {image_url}: {e}")
            return None

    def upload_images_batch(self, image_urls: List[str], batch_number: str) -> List[str]:
        """
        Upload multiple images to S3 from URLs.

        Args:
            image_urls: List of source image URLs
            batch_number: Batch/lot number for organizing

        Returns:
            List of public S3 URLs (empty string for failed uploads)
        """
        s3_urls = []

        for idx, image_url in enumerate(image_urls):
            if not image_url or not image_url.strip():
                s3_urls.append('')
                continue

            s3_url = self.upload_image_to_s3(image_url, batch_number, idx)
            s3_urls.append(s3_url if s3_url else image_url)  # Fallback to original URL if upload fails

        logger.info(f"Uploaded {len([u for u in s3_urls if u])} images for batch {batch_number}")
        return s3_urls

    def delete_pdf_from_s3(self, batch_number: str) -> bool:
        """
        Delete PDF file from S3.

        Args:
            batch_number: Batch/lot number

        Returns:
            True if deleted successfully, False otherwise
        """
        s3_key = f"{Config.S3_PDF_PREFIX}batch-{batch_number}.pdf"

        try:
            self.s3_client.delete_object(
                Bucket=Config.AWS_BUCKET_PDFS,
                Key=s3_key
            )
            logger.info(f"PDF deleted from S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete PDF from S3: {e}")
            return False

    def delete_images_from_s3(self, batch_number: str) -> bool:
        """
        Delete all images for a batch from S3.

        Args:
            batch_number: Batch/lot number

        Returns:
            True if deleted successfully, False otherwise
        """
        # List all objects in the batch images folder
        prefix = f"{Config.S3_IMAGES_PREFIX}batch-{batch_number}/"

        try:
            # List all objects with this prefix
            response = self.s3_client.list_objects_v2(
                Bucket=Config.AWS_BUCKET_IMAGES,
                Prefix=prefix
            )

            if 'Contents' in response:
                # Delete all objects
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]

                if objects_to_delete:
                    self.s3_client.delete_objects(
                        Bucket=Config.AWS_BUCKET_IMAGES,
                        Delete={'Objects': objects_to_delete}
                    )
                    logger.info(f"Deleted {len(objects_to_delete)} images for batch {batch_number}")
            else:
                logger.info(f"No images found for batch {batch_number}")

            return True
        except ClientError as e:
            logger.error(f"Failed to delete images from S3: {e}")
            return False

    def check_connection(self) -> bool:
        """
        Test S3 connection by listing buckets.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.s3_client.list_buckets()
            logger.info("S3 connection successful")
            return True
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"S3 connection failed: {e}")
            return False
