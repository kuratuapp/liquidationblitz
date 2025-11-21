"""
Configuration management for Liquidation Blitz application.
Handles AWS S3 settings and application constants.
Supports both .env files and Streamlit secrets.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Try to import Streamlit secrets (only available in Streamlit environment)
try:
    import streamlit as st
    USE_STREAMLIT_SECRETS = True
except ImportError:
    USE_STREAMLIT_SECRETS = False


def _get_config_value(key: str, default: str = '') -> str:
    """
    Get configuration value from Streamlit secrets or environment variables.
    Priority: Streamlit secrets > Environment variables > Default
    """
    # Try Streamlit secrets first (if available)
    if USE_STREAMLIT_SECRETS:
        try:
            if hasattr(st, 'secrets') and key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass

    # Fall back to environment variables
    return os.getenv(key, default)


class Config:
    """Application configuration settings."""

    # AWS S3 Configuration
    AWS_REGION = _get_config_value('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID = _get_config_value('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = _get_config_value('AWS_SECRET_ACCESS_KEY', '')

    # S3 Buckets (can be same or different buckets)
    AWS_BUCKET_PDFS = _get_config_value('AWS_BUCKET_PDFS', _get_config_value('AWS_BUCKET_NAME', ''))
    AWS_BUCKET_IMAGES = _get_config_value('AWS_BUCKET_IMAGES', _get_config_value('AWS_BUCKET_NAME', ''))
    AWS_BUCKET_CATALOG = _get_config_value('AWS_BUCKET_CATALOG', _get_config_value('AWS_BUCKET_NAME', ''))

    # S3 Paths (prefixes within buckets)
    S3_PDF_PREFIX = 'pdfs/'
    S3_CATALOG_PREFIX = ''  # Catalog at root of bucket
    S3_IMAGES_PREFIX = 'images/'

    # Catalog Settings
    CATALOG_FILENAME = 'liquidationblitzcatalog.csv'

    # Local Paths
    BASE_DIR = Path(__file__).resolve().parent
    OUTPUT_DIR = BASE_DIR / 'output'
    TEMP_DIR = BASE_DIR / 'temp'

    # CSV Columns (Google Shopping Feed Format)
    CSV_COLUMNS = [
        'id',
        'title',
        'description',
        'availability',
        'condition',
        'price',
        'link',
        'image_link',
        'brand',
        'google_product_category',
        'item_group_id',
        'shipping_weight',
        'video[0].url',
        'additional_image_link'
    ]

    # Category Mapping (Excel category → Google Product Category)
    CATEGORY_MAPPING = {
        'MENS SUITS & COATS': 'Apparel & Accessories > Clothing > Suits',
        'WOMENS DRESSES': 'Apparel & Accessories > Clothing > Dresses',
        'MENS SHIRTS': 'Apparel & Accessories > Clothing > Shirts & Tops',
        'WOMENS SHOES': 'Apparel & Accessories > Shoes',
        'MENS SHOES': 'Apparel & Accessories > Shoes',
        'JEWELRY': 'Apparel & Accessories > Jewelry',
        'HANDBAGS': 'Apparel & Accessories > Handbags, Wallets & Cases',
        'DEFAULT': 'Apparel & Accessories'
    }

    @classmethod
    def validate(cls):
        """Validate required configuration settings."""
        missing = []

        if not cls.AWS_BUCKET_PDFS:
            missing.append('AWS_BUCKET_PDFS')
        if not cls.AWS_BUCKET_IMAGES:
            missing.append('AWS_BUCKET_IMAGES')
        if not cls.AWS_BUCKET_CATALOG:
            missing.append('AWS_BUCKET_CATALOG')
        if not cls.AWS_ACCESS_KEY_ID:
            missing.append('AWS_ACCESS_KEY_ID')
        if not cls.AWS_SECRET_ACCESS_KEY:
            missing.append('AWS_SECRET_ACCESS_KEY')

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"Please set these in your .env file or environment variables."
            )

    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        cls.TEMP_DIR.mkdir(exist_ok=True)

    @classmethod
    def get_google_category(cls, excel_category: str) -> str:
        """Map Excel category to Google Product Category."""
        return cls.CATEGORY_MAPPING.get(
            excel_category.upper(),
            cls.CATEGORY_MAPPING['DEFAULT']
        )


# Create directories on import
Config.ensure_directories()
