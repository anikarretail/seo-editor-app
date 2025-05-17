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

def load_data(source_key, updated_key):
    # Load base data
    obj = s3.get_object(Bucket=BUCKET, Key=source_key)
    base_df = pd.read_csv(io.BytesIO(obj['Body'].read()))
    base_df.columns = base_df.columns.str.strip()
    base_df['seo_done'] = ''

    # Merge in any completed handles
    try:
        upd = pd.read_csv(io.BytesIO(
            s3.get_object(Bucket=BUCKET, Key=updated_key)['Body'].read()
        ))
        upd.columns = upd.columns.str.strip()
        if 'seo_done' in upd.columns:
            done_handles = upd.loc[
                upd['seo_done'].astype(str).str.upper() == 'TRUE',
                'Handle'
            ].unique()
            base_df['seo_done'] = base_df['Handle'].apply(
                lambda h: 'TRUE' if h in done_handles else ''
            )
    except s3.exceptions.NoSuchKey:
        pass

    return base_df

def append_rows_by_handle(df, updated_handles, key):
    subset = df[df['Handle'].isin(updated_handles)].drop(columns='index')
    try:
        existing = pd.read_csv(io.BytesIO(
            s3.get_object(Bucket=BUCKET, Key=key)['Body'].read()
        ))
        combined = pd.concat([existing, subset], ignore_index=True)
    except s3.exceptions.NoSuchKey:
        combined = subset

    buf = io.StringIO()
    combined.to_csv(buf, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buf.getvalue())

def seo_editor_app(label, df, key):
    st.header(f"📝 SEO Description Editor – {label}")

    df['seo_done'] = df.get('seo_done', '').fillna('')
    df.reset_index(inplace=True)

    editable = df[
        df['Title'].notnull() &
        (df['Title'] != '') &
        df['desc (product.metafields.custom.desc)'].notnull() &
        (df['seo_done'] == '')
    ].copy()

    # ✅ Notify and exit if all done
    if editable.empty:
        st.success(f"✅ All {label.lower()} products are complete! Nothing left to edit.")

        # ✅ SNS notification
        try:
            sns = boto3.client('sns')
            sns.publish(
                TopicArn='arn:aws:sns:us-west-2:568869123221:seo-review-complete',
                Subject='SEO Review Complete',
                Message=f'All {label} products have been reviewed for SEO and saved.'
            )
        except Exception as e:
            st.warning(f"SNS notification failed: {e}")

        return

    # Otherwise, show batch of 5 products
    batch_size = 5
    if 'start_idx' not in st.session_state:
        st.session_state['start_idx'] = 0

    start = st.session_state['start_idx']
    pending = editable.iloc[start:start + batch_size]
    cols = st.columns(2)

    for i, (_, row) in enumerate(pending.iterrows()):
        col = cols[i % 2]
        with col.container():
            st.markdown(
                '<div style="background-color:#f7f9fc;padding:15px;border-radius:10px;">',
                unsafe_allow_html=True
            )
            st.markdown(f"**SKU:** {row['Handle']}")
            desc = row['desc (product.metafields.custom.desc)'] or row.get('Body (HTML)', 'No description available.')
            st.markdown(f"**Current Description:** {desc}")
            fabric = row.get('fabric', '')
            prompt = (
                f"Write a short SEO-optimized product description "
                f"(max 150 chars) for a Bandisha {fabric} saree based on: "
                f"\"{desc}, {row.get('product_type','')}\""
            )
            st.code(prompt, language='text')
            new = st.text_area(f"New SEO description for SKU {row['Handle']}:", key=f'desc_input_{i}')
            pending.at[row.name, 'new_desc'] = new
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("✅ Submit This Batch"):
        updated_handles = set()
        for _, row in pending.iterrows():
            text = row.get('new_desc')
            if pd.notnull(text) and text.strip():
                idx = row['index']
                df.at[idx, 'desc (product.metafields.custom.desc)'] = text
                df.at[idx, 'SEO Description'] = text
                df.at[idx, 'Body (HTML)'] = text
                df.at[idx, 'seo_done'] = 'TRUE'
                updated_handles.add(row['Handle'])

        if updated_handles:
            append_rows_by_handle(df, updated_handles, key)

        st.session_state['start_idx'] += batch_size
        if st.session_state['start_idx'] >= len(editable):
            st.session_state['start_idx'] = 0
        st.rerun()

# ——— UI Entry Point ——————————————
choice = st.selectbox("Choose Product Type", ['Trending', 'Wedding'])
if choice == 'Trending':
    df_tr = load_data(TRENDING_KEY, UPDATED_TRENDING)
    seo_editor_app("Trending", df_tr, UPDATED_TRENDING)
else:
    df_wed = load_data(WEDDING_KEY, UPDATED_WEDDING)
    seo_editor_app("Wedding", df_wed, UPDATED_WEDDING)
