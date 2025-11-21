"""
Streamlit UI for Liquidation Blitz application.
Provides web interface for batch processing and catalog management.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import tempfile
import os
from datetime import datetime

from data_structure import BatchProcessor
from pdf_generator import PDFGenerator
from s3_manager import S3Manager
from csv_generator import CatalogGenerator
from config import Config

# Page configuration
st.set_page_config(
    page_title="Liquidation Blitz",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    </style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if 'processed_batches' not in st.session_state:
        st.session_state.processed_batches = []
    if 's3_manager' not in st.session_state:
        st.session_state.s3_manager = None
    if 'catalog_df' not in st.session_state:
        st.session_state.catalog_df = None
    if 'batch_data' not in st.session_state:
        st.session_state.batch_data = None
    if 'markup_percentage' not in st.session_state:
        st.session_state.markup_percentage = 0.0


def get_s3_manager():
    """Get or create S3 manager instance."""
    if st.session_state.s3_manager is None:
        try:
            st.session_state.s3_manager = S3Manager()
        except Exception as e:
            st.error(f"Failed to initialize S3 Manager: {e}")
            return None
    return st.session_state.s3_manager


def load_catalog():
    """Load catalog from S3."""
    s3_manager = get_s3_manager()
    if s3_manager is None:
        return None

    try:
        with st.spinner("Loading catalog from S3..."):
            catalog_path = str(Config.TEMP_DIR / Config.CATALOG_FILENAME)
            s3_manager.download_catalog_from_s3(catalog_path)

            if Path(catalog_path).exists():
                df = pd.read_csv(catalog_path)
                st.session_state.catalog_df = df
                return df
            else:
                # Create empty catalog
                df = pd.DataFrame(columns=Config.CSV_COLUMNS)
                st.session_state.catalog_df = df
                return df
    except Exception as e:
        st.error(f"Error loading catalog: {e}")
        return None


def process_single_batch(excel_file, file_name, markup_percentage=0.0):
    """Process a single batch file."""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(excel_file.read())
            tmp_path = tmp_file.name

        # Parse Excel
        batch_processor = BatchProcessor()
        batch = batch_processor.parse_excel_file(tmp_path)

        # Store batch data for review
        return {
            'success': True,
            'batch': batch,
            'tmp_path': tmp_path,
            'file_name': file_name
        }

    except Exception as e:
        return {
            'success': False,
            'file_name': file_name,
            'error': str(e)
        }


def finalize_batch_processing(batch, tmp_path, markup_percentage=0.0):
    """Generate PDF and update catalog with markup."""
    try:
        s3_manager = get_s3_manager()

        # Step 1: Upload images to S3
        st.info(f"📸 Uploading images for batch #{batch.summary.lot_number}...")
        image_urls = [item.image_url for item in batch.items if item.image_url]
        s3_image_urls = s3_manager.upload_images_batch(image_urls, batch.summary.lot_number)

        # Update batch items with S3 image URLs
        for idx, item in enumerate(batch.items):
            if idx < len(s3_image_urls) and s3_image_urls[idx]:
                item.image_url = s3_image_urls[idx]

        # Step 2: Generate PDF (now with S3 image URLs)
        st.info(f"📄 Generating PDF...")
        pdf_generator = PDFGenerator()
        pdf_path = str(Config.OUTPUT_DIR / f"batch_{batch.summary.lot_number}.pdf")
        pdf_generator.generate_report(batch, pdf_path)

        # Step 3: Upload PDF to S3
        st.info(f"☁️ Uploading PDF to S3...")
        pdf_url = s3_manager.upload_pdf_to_s3(pdf_path, batch.summary.lot_number)

        # Step 4: Update catalog with markup
        st.info(f"📋 Updating catalog...")
        catalog_path = str(Config.TEMP_DIR / Config.CATALOG_FILENAME)
        catalog_generator = CatalogGenerator()
        catalog_generator.update_catalog(batch, pdf_url, catalog_path, markup_percentage)

        # Step 5: Upload catalog to S3
        st.info(f"☁️ Uploading catalog to S3...")
        catalog_url = s3_manager.upload_catalog_to_s3(catalog_path)

        # Clean up temp file
        os.unlink(tmp_path)

        # Calculate final price with markup
        base_price = batch.summary.total_client_cost
        final_price = base_price * (1 + markup_percentage / 100.0)

        return {
            'success': True,
            'batch_number': batch.summary.lot_number,
            'category': batch.summary.category,
            'units': batch.summary.total_units,
            'base_price': base_price,
            'markup_percentage': markup_percentage,
            'final_price': final_price,
            'pdf_url': pdf_url,
            'catalog_url': catalog_url
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def delete_batches_from_catalog(batch_ids_to_delete):
    """Delete selected batches from catalog."""
    try:
        # Load current catalog
        catalog_path = str(Config.TEMP_DIR / Config.CATALOG_FILENAME)
        s3_manager = get_s3_manager()
        s3_manager.download_catalog_from_s3(catalog_path)

        # Read catalog
        df = pd.read_csv(catalog_path)

        # Filter out selected batches
        df = df[~df['id'].isin(batch_ids_to_delete)]

        # Save updated catalog
        df.to_csv(catalog_path, index=False)

        # Upload to S3
        catalog_url = s3_manager.upload_catalog_to_s3(catalog_path)

        # Update session state
        st.session_state.catalog_df = df

        return True, catalog_url

    except Exception as e:
        st.error(f"Error deleting batches: {e}")
        return False, None


def main():
    """Main Streamlit application."""
    initialize_session_state()

    # Header
    st.markdown('<div class="main-header">📦 Liquidation Blitz</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar - Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Check AWS configuration
        try:
            Config.validate()
            st.success("✅ AWS configured")

            # Test S3 connection
            s3_manager = get_s3_manager()
            if s3_manager and s3_manager.check_connection():
                st.success("✅ S3 connected")
            else:
                st.error("❌ S3 connection failed")
        except ValueError as e:
            st.error(f"❌ Configuration error")
            st.code(str(e))
            st.info("💡 Configure AWS credentials in Streamlit secrets or .env file")

        st.markdown("---")

        # Statistics
        st.header("📊 Catalog Stats")
        if st.button("Refresh Catalog"):
            load_catalog()

        if st.session_state.catalog_df is not None:
            df = st.session_state.catalog_df
            st.metric("Total Batches", len(df))

            if len(df) > 0 and 'price' in df.columns:
                # Parse prices
                prices = df['price'].str.replace(' USD', '').astype(float)
                total_value = prices.sum()
                st.metric("Total Value", f"${total_value:,.2f}")

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload & Review", "📋 Manage Catalog", "📊 View Catalog", "ℹ️ Help"])

    # Tab 1: Upload & Review Batches
    with tab1:
        st.header("Upload & Review Batches")
        st.markdown("Upload Excel files, review batch details, set markup, and generate PDF + Catalog.")

        # Step 1: Upload Files
        st.subheader("Step 1: Upload Excel Files")
        uploaded_files = st.file_uploader(
            "Choose Excel files",
            type=['xlsx', 'xls'],
            accept_multiple_files=True,
            help="Select multiple Excel files to process batches"
        )

        if uploaded_files:
            st.info(f"📁 {len(uploaded_files)} file(s) selected")

            # Step 2: Parse and Review
            if st.button("📋 Parse Files", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                parsed_batches = []

                for idx, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Parsing {uploaded_file.name}...")
                    result = process_single_batch(uploaded_file, uploaded_file.name)

                    if result['success']:
                        parsed_batches.append(result)

                    progress_bar.progress((idx + 1) / len(uploaded_files))

                status_text.empty()
                progress_bar.empty()

                if parsed_batches:
                    st.session_state.batch_data = parsed_batches
                    st.success(f"✅ Parsed {len(parsed_batches)} batch(es) successfully!")
                    st.rerun()

        # Step 3: Review and Set Markup
        if st.session_state.batch_data:
            st.markdown("---")
            st.subheader("Step 2: Review Batches & Set Markup")

            # Global markup setting
            col1, col2 = st.columns([3, 1])
            with col1:
                st.session_state.markup_percentage = st.slider(
                    "Markup Percentage (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=st.session_state.markup_percentage,
                    step=0.5,
                    help="Set the markup percentage to add to the base cost"
                )
            with col2:
                st.metric("Markup", f"{st.session_state.markup_percentage}%")

            # Show batch details with pricing
            st.markdown("**Batch Details:**")

            for idx, batch_data in enumerate(st.session_state.batch_data):
                batch = batch_data['batch']
                base_price = batch.summary.total_client_cost
                markup_amount = base_price * (st.session_state.markup_percentage / 100.0)
                final_price = base_price + markup_amount

                with st.expander(f"Batch #{batch.summary.lot_number} - {batch.summary.category}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write(f"**Category:** {batch.summary.category}")
                        st.write(f"**Units:** {batch.summary.total_units}")
                        st.write(f"**Location:** {batch.summary.location}")

                    with col2:
                        st.write(f"**Base Cost:** ${base_price:,.2f}")
                        st.write(f"**Markup:** +${markup_amount:,.2f} ({st.session_state.markup_percentage}%)")
                        st.write(f"**Final Price:** ${final_price:,.2f}")

                    with col3:
                        profit = batch.summary.total_original_retail - final_price
                        savings_pct = (profit / batch.summary.total_original_retail * 100) if batch.summary.total_original_retail > 0 else 0
                        st.write(f"**Original Retail:** ${batch.summary.total_original_retail:,.2f}")
                        st.write(f"**Customer Savings:** ${profit:,.2f}")
                        st.write(f"**Savings %:** {savings_pct:.1f}%")

            # Step 4: Generate PDF and Upload
            st.markdown("---")
            st.subheader("Step 3: Generate PDF & Upload to Catalog")

            if st.button("🚀 Generate PDFs & Update Catalog", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                results = []

                for idx, batch_data in enumerate(st.session_state.batch_data):
                    batch = batch_data['batch']
                    tmp_path = batch_data['tmp_path']

                    status_text.text(f"Processing batch #{batch.summary.lot_number}...")

                    result = finalize_batch_processing(batch, tmp_path, st.session_state.markup_percentage)
                    results.append(result)

                    progress_bar.progress((idx + 1) / len(st.session_state.batch_data))

                status_text.empty()
                progress_bar.empty()

                # Show results
                successful = [r for r in results if r['success']]
                if successful:
                    st.success(f"✅ Successfully processed {len(successful)} batch(es)")

                    for result in successful:
                        with st.expander(f"Batch #{result['batch_number']} Details"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Category:** {result['category']}")
                                st.write(f"**Units:** {result['units']}")
                                st.write(f"**Base Cost:** ${result['base_price']:,.2f}")
                                st.write(f"**Markup:** {result['markup_percentage']}%")
                                st.write(f"**Final Price:** ${result['final_price']:,.2f}")
                            with col2:
                                st.write("**PDF URL:**")
                                st.code(result['pdf_url'], language=None)

                    # Show final catalog URL
                    st.markdown("---")
                    st.success("📊 Catalog Updated!")
                    st.write("**Catalog URL:**")
                    st.code(successful[-1]['catalog_url'], language=None)

                # Failed batches
                failed = [r for r in results if not r['success']]
                if failed:
                    st.error(f"❌ Failed to process {len(failed)} batch(es)")
                    for result in failed:
                        st.error(result['error'])

                # Clear session data
                st.session_state.batch_data = None
                load_catalog()

    # Tab 2: Manage Catalog
    with tab2:
        st.header("Manage Catalog")
        st.markdown("View and delete batches from the catalog.")

        if st.button("🔄 Load Catalog from S3"):
            load_catalog()

        if st.session_state.catalog_df is not None:
            df = st.session_state.catalog_df

            if len(df) == 0:
                st.info("📭 Catalog is empty. Upload some batches to get started!")
            else:
                st.subheader(f"Current Catalog ({len(df)} batches)")

                # Display catalog with selection
                st.markdown("**Select batches to delete:**")

                # Create selection dataframe
                display_df = df[['id', 'title', 'price', 'condition', 'availability']].copy()
                display_df.columns = ['Batch ID', 'Title', 'Price', 'Condition', 'Availability']

                # Multi-select for deletion
                selected_indices = []

                for idx, row in display_df.iterrows():
                    col1, col2, col3, col4, col5, col6 = st.columns([1, 4, 2, 2, 2, 1])

                    with col1:
                        if st.checkbox("", key=f"select_{idx}"):
                            selected_indices.append(idx)
                    with col2:
                        st.write(row['Batch ID'])
                    with col3:
                        st.write(row['Title'][:30] + "..." if len(row['Title']) > 30 else row['Title'])
                    with col4:
                        st.write(row['Price'])
                    with col5:
                        st.write(row['Condition'])
                    with col6:
                        if st.button("🔗", key=f"link_{idx}", help="View PDF"):
                            st.code(df.loc[idx, 'link'], language=None)

                # Delete selected
                if selected_indices:
                    st.markdown("---")
                    st.warning(f"⚠️ {len(selected_indices)} batch(es) selected for deletion")

                    batch_ids_to_delete = df.loc[selected_indices, 'id'].tolist()
                    st.write("**Batches to delete:**", ", ".join(map(str, batch_ids_to_delete)))

                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("🗑️ Delete Selected", type="primary"):
                            success, catalog_url = delete_batches_from_catalog(batch_ids_to_delete)
                            if success:
                                st.success(f"✅ Deleted {len(batch_ids_to_delete)} batch(es)")
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete batches")
                    with col2:
                        if st.button("Cancel"):
                            st.rerun()
        else:
            st.info("Click 'Load Catalog from S3' to view catalog")

    # Tab 3: View Catalog
    with tab3:
        st.header("View Complete Catalog")

        if st.button("🔄 Reload Catalog"):
            load_catalog()

        if st.session_state.catalog_df is not None:
            df = st.session_state.catalog_df

            if len(df) == 0:
                st.info("📭 Catalog is empty")
            else:
                # Display full catalog
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=600
                )

                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Catalog CSV",
                    data=csv,
                    file_name=f"liquidation_catalog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("Click 'Reload Catalog' to view catalog")

    # Tab 4: Help
    with tab4:
        st.header("Help & Instructions")

        st.markdown("""
        ## How to Use Liquidation Blitz

        ### 1. Upload & Review Tab
        **Process batches with markup:**
        1. **Upload Excel files** - Select one or more liquidation batch Excel files
        2. **Parse Files** - System reads and analyzes your batches
        3. **Review & Set Markup** - Use the slider to set your markup percentage (0-100%)
        4. **Generate PDFs & Catalog** - Creates PDFs and updates catalog with your markup

        **Markup Feature:**
        - Set a markup percentage to add to your base cost
        - See real-time pricing updates as you adjust markup
        - View customer savings and profit margins
        - Markup applies to catalog price (CSV), not PDF content

        **Image Processing:**
        - All product images automatically downloaded and uploaded to your S3
        - Images stored in organized folders by batch number
        - PDF and catalog use your S3 URLs (not original URLs)
        - Full control and ownership of all product images

        ### 2. Manage Catalog Tab
        **Delete batches:**
        1. Load catalog from S3
        2. Select checkboxes next to batches to delete
        3. Click "Delete Selected"
        4. Catalog automatically syncs to S3

        ### 3. View Catalog Tab
        **Browse & download:**
        - View complete catalog in table format
        - Download as CSV for offline use
        - See all batches with pricing and details

        ## Pricing Breakdown

        - **Base Cost**: Original cost from liquidation supplier
        - **Markup**: Your profit margin (% you add)
        - **Final Price**: What goes in the catalog (Base + Markup)
        - **Original Retail**: MSRP of the items
        - **Customer Savings**: Retail - Final Price

        ## Example

        - Base Cost: $10,000
        - Markup: 25%
        - Final Price: $12,500 (goes in catalog)
        - Original Retail: $50,000
        - Customer Savings: $37,500 (75% off retail)

        ## Tips

        - **Batch Processing**: Upload multiple files at once for efficiency
        - **Review First**: Always review batch details before finalizing
        - **Adjust Markup**: Try different markups to find the right price point
        - **Save URLs**: Copy PDF and Catalog URLs for sharing

        ## Troubleshooting

        **Configuration Error:**
        - Make sure `.streamlit/secrets.toml` is configured with AWS credentials

        **S3 Connection Failed:**
        - Check AWS Access Key ID and Secret Access Key
        - Verify bucket name and region
        - Ensure IAM user has S3 permissions

        **Upload Failed:**
        - Verify Excel file format matches expected structure
        - Check file isn't corrupted

        ## Support

        For issues or questions, check [README.md](README.md) for full documentation.
        """)


if __name__ == '__main__':
    main()
