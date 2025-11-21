"""
PDF Generator for Liquidation Batch Reports

Creates custom PDF reports with:
- Cover page: "Liquidation Blitz" title with lot number
- Summary page: Details and financial analysis
- Item catalog: Images on left, details on right (3-4 items per page)
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
from typing import List, Dict, Any
import os
import requests
from io import BytesIO
from PIL import Image as PILImage
from data_structure import LiquidationBatch, Item, BatchSummary


class NumberedCanvas(canvas.Canvas):
    """Custom canvas for page numbering"""

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for (page_num, page_state) in enumerate(self._saved_page_states):
            self.__dict__.update(page_state)
            if page_num > 0:  # Skip page number on cover
                self.draw_page_number(page_num + 1, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_num: int, total_pages: int):
        """Draw page number"""
        self.setFont("Helvetica", 10)
        self.setFillColor(colors.grey)
        self.drawRightString(
            letter[0] - 0.75 * inch,
            0.75 * inch,
            f"Page {page_num} of {total_pages}"
        )


class PDFGenerator:
    """Generate custom PDF reports from liquidation batch data"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles with large, visible text"""

        # Cover page title
        self.styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=self.styles['Title'],
            fontSize=48,
            spaceAfter=30,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        # Cover page lot number
        self.styles.add(ParagraphStyle(
            name='CoverLot',
            parent=self.styles['Title'],
            fontSize=32,
            spaceAfter=20,
            textColor=colors.HexColor('#333333'),
            alignment=TA_CENTER,
            fontName='Helvetica'
        ))

        # Section headers - large and bold
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=20,
            spaceAfter=15,
            spaceBefore=10,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        ))

        # Sub headers
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=10,
            spaceBefore=8,
            textColor=colors.HexColor('#333333'),
            fontName='Helvetica-Bold'
        ))

        # Body text - larger and more readable
        self.styles.add(ParagraphStyle(
            name='LargeBody',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=8,
            leading=16,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica'
        ))

        # Item details text
        self.styles.add(ParagraphStyle(
            name='ItemDetail',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=4,
            leading=14,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica'
        ))

        # Item title
        self.styles.add(ParagraphStyle(
            name='ItemTitle',
            parent=self.styles['Normal'],
            fontSize=14,
            spaceAfter=6,
            leading=16,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica-Bold'
        ))

    def generate_report(self, batch: LiquidationBatch, output_path: str):
        """Generate the custom PDF report"""
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=inch,
            bottomMargin=inch,
            canvasmaker=NumberedCanvas
        )

        story = []

        # 1. Cover page
        story.extend(self._create_cover_page(batch.summary))
        story.append(PageBreak())

        # 2. Summary page with details and financial analysis
        story.extend(self._create_summary_page(batch))
        story.append(PageBreak())

        # 3. Item catalog with images
        story.extend(self._create_image_catalog(batch.items))

        # Build PDF
        doc.build(story)
        return output_path

    def _create_cover_page(self, summary: BatchSummary) -> List:
        """Create cover page with 'Liquidation Blitz' title and lot number"""
        content = []

        # Add some space from top
        content.append(Spacer(1, 2*inch))

        # Main title
        title = "Liquidation Blitz"
        content.append(Paragraph(title, self.styles['CoverTitle']))

        # Add space between title and lot number
        content.append(Spacer(1, 0.8*inch))

        # Lot number
        lot_text = f"Lot #{summary.lot_number}"
        content.append(Paragraph(lot_text, self.styles['CoverLot']))

        # Add some decorative space
        content.append(Spacer(1, 1*inch))

        # Category and date info
        info_text = f"""
        <para alignment="center">
        <font size="16" color="#666666">
        {summary.category}<br/>
        {summary.processed_date.strftime('%B %d, %Y')}
        </font>
        </para>
        """
        content.append(Paragraph(info_text, self.styles['LargeBody']))

        # Add space and sale notice
        content.append(Spacer(1, 0.5*inch))

        sale_notice = """
        <para alignment="center">
        <font size="18" color="#d32f2f"><b>SOLD AS SINGLE LOT ONLY</b></font><br/>
        <font size="14" color="#666666">All items must be purchased together</font>
        </para>
        """
        content.append(Paragraph(sale_notice, self.styles['LargeBody']))

        return content

    def _create_summary_page(self, batch: LiquidationBatch) -> List:
        """Create summary page with details and financial analysis"""
        content = []

        # Details section
        content.append(Paragraph("Details", self.styles['SectionHeader']))

        # Batch information in large, readable format
        details_data = [
            ['Location:', batch.summary.location],
            ['Category:', batch.summary.category],
            ['Season:', batch.summary.season_code or 'N/A'],
            ['Return Type:', batch.summary.return_type],
            ['Total Pallets:', f"{batch.summary.num_pallets:,}"],
            ['Total Cartons:', f"{batch.summary.num_cartons:,}"],
            ['Total Units:', f"{batch.summary.total_units:,}"],
        ]

        details_table = Table(details_data, colWidths=[2.2*inch, 4.5*inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        content.append(details_table)
        content.append(Spacer(1, 0.4*inch))

        # Financial Analysis
        content.append(Paragraph("Financial Analysis", self.styles['SectionHeader']))

        # Calculate key metrics
        original_cost = sum(item.total_original_cost for item in batch.items)
        client_cost = sum(item.total_client_cost for item in batch.items)
        retail_value = sum(item.total_original_retail for item in batch.items)
        discount_percent = ((retail_value - client_cost) / retail_value * 100)

        financial_data = [
            ['Metric', 'Amount'],
            ['Total Client Cost', f"${int(client_cost):,d}"],
            ['Total Original Retail', f"${int(retail_value):,d}"],
            ['Total Savings', f"${int(retail_value - client_cost):,d}"],
            ['Average Discount', f"{discount_percent:.1f}%"],
            ['Average Item Cost', f"${int(batch.avg_item_cost):,d}"],
            ['Unique Items', f"{batch.total_items:,}"],
        ]

        financial_table = Table(financial_data, colWidths=[2.8*inch, 2*inch])
        financial_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('GRID', (0, 0), (-1, -1), 1.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))

        content.append(financial_table)

        # Add lot sale notice
        content.append(Spacer(1, 0.3*inch))

        lot_notice = """
        <para alignment="center">
        <font size="16" color="#d32f2f"><b>⚠️ IMPORTANT: SOLD AS COMPLETE LOT ONLY</b></font><br/>
        <font size="12" color="#666666">Individual items cannot be purchased separately</font>
        </para>
        """
        content.append(Paragraph(lot_notice, self.styles['LargeBody']))

        return content

    def _create_image_catalog(self, items: List[Item]) -> List:
        """Create item catalog with images on left, details on right (3-4 items per page)"""
        content = []

        content.append(Paragraph("Item Catalog", self.styles['SectionHeader']))
        content.append(Spacer(1, 0.2*inch))

        # Group items (3 per page for better spacing)
        items_per_page = 3

        for i in range(0, len(items), items_per_page):
            page_items = items[i:i + items_per_page]

            # Create items for this page
            page_content = []

            for item in page_items:
                item_content = self._create_item_entry(item)
                page_content.append(KeepTogether(item_content))
                page_content.append(Spacer(1, 0.3*inch))

            content.extend(page_content)

            # Add page break if there are more items
            if i + items_per_page < len(items):
                content.append(PageBreak())

        return content

    def _create_item_entry(self, item: Item) -> List:
        """Create a single item entry with image on left, details on right"""
        content = []

        # Create table with image and details
        image_cell = self._get_item_image(item)
        details_cell = self._get_item_details(item)

        # Create two-column layout
        item_table = Table(
            [[image_cell, details_cell]],
            colWidths=[2.5*inch, 4*inch]
        )

        item_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        content.append(item_table)

        # Add a separator line
        content.append(Spacer(1, 0.1*inch))
        separator = Table([['']]*1, colWidths=[6.5*inch])
        separator.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.lightgrey),
        ]))
        content.append(separator)

        return content

    def _get_item_image(self, item: Item):
        """Get item image or placeholder"""
        try:
            if item.image_url and item.image_url.startswith('http'):
                # Download and resize image
                response = requests.get(item.image_url, timeout=10)
                if response.status_code == 200:
                    image_data = BytesIO(response.content)
                    pil_image = PILImage.open(image_data)

                    # Resize to fit (maintain aspect ratio)
                    max_size = (200, 200)  # 2 inch roughly
                    pil_image.thumbnail(max_size, PILImage.Resampling.LANCZOS)

                    # Save to BytesIO
                    img_buffer = BytesIO()
                    pil_image.save(img_buffer, format='PNG')
                    img_buffer.seek(0)

                    # Create ReportLab Image
                    img = Image(img_buffer, width=pil_image.width, height=pil_image.height)
                    return img
        except Exception as e:
            print(f"Could not load image for {item.upc}: {e}")

        # Placeholder if image fails
        placeholder_text = f"""
        <para alignment="center">
        <font size="10" color="#999999">
        [Image Not Available]<br/>
        UPC: {item.upc}
        </font>
        </para>
        """
        return Paragraph(placeholder_text, self.styles['ItemDetail'])

    def _get_item_details(self, item: Item):
        """Get formatted item details"""
        # Calculate profit margin
        profit_margin = ((item.original_retail - item.client_cost) / item.original_retail * 100) if item.original_retail > 0 else 0

        details_html = f"""
        <font size="14" color="#1a1a1a"><b>{item.description}</b></font><br/>
        <br/>
        <font size="12" color="#1a1a1a">
        <b>UPC:</b> {item.upc}<br/>
        <b>Quantity:</b> <font color="#1565c0">{item.original_qty}</font><br/>
        <b>Size:</b> {item.size}<br/>
        <b>Color:</b> {item.color}<br/>
        <br/>
        <b>Client Cost:</b> <font color="#d32f2f">${int(item.client_cost):,d}</font> <font color="#666666">(each)</font><br/>
        <b>Total Cost:</b> <font color="#d32f2f">${int(item.total_client_cost):,d}</font><br/>
        <b>Original Retail:</b> <font color="#666666">${int(item.original_retail):,d}</font> <font color="#666666">(each)</font><br/>
        <b>Savings:</b> <font color="#2e7d32">{profit_margin:.0f}% off retail</font><br/>
        <br/>
        <b>Vendor:</b> {item.vendor_name.split('/')[0] if '/' in item.vendor_name else item.vendor_name}<br/>
        <b>Style #:</b> {item.vendor_style}
        </font>
        """

        return Paragraph(details_html, self.styles['ItemDetail'])


# Example usage
if __name__ == "__main__":
    # Install requests if not available
    try:
        import requests
    except ImportError:
        print("Installing requests library...")
        os.system("pip3 install requests")
        import requests

    from data_structure import BatchProcessor

    # Process the sample Excel file
    processor = BatchProcessor()
    batch = processor.parse_excel_file("/Users/fevrose/Downloads/Liquidation Blits/16601678.xlsx")

    # Generate PDF report
    generator = PDFGenerator()
    output_path = "/Users/fevrose/Downloads/Liquidation Blits/liquidation_blits_report.pdf"
    generator.generate_report(batch, output_path)

    print(f"PDF report generated: {output_path}")