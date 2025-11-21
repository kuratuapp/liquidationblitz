"""
Main orchestration script for Liquidation Blitz application.
Handles the complete workflow from Excel upload to S3 catalog generation.
"""

import sys
import logging
from pathlib import Path
from typing import Tuple

from data_structure import BatchProcessor
from pdf_generator import PDFGenerator
from s3_manager import S3Manager
from csv_generator import CatalogGenerator
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiquidationBlitzApp:
    """Main application orchestrator."""

    def __init__(self):
        """Initialize application components."""
        self.batch_processor = BatchProcessor()
        self.pdf_generator = PDFGenerator()
        self.s3_manager = S3Manager()
        self.catalog_generator = CatalogGenerator()

    def process_batch(self, excel_path: str) -> Tuple[str, str]:
        """
        Process a liquidation batch through the complete workflow.

        Workflow:
        1. Parse Excel file
        2. Generate PDF report
        3. Upload PDF to S3
        4. Download existing catalog from S3
        5. Update catalog with new batch
        6. Upload catalog to S3
        7. Return both URLs

        Args:
            excel_path: Path to Excel file

        Returns:
            Tuple of (pdf_url, catalog_url)

        Raises:
            FileNotFoundError: If Excel file doesn't exist
            ValueError: If configuration is invalid
            Exception: For any processing errors
        """
        logger.info("=" * 80)
        logger.info("LIQUIDATION BLITZ - BATCH PROCESSING")
        logger.info("=" * 80)

        # Validate configuration
        try:
            Config.validate()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise

        # Check if Excel file exists
        excel_file = Path(excel_path)
        if not excel_file.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        logger.info(f"Processing Excel file: {excel_file.name}")

        # Step 1: Parse Excel file
        logger.info("\n[1/8] Parsing Excel file...")
        batch = self.batch_processor.parse_excel_file(str(excel_file))
        logger.info(f"✓ Parsed batch #{batch.summary.lot_number}")
        logger.info(f"  - Category: {batch.summary.category}")
        logger.info(f"  - Units: {batch.summary.total_units}")
        logger.info(f"  - Value: ${batch.summary.total_client_cost:,.2f}")

        # Step 2: Upload images to S3
        logger.info("\n[2/8] Uploading images to S3...")
        image_urls = [item.image_url for item in batch.items if item.image_url]
        logger.info(f"  - Found {len(image_urls)} images to upload")
        s3_image_urls = self.s3_manager.upload_images_batch(image_urls, batch.summary.lot_number)

        # Update batch items with S3 image URLs
        for idx, item in enumerate(batch.items):
            if idx < len(s3_image_urls) and s3_image_urls[idx]:
                item.image_url = s3_image_urls[idx]
        logger.info(f"✓ Images uploaded to S3")

        # Step 3: Generate PDF report
        logger.info("\n[3/8] Generating PDF report...")
        pdf_path = str(Config.OUTPUT_DIR / f"batch_{batch.summary.lot_number}.pdf")
        self.pdf_generator.generate_report(batch, pdf_path)
        logger.info(f"✓ PDF generated: {pdf_path}")

        # Step 4: Upload PDF to S3
        logger.info("\n[4/8] Uploading PDF to S3...")
        pdf_url = self.s3_manager.upload_pdf_to_s3(pdf_path, batch.summary.lot_number)
        logger.info(f"✓ PDF uploaded: {pdf_url}")

        # Step 5: Download existing catalog from S3
        logger.info("\n[5/8] Downloading catalog from S3...")
        catalog_path = str(Config.TEMP_DIR / Config.CATALOG_FILENAME)
        self.s3_manager.download_catalog_from_s3(catalog_path)
        logger.info(f"✓ Catalog ready: {catalog_path}")

        # Step 6: Update catalog with new batch
        logger.info("\n[6/8] Updating catalog...")
        updated_catalog_path = self.catalog_generator.update_catalog(
            batch, pdf_url, catalog_path
        )
        logger.info(f"✓ Catalog updated")

        # Get catalog stats
        stats = self.catalog_generator.get_catalog_stats(updated_catalog_path)
        logger.info(f"  - Total batches in catalog: {stats['total_batches']}")
        logger.info(f"  - Total catalog value: ${stats['total_value']:,.2f}")

        # Step 7: Upload catalog to S3
        logger.info("\n[7/8] Uploading catalog to S3...")
        catalog_url = self.s3_manager.upload_catalog_to_s3(updated_catalog_path)
        logger.info(f"✓ Catalog uploaded: {catalog_url}")

        # Step 8: Complete
        logger.info("\n[8/8] Processing complete!")
        logger.info("=" * 80)
        logger.info("RESULTS:")
        logger.info(f"  PDF URL:     {pdf_url}")
        logger.info(f"  Catalog URL: {catalog_url}")
        logger.info("=" * 80)

        return pdf_url, catalog_url

    def test_s3_connection(self) -> bool:
        """
        Test S3 connection.

        Returns:
            True if connection successful
        """
        logger.info("Testing S3 connection...")
        return self.s3_manager.check_connection()


def main():
    """Main entry point for command-line usage."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <excel_file_path>")
        print("\nExample:")
        print("  python main.py 16601678.xlsx")
        sys.exit(1)

    excel_path = sys.argv[1]

    try:
        # Initialize app
        app = LiquidationBlitzApp()

        # Test S3 connection first
        if not app.test_s3_connection():
            logger.error("S3 connection failed. Please check your configuration.")
            sys.exit(1)

        # Process batch
        pdf_url, catalog_url = app.process_batch(excel_path)

        # Print results
        print("\n" + "=" * 80)
        print("SUCCESS!")
        print("=" * 80)
        print(f"\nPDF URL:\n{pdf_url}")
        print(f"\nCatalog URL:\n{catalog_url}")
        print("\n" + "=" * 80)

    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
