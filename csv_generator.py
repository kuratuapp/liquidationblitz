"""
CSV Catalog Generator for Liquidation Blitz application.
Creates and updates Google Shopping Feed format catalog.
"""

import csv
import pandas as pd
from pathlib import Path
from typing import List, Optional
from collections import Counter
import logging

from data_structure import LiquidationBatch
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CatalogGenerator:
    """Generates and updates CSV catalog in Google Shopping Feed format."""

    def __init__(self):
        """Initialize catalog generator with column definitions."""
        self.columns = Config.CSV_COLUMNS

    def update_catalog(
        self,
        batch: LiquidationBatch,
        pdf_url: str,
        catalog_path: str,
        markup_percentage: float = 0.0
    ) -> str:
        """
        Update or create catalog CSV with batch information.

        Args:
            batch: LiquidationBatch object with all batch data
            pdf_url: Public URL to PDF report on S3
            catalog_path: Path to catalog CSV file
            markup_percentage: Markup percentage to add to price (default: 0.0)

        Returns:
            Path to updated catalog file
        """
        # Load existing catalog or create new
        catalog_df = self._load_or_create_catalog(catalog_path)

        # Create row data for this batch
        batch_row = self._create_batch_row(batch, pdf_url, markup_percentage)

        # Check if batch ID exists
        batch_id = batch.summary.lot_number
        if batch_id in catalog_df['id'].values:
            # Replace existing row
            logger.info(f"Batch {batch_id} exists - replacing row")
            catalog_df = catalog_df[catalog_df['id'] != batch_id]

        # Add new row
        new_row_df = pd.DataFrame([batch_row])
        catalog_df = pd.concat([catalog_df, new_row_df], ignore_index=True)

        # Save updated catalog
        catalog_df.to_csv(catalog_path, index=False)
        logger.info(f"Catalog updated successfully: {catalog_path}")

        return catalog_path

    def _load_or_create_catalog(self, catalog_path: str) -> pd.DataFrame:
        """
        Load existing catalog or create new DataFrame with headers.

        Args:
            catalog_path: Path to catalog CSV file

        Returns:
            DataFrame with catalog data or empty DataFrame with headers
        """
        catalog_file = Path(catalog_path)

        if catalog_file.exists():
            try:
                df = pd.read_csv(catalog_path)
                logger.info(f"Loaded existing catalog with {len(df)} rows")
                return df
            except Exception as e:
                logger.warning(f"Error loading catalog, creating new: {e}")

        # Create new DataFrame with correct columns
        logger.info("Creating new catalog")
        return pd.DataFrame(columns=self.columns)

    def _create_batch_row(
        self,
        batch: LiquidationBatch,
        pdf_url: str,
        markup_percentage: float = 0.0
    ) -> dict:
        """
        Create a single row dictionary for the batch.

        Args:
            batch: LiquidationBatch object
            pdf_url: Public URL to PDF report
            markup_percentage: Markup percentage to add to price (e.g., 25.0 for 25%)

        Returns:
            Dictionary with row data matching CSV columns
        """
        summary = batch.summary

        # Calculate final price with markup
        base_price = summary.total_client_cost
        markup_amount = base_price * (markup_percentage / 100.0)
        final_price = base_price + markup_amount

        # Extract images (first 10 items)
        image_links = self._extract_images(batch, max_images=10)
        primary_image = image_links[0] if image_links else ''
        additional_images = ','.join(image_links[1:]) if len(image_links) > 1 else ''

        # Get most common brand/vendor
        brand = self._get_most_common_vendor(batch)

        # Map category
        google_category = Config.get_google_category(summary.category)

        # Create title
        title = f"{summary.category.title()} Liquidation Batch - {summary.total_units} Units"

        # Create description
        description = self._create_description(batch)

        # Build row data
        row = {
            'id': summary.lot_number,
            'title': title,
            'description': description,
            'availability': 'in stock',
            'condition': 'New',
            'price': f"{final_price:.2f} USD",
            'link': pdf_url,
            'image_link': primary_image,
            'brand': brand,
            'google_product_category': google_category,
            'item_group_id': '',
            'shipping_weight': '',
            'video[0].url': '',
            'additional_image_link': additional_images
        }

        return row

    def _extract_images(self, batch: LiquidationBatch, max_images: int = 10) -> List[str]:
        """
        Extract image URLs from batch items.

        Args:
            batch: LiquidationBatch object
            max_images: Maximum number of images to extract

        Returns:
            List of image URLs
        """
        images = []

        for item in batch.items[:max_images]:
            if item.image_url and item.image_url.strip():
                images.append(item.image_url)

        logger.info(f"Extracted {len(images)} images from batch")
        return images

    def _get_most_common_vendor(self, batch: LiquidationBatch) -> str:
        """
        Get the most common vendor/brand from batch items.

        Args:
            batch: LiquidationBatch object

        Returns:
            Most common vendor name or 'Mixed Brands'
        """
        vendors = [item.vendor_name for item in batch.items if item.vendor_name]

        if not vendors:
            return 'Mixed Brands'

        # Get most common vendor
        vendor_counts = Counter(vendors)
        most_common = vendor_counts.most_common(1)[0][0]

        # Clean up vendor name (take first part before '/')
        brand = most_common.split('/')[0].strip()

        return brand

    def _create_description(self, batch: LiquidationBatch) -> str:
        """
        Create detailed description for the batch.

        Args:
            batch: LiquidationBatch object

        Returns:
            Formatted description string
        """
        summary = batch.summary

        description_parts = [
            f"Liquidation Batch #{summary.lot_number}",
            f"Category: {summary.category}",
            f"Total Units: {summary.total_units}",
            f"Condition: {summary.return_type}",
        ]

        if summary.season_code:
            description_parts.append(f"Season: {summary.season_code}")

        if summary.num_pallets:
            description_parts.append(f"Pallets: {summary.num_pallets}")

        if summary.num_cartons:
            description_parts.append(f"Cartons: {summary.num_cartons}")

        # Add value information
        description_parts.extend([
            f"Original Retail Value: ${summary.total_original_retail:,.2f}",
            f"Batch Price: ${summary.total_client_cost:,.2f}",
            f"Location: {summary.location}"
        ])

        # Join with " | " separator
        description = " | ".join(description_parts)

        return description

    def delete_batches(self, batch_ids: List[str], catalog_path: str) -> str:
        """
        Delete batches from catalog by their IDs.

        Args:
            batch_ids: List of batch IDs to delete
            catalog_path: Path to catalog CSV file

        Returns:
            Path to updated catalog file

        Raises:
            FileNotFoundError: If catalog file doesn't exist
        """
        catalog_file = Path(catalog_path)

        if not catalog_file.exists():
            raise FileNotFoundError(f"Catalog file not found: {catalog_path}")

        # Load catalog
        df = pd.read_csv(catalog_path)
        original_count = len(df)

        # Filter out batches to delete
        df = df[~df['id'].isin(batch_ids)]
        new_count = len(df)

        deleted_count = original_count - new_count

        # Save updated catalog
        df.to_csv(catalog_path, index=False)
        logger.info(f"Deleted {deleted_count} batch(es) from catalog")

        return catalog_path

    def get_catalog_stats(self, catalog_path: str) -> dict:
        """
        Get statistics about the catalog.

        Args:
            catalog_path: Path to catalog CSV file

        Returns:
            Dictionary with catalog statistics
        """
        catalog_file = Path(catalog_path)

        if not catalog_file.exists():
            return {
                'total_batches': 0,
                'total_value': 0,
                'exists': False
            }

        df = pd.read_csv(catalog_path)

        # Parse prices (remove " USD" and convert to float)
        prices = df['price'].str.replace(' USD', '').astype(float)

        stats = {
            'total_batches': len(df),
            'total_value': prices.sum(),
            'exists': True,
            'batch_ids': df['id'].tolist()
        }

        return stats
