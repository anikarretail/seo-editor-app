
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

def save_data(df, key):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())

def seo_editor_app(label, df, key):
    st.header(f"📝 SEO Description Editor – {label}")

    batch_size = 5
    if 'start_idx' not in st.session_state:
        st.session_state['start_idx'] = 0
    start_idx = st.session_state['start_idx']
    end_idx = start_idx + batch_size

    editable_df = df[df['desc (product.metafields.custom.desc)'].notnull()].reset_index()
    if end_idx > len(editable_df):
        end_idx = len(editable_df)

    cols = st.columns(2)

    for i, row_idx in enumerate(range(start_idx, end_idx)):
        row = editable_df.iloc[row_idx]
        col = cols[i % 2]
        with col.container():
            with col:
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
                new_desc = st.text_area(f"New SEO description for SKU {row['Handle']}:", key=f'desc_input_{row_idx}')
                st.markdown("</div>", unsafe_allow_html=True)
                editable_df.at[row_idx, 'new_desc'] = new_desc

    if st.button("✅ Submit This Batch"):
        for row_idx in range(start_idx, end_idx):
            row = editable_df.iloc[row_idx]
            new_text = row.get('new_desc')
            if pd.notnull(new_text) and new_text.strip():
                original_index = row['index']
                df.at[original_index, 'desc (product.metafields.custom.desc)'] = new_text
                df.at[original_index, 'SEO Description'] = new_text
                df.at[original_index, 'Body (HTML)'] = new_text

        save_data(df, key)
        st.session_state['start_idx'] = end_idx if end_idx < len(editable_df) else 0
        st.rerun()

tab = st.selectbox("Choose Product Type", ['Wedding', 'Trending'])

if tab == 'Wedding':
    df = load_data(WEDDING_KEY)
    seo_editor_app("Wedding", df, UPDATED_WEDDING)
elif tab == 'Trending':
    df = load_data(TRENDING_KEY)
    seo_editor_app("Trending", df, UPDATED_TRENDING)
