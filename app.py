
import streamlit as st
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
    st.set_page_config(layout="wide")
    st.header(f"📝 SEO Description Editor – {label}")

    df = df[df['desc (product.metafields.custom.desc)'].notnull()].copy()
    df['edited'] = False

    batch_size = 10
    start_idx = st.session_state.get('start_idx', 0)
    end_idx = start_idx + batch_size

    if end_idx > len(df):
        end_idx = len(df)

    cols = st.columns(2)

    for i, idx in enumerate(range(start_idx, end_idx)):
        row = df.iloc[idx]
        col = cols[i % 2]

        with col.container():
            st.markdown(f"**SKU:** {row['Handle']}")
            current_desc = row.get('desc (product.metafields.custom.desc)') or row.get('Body (HTML)', 'No description available.')
            st.markdown(f"**Current Description:** {current_desc}")

            fabric = row.get('fabric', '')
            prompt = f"Give me a compelling SEO description for a {fabric} saree based on: \"{current_desc}, {row.get('product_type', '')}\""
            st.code(prompt, language='text')

            new_desc = st.text_area(f"New SEO description for SKU {row['Handle']}:", key=f'desc_input_{idx}')

            df.at[idx, 'new_desc'] = new_desc

    if st.button("✅ Submit This Batch"):
        for idx in range(start_idx, end_idx):
            new_text = df.at[idx, 'new_desc']
            if pd.notnull(new_text) and new_text.strip():
                df.at[idx, 'desc (product.metafields.custom.desc)'] = new_text
                df.at[idx, 'SEO Description'] = new_text
                df.at[idx, 'Body (HTML)'] = new_text
                df.at[idx, 'edited'] = True

        save_data(df[df['edited']], key)
        st.session_state['start_idx'] = end_idx if end_idx < len(df) else 0
        st.rerun()

tab = st.selectbox("Choose Product Type", ['Wedding', 'Trending'])

if tab == 'Wedding':
    df = load_data(WEDDING_KEY)
    seo_editor_app("Wedding", df, UPDATED_WEDDING)

elif tab == 'Trending':
    df = load_data(TRENDING_KEY)
    seo_editor_app("Trending", df, UPDATED_TRENDING)
