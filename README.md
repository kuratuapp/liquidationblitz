# Liquidation Blitz

Application that processes liquidation batch data from Excel spreadsheets, generates PDF reports, and maintains a Google Shopping Feed catalog on AWS S3.

## Features

- **Streamlit Web UI**: User-friendly web interface for batch processing
- **Multiple File Upload**: Process multiple liquidation batches at once
- **Excel Processing**: Parse liquidation batch data from Excel files
- **Image Upload**: Automatically downloads and uploads all product images to your S3
- **PDF Generation**: Create professional branded PDF reports with images
- **CSV Catalog Management**: View, edit, and delete batches from catalog
- **Markup/Margin**: Set profit margin percentage before generating catalog
- **S3 Integration**: Automatic upload to AWS S3 with public URLs
- **Batch Management**: Automatic batch ID tracking and catalog updates

## Complete Workflow

```
Excel File → Parse Data → Generate PDF → Upload to S3
                ↓
         PDF Public URL
                ↓
    Download Catalog from S3 → Update/Add Batch → Upload to S3
                                      ↓
                              Catalog Public URL
```

## Installation

### 1. Clone/Download Project

```bash
cd "/Users/fevrose/Downloads/Liquidation Blits"
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. AWS S3 Setup

**Create S3 Bucket:**
1. Go to AWS Console → S3
2. Create new bucket (e.g., `liquidation-blits-storage`)
3. Enable public access for specific paths
4. Apply bucket policy (see below)

**Bucket Policy Example:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME/batches/*"
      ]
    }
  ]
}
```

**Create IAM User:**
1. Go to AWS Console → IAM → Users
2. Create new user with programmatic access
3. Attach policy: `AmazonS3FullAccess` (or custom S3 policy)
4. Save Access Key ID and Secret Access Key

### 4. Configure Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use any text editor
```

Fill in your AWS credentials in `.env`:
```env
AWS_ACCESS_KEY_ID=your_actual_access_key_here
AWS_SECRET_ACCESS_KEY=your_actual_secret_key_here
AWS_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-1
```

## Usage

### Option 1: Streamlit Web UI (Recommended)

**Start the Streamlit app:**
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

**Features:**
- **Upload Batches Tab**: Upload multiple Excel files and process them in batch
- **Manage Catalog Tab**: View batches and delete selected items from catalog
- **View Catalog Tab**: Browse complete catalog and download as CSV

**Streamlit Configuration:**
1. Copy secrets template:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
2. Edit `.streamlit/secrets.toml` with your AWS credentials
3. Start the app

### Option 2: Command Line Interface

**Process a single batch:**
```bash
python main.py <excel_file_path>
```

**Example:**
```bash
python main.py 16601678.xlsx
```

**Output:**
The script will:
1. Parse the Excel file
2. Generate a PDF report
3. Upload PDF to S3
4. Download existing catalog from S3 (or create new)
5. Update catalog with batch data
6. Upload catalog to S3
7. Return public URLs for both files

**Console Output:**
```
================================================================================
SUCCESS!
================================================================================

PDF URL:
https://your-bucket.s3.us-east-1.amazonaws.com/batches/pdfs/batch-16601678.pdf

Catalog URL:
https://your-bucket.s3.us-east-1.amazonaws.com/batches/liquidationblitzcatalog.csv

================================================================================
```

## Project Structure

```
Liquidation Blitz/
├── app.py                          # Streamlit web UI
├── main.py                         # CLI orchestration script
├── config.py                       # Configuration (supports .env and Streamlit secrets)
├── data_structure.py               # Data models for batches
├── pdf_generator.py                # PDF report generation
├── csv_generator.py                # CSV catalog generation (with delete feature)
├── s3_manager.py                   # AWS S3 operations
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── .env                            # Your credentials (not in git)
├── .streamlit/
│   ├── secrets.toml.example        # Streamlit secrets template
│   └── secrets.toml                # Your Streamlit secrets (not in git)
├── .gitignore                      # Git ignore rules
├── CLAUDE.md                       # Project instructions
├── README.md                       # This file
├── output/                         # Generated PDFs (local)
└── temp/                           # Temporary files (local)
```

## CSV Catalog Structure

The catalog follows Google Shopping Feed format with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| id | Batch/lot number | "16601678" |
| title | Batch description | "Mens Suits & Coats Liquidation Batch - 147 Units" |
| description | Detailed batch info | "Liquidation Batch #16601678 \| Category: MENS SUITS & COATS..." |
| availability | Stock status | "in stock" |
| condition | Product condition | "New" |
| price | Batch price | "9622.28 USD" |
| link | PDF report URL | S3 public URL |
| image_link | Primary product image | First item's image URL |
| brand | Most common vendor | "Michael Kors" |
| google_product_category | Google category | "Apparel & Accessories > Clothing > Suits" |
| item_group_id | Optional grouping | Empty |
| shipping_weight | Weight | Empty |
| video[0].url | Video URL | Empty |
| additional_image_link | More images | Comma-separated URLs (up to 10) |

## Batch Update Logic

- **New Batch ID**: Adds new row to catalog
- **Existing Batch ID**: Replaces entire row with updated data
- **Preserves Other Batches**: Never deletes unrelated batch data

## Configuration Options

Edit [config.py](config.py) to customize:

- **S3 Paths**: Change `S3_PDF_PREFIX` and `S3_CATALOG_PREFIX`
- **Catalog Name**: Modify `CATALOG_FILENAME`
- **Category Mapping**: Update `CATEGORY_MAPPING` for Google taxonomy
- **CSV Columns**: Adjust `CSV_COLUMNS` if needed

## Troubleshooting

### S3 Connection Failed
- Verify AWS credentials in `.env`
- Check IAM user has S3 permissions
- Confirm bucket name is correct
- Test with: `aws s3 ls` (if AWS CLI installed)

### PDF Generation Error
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Check Excel file format matches expected structure
- Verify image URLs in Excel are accessible

### Catalog Upload Error
- Check bucket policy allows public-read
- Verify S3 prefix paths exist
- Ensure bucket is in correct region

## Development

### Running Tests
```bash
# Test with sample file
python main.py 16601678.xlsx
```

### Adding New Features
- Modify data models in [data_structure.py](data_structure.py)
- Update PDF layout in [pdf_generator.py](pdf_generator.py)
- Adjust CSV mapping in [csv_generator.py](csv_generator.py)

## Security Notes

- **Never commit `.env` file** - Contains AWS credentials
- **Use IAM best practices** - Least privilege access
- **Rotate credentials regularly** - Update keys periodically
- **Monitor S3 costs** - Check AWS billing dashboard

## License

Internal business tool - All rights reserved

## Support

For issues or questions, contact the development team.
