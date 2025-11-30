"""
Liquidation Batch Data Structure

This module defines the data structures for processing liquidation batch files
from Excel spreadsheets into standardized formats for PDF reports and CSV catalogs.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import math


@dataclass
class BatchSummary:
    """Summary information for a liquidation batch"""
    location: str
    lot_number: str
    bol_number: str
    category: str
    subcategory: Optional[str] = None
    season_code: Optional[str] = None
    return_type: str = ""
    num_pallets: int = 0
    num_cartons: int = 0
    total_original_cost: float = 0.0
    total_original_retail: float = 0.0
    total_units: int = 0
    total_client_cost: float = 0.0
    avg_unit_client_cost: Optional[float] = None

    # Additional metadata
    processed_date: datetime = field(default_factory=datetime.now)
    source_file: str = ""

    # Shipping constants
    SHIPPING_RATE_PER_KG: float = 15.50
    SHIPPING_MIN_KG: float = 25.0
    ESTIMATED_LBS_PER_PALLET: float = 750.0
    LBS_TO_KG: float = 0.453592

    @property
    def estimated_weight_lbs(self) -> float:
        """Estimate total weight in pounds based on number of pallets"""
        if self.num_pallets > 0:
            return self.num_pallets * self.ESTIMATED_LBS_PER_PALLET
        # Fallback: estimate based on units (avg 2 lbs per apparel item)
        return self.total_units * 2.0

    @property
    def estimated_weight_kg(self) -> float:
        """Convert estimated weight to kilograms"""
        return self.estimated_weight_lbs * self.LBS_TO_KG

    @property
    def chargeable_weight_kg(self) -> float:
        """Get chargeable weight (minimum 25 kg)"""
        return max(self.estimated_weight_kg, self.SHIPPING_MIN_KG)

    @property
    def estimated_shipping_cost(self) -> float:
        """Calculate estimated shipping cost to Kenya"""
        return self.chargeable_weight_kg * self.SHIPPING_RATE_PER_KG


@dataclass
class Item:
    """Individual item in a liquidation batch"""
    upc: str
    description: str
    original_qty: int
    original_cost: float
    total_original_cost: float
    original_retail: float
    total_original_retail: float
    vendor_style: str = ""
    color: str = ""
    size: str = ""
    client_cost: float = 0.0
    total_client_cost: float = 0.0
    division: str = ""
    department_name: str = ""
    vendor_name: str = ""
    image_url: str = ""

    @property
    def profit_margin(self) -> float:
        """Calculate profit margin percentage"""
        if self.client_cost > 0:
            return ((self.original_retail - self.client_cost) / self.original_retail) * 100
        return 0.0

    @property
    def cost_ratio(self) -> float:
        """Calculate cost ratio (client cost / original retail)"""
        if self.original_retail > 0:
            return self.client_cost / self.original_retail
        return 0.0


@dataclass
class LiquidationBatch:
    """Complete liquidation batch containing summary and items"""
    summary: BatchSummary
    items: List[Item] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        """Total number of items in batch"""
        return len(self.items)

    @property
    def total_value(self) -> float:
        """Total client cost of all items"""
        return sum(item.total_client_cost for item in self.items)

    @property
    def avg_item_cost(self) -> float:
        """Average cost per item"""
        if self.items:
            return self.total_value / len(self.items)
        return 0.0

    @property
    def top_vendors(self) -> Dict[str, int]:
        """Count items by vendor"""
        vendors = {}
        for item in self.items:
            vendor = item.vendor_name or "Unknown"
            vendors[vendor] = vendors.get(vendor, 0) + 1
        return dict(sorted(vendors.items(), key=lambda x: x[1], reverse=True))

    @property
    def size_distribution(self) -> Dict[str, int]:
        """Count items by size"""
        sizes = {}
        for item in self.items:
            size = item.size or "Unknown"
            sizes[size] = sizes.get(size, 0) + 1
        return dict(sorted(sizes.items(), key=lambda x: x[1], reverse=True))

    def apply_markup(self, markup_percentage: float) -> None:
        """
        Apply markup percentage to all item prices (rounded up to integers).
        Updates both individual item costs and batch total.

        Args:
            markup_percentage: Markup percentage (e.g., 25.0 for 25%)
        """
        for item in self.items:
            # Apply markup and round UP to nearest integer
            new_client_cost = math.ceil(item.client_cost * (1 + markup_percentage / 100.0))
            item.client_cost = float(new_client_cost)

            # Update total client cost for this item
            item.total_client_cost = item.client_cost * item.original_qty

        # Update batch summary total to match sum of items
        self.summary.total_client_cost = sum(item.total_client_cost for item in self.items)


class BatchProcessor:
    """Process liquidation batch Excel files into structured data"""

    @staticmethod
    def parse_excel_file(file_path: str) -> LiquidationBatch:
        """
        Parse an Excel file into a LiquidationBatch object

        Args:
            file_path: Path to the Excel file

        Returns:
            LiquidationBatch object with parsed data
        """
        df_raw = pd.read_excel(file_path, header=None)

        # Parse batch summary (row 1 = headers, row 2 = data)
        batch_data = BatchProcessor._parse_batch_summary(df_raw)

        # Parse items (starting from row 8 = headers, row 9+ = data)
        items = BatchProcessor._parse_items(df_raw)

        # Create batch summary object
        summary = BatchSummary(
            location=batch_data.get('LOCATION', ''),
            lot_number=str(batch_data.get('LOT #', '')),
            bol_number=str(batch_data.get('BOL #', '')),
            category=batch_data.get('CATEGORY', ''),
            subcategory=batch_data.get('SUBCATEGORY'),
            season_code=batch_data.get('SEASON CODE'),
            return_type=batch_data.get('RETURN TYPE', ''),
            num_pallets=int(batch_data.get('# OF PALLETS', 0)),
            num_cartons=int(batch_data.get('# OF CARTONS', 0)),
            total_original_cost=float(batch_data.get('TOTAL ORIGINAL COST', 0)),
            total_original_retail=float(batch_data.get('TOTAL ORIGINAL RETAIL', 0)),
            total_units=int(batch_data.get('# OF UNITS', 0)),
            total_client_cost=float(batch_data.get('TOTAL CLIENT COST', 0)),
            avg_unit_client_cost=batch_data.get('AVG. UNIT CLIENT COST'),
            source_file=file_path
        )

        return LiquidationBatch(summary=summary, items=items)

    @staticmethod
    def _parse_batch_summary(df_raw: pd.DataFrame) -> Dict[str, Any]:
        """Parse the batch summary section"""
        batch_data = {}

        # Row 1 contains headers, row 2 contains data
        for j in range(len(df_raw.columns)):
            header = df_raw.iloc[1, j]
            value = df_raw.iloc[2, j]

            if pd.notna(header) and pd.notna(value):
                batch_data[str(header)] = value

        return batch_data

    @staticmethod
    def _parse_items(df_raw: pd.DataFrame) -> List[Item]:
        """Parse the items section starting from row 8"""
        items = []

        # Row 8 contains item headers
        item_headers = []
        for j in range(len(df_raw.columns)):
            val = df_raw.iloc[8, j]
            if pd.notna(val):
                item_headers.append(str(val))
            else:
                item_headers.append(f'column_{j}')

        # Parse items starting from row 9
        for i in range(9, len(df_raw)):
            row_data = {}
            has_data = False

            for j, header in enumerate(item_headers):
                val = df_raw.iloc[i, j]
                if pd.notna(val):
                    row_data[header] = val
                    has_data = True

            # Only process rows with UPC (actual items)
            if has_data and 'UPC' in row_data and row_data['UPC']:
                try:
                    item = Item(
                        upc=str(row_data.get('UPC', '')),
                        description=str(row_data.get('ITEM DESCRIPTION', '')),
                        original_qty=int(row_data.get('ORIGINAL QTY', 0)),
                        original_cost=float(row_data.get('ORIGINAL COST', 0)),
                        total_original_cost=float(row_data.get('TOTAL ORIGINAL COST', 0)),
                        original_retail=float(row_data.get('ORIGINAL RETAIL', 0)),
                        total_original_retail=float(row_data.get('TOTAL ORIGINAL RETAIL', 0)),
                        vendor_style=str(row_data.get('VENDOR / STYLE #', '')),
                        color=str(row_data.get('COLOR', '')),
                        size=str(row_data.get('SIZE', '')),
                        client_cost=float(row_data.get('CLIENT COST', 0)),
                        total_client_cost=float(row_data.get('TOTAL CLIENT COST', 0)),
                        division=str(row_data.get('DIVISION', '')),
                        department_name=str(row_data.get('DEPARTMENT NAME', '')),
                        vendor_name=str(row_data.get('VENDOR NAME', '')),
                        image_url=str(row_data.get('IMAGE', ''))
                    )
                    items.append(item)
                except (ValueError, TypeError) as e:
                    # Skip rows with invalid data
                    print(f"Warning: Skipping row {i} due to data error: {e}")
                    continue

        return items


# Example usage and testing
if __name__ == "__main__":
    # Test the data structure with the sample file
    processor = BatchProcessor()
    batch = processor.parse_excel_file("/Users/fevrose/Downloads/Liquidation Blits/16601678.xlsx")

    print("=== BATCH SUMMARY ===")
    print(f"Location: {batch.summary.location}")
    print(f"Lot #: {batch.summary.lot_number}")
    print(f"Category: {batch.summary.category}")
    print(f"Total Units: {batch.summary.total_units}")
    print(f"Total Client Cost: ${batch.summary.total_client_cost:,.2f}")

    print(f"\n=== ITEMS ANALYSIS ===")
    print(f"Total Items Parsed: {batch.total_items}")
    print(f"Average Item Cost: ${batch.avg_item_cost:.2f}")

    print("\nTop Vendors:")
    for vendor, count in list(batch.top_vendors.items())[:5]:
        print(f"  {vendor}: {count} items")

    print("\nSize Distribution:")
    for size, count in list(batch.size_distribution.items())[:5]:
        print(f"  {size}: {count} items")

    print("\nSample Items:")
    for i, item in enumerate(batch.items[:3]):
        print(f"  {i+1}. {item.description[:50]}... - ${item.client_cost:.2f}")