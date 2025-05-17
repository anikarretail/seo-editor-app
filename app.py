import streamlit as st
st.set_page_config(layout="wide")

import boto3
import pandas as pd
import io

BUCKET = 'bandisha-shopify-files'
TRENDING_KEY = 'shopify_trending.csv'
WEDDING_KEY = 'shopify_wedding.csv'

UPDATED_TRENDING = 'shopify_trending_updated.csv'
UPDATED_WEDDING = 'shopify_wedding_updated.csv'

s3 = boto3.client('s3')

@st.cache_data
def load_data(key):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_csv(io.BytesIO(obj['Body'].read()))

def append_updated_rows(df_batch, key):
    try:
        # Try to read existing updated file
        existing_obj = s3.get_object(Bucket=BUCKET, Key=key)
        existing_df = pd.read_csv(io.BytesIO(existing_obj['Body'].read()))
        combined_df = pd.concat([existing_df, df_batch], ignore_index=True)
        combined_df.drop_duplicates(subset=['Handle', 'Image Src'], keep='last', inplace=True)
    except s3.exceptions.NoSuchKey:
        # If file doesn't exist, this is the first write
        combined_df = df_batch

    # Save combined data
    buffer = io.StringIO()
    combined_df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())

def seo_editor_app(label, df, key):
    st.header(f"📝 SEO Description Editor – {label}")

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
        updated_rows = []

        for _, row in pending_batch.iterrows():
            new_text = row.get('new_desc')
            if pd.notnull(new_text) and new_text.strip():
                original_index = row['index']
                df.at[original_index, 'desc (product.metafields.custom.desc)'] = new_text
                df.at[original_index, 'SEO Description'] = new_text
                df.at[original_index, 'Body (HTML)'] = new_text
                df.at[original_index, 'seo_done'] = 'TRUE'
                updated_rows.append(df.loc[original_index])

        # Save only newly updated rows to the updated file
        if updated_rows:
            updated_df = pd.DataFrame(updated_rows).drop(columns='index')
            append_updated_rows(updated_df, key)

        st.session_state['start_idx'] += batch_size
        st.rerun()

tab = st.selectbox("Choose Product Type", ['Wedding', 'Trending'])

if tab == 'Wedding':
    df = load_data(WEDDING_KEY)
    seo_editor_app("Wedding", df, UPDATED_WEDDING)
elif tab == 'Trending':
    df = load_data(TRENDING_KEY)
    seo_editor_app("Trending", df, UPDATED_TRENDING)
