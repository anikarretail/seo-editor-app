import streamlit as st
st.set_page_config(layout="wide")

import boto3
import pandas as pd
import io

BUCKET = 'bandisha-shopify-files'
TRENDING_KEY = 'shopify_trending.csv'
UPDATED_TRENDING = 'shopify_trending_updated.csv'

s3 = boto3.client('s3')

@st.cache_data
def load_data(source_key, updated_key):
    # Load base data
    obj = s3.get_object(Bucket=BUCKET, Key=source_key)
    base_df = pd.read_csv(io.BytesIO(obj['Body'].read()))

    # Try to load updated data if it exists
    try:
        updated_obj = s3.get_object(Bucket=BUCKET, Key=updated_key)
        updated_df = pd.read_csv(io.BytesIO(updated_obj['Body'].read()))

        # ✅ Get all handles where at least one row has seo_done = TRUE
        true_handles = updated_df.loc[updated_df['seo_done'] == 'TRUE', 'Handle'].unique()

        # ✅ Mark all rows in base_df as TRUE if handle was done earlier
        base_df['seo_done'] = base_df['Handle'].apply(lambda h: 'TRUE' if h in true_handles else '')
    except s3.exceptions.NoSuchKey:
        base_df['seo_done'] = ''

    return base_df

def append_rows_by_handle(df, updated_handles, key):
    # Get all rows for updated handles
    subset_df = df[df['Handle'].isin(updated_handles)].drop(columns='index')

    # Try to read existing file and append
    try:
        existing_obj = s3.get_object(Bucket=BUCKET, Key=key)
        existing_df = pd.read_csv(io.BytesIO(existing_obj['Body'].read()))
        combined_df = pd.concat([existing_df, subset_df], ignore_index=True)
    except s3.exceptions.NoSuchKey:
        # No file exists yet
        combined_df = subset_df

    # Save combined version
    buffer = io.StringIO()
    combined_df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())

def seo_editor_app(df, key):
    st.header("📝 SEO Description Editor – Trending")

    if 'seo_done' not in df.columns:
        df['seo_done'] = ''
    df['seo_done'] = df['seo_done'].fillna('')

    # Keep reference to original DataFrame index
    df.reset_index(inplace=True)

    # Only editable entries
    editable_df = df[
        (df['Title'].notnull()) & 
        (df['Title'] != '') & 
        (df['desc (product.metafields.custom.desc)'].notnull()) & 
        (df['seo_done'] == '')
    ].copy()

    # ✅ If everything is done
    if editable_df.empty:
        st.success("✅ All trending products are complete! Nothing left to edit.")
        return

    batch_size = 5
    if 'start_idx' not in st.session_state:
        st.session_state['start_idx'] = 0

    start_idx = st.session_state['start_idx']
    end_idx = start_idx + batch_size

    pending_batch = editable_df.iloc[start_idx:end_idx]
    cols = st.columns(2)

    for i, (_, row) in enumerate(pending_batch.iterrows()):
        col = cols[i % 2]
        with col.container():
            st.markdown(
                '<div style="background-color:#f7f9fc;padding:15px;border-radius:10px;">',
                unsafe_allow_html=True
            )
            st.markdown(f"**SKU:** {row['Handle']}")
            current_desc = row['desc (product.metafields.custom.desc)'] or row.get('Body (HTML)', 'No description available.')
            st.markdown(f"**Current Description:** {current_desc}")
            fabric = row.get('fabric', '')
            prompt = f"Write a short SEO-optimized product description (max 150 chars) for a Bandisha {fabric} saree based on: \"{current_desc}, {row.get('product_type', '')}\""
            st.code(prompt, language='text')
            new_desc = st.text_area(f"New SEO description for SKU {row['Handle']}:", key=f'desc_input_{i}')
            st.markdown("</div>", unsafe_allow_html=True)
            pending_batch.at[row.name, 'new_desc'] = new_desc

    if st.button("✅ Submit This Batch"):
        updated_handles = set()

        for _, row in pending_batch.iterrows():
            new_text = row.get('new_desc')
            if pd.notnull(new_text) and new_text.strip():
                original_index = row['index']
                df.at[original_index, 'desc (product.metafields.custom.desc)'] = new_text
                df.at[original_index, 'SEO Description'] = new_text
                df.at[original_index, 'Body (HTML)'] = new_text
                df.at[original_index, 'seo_done'] = 'TRUE'
                updated_handles.add(row['Handle'])

        if updated_handles:
            append_rows_by_handle(df, updated_handles, key)

        st.session_state['start_idx'] += batch_size
        st.rerun()

# 🚀 Load and launch app for trending products only
df = load_data(TRENDING_KEY, UPDATED_TRENDING)
seo_editor_app(df, UPDATED_TRENDING)
