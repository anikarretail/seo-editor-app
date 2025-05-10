
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
    st.header(f"📝 SEO Description Editor – {label}")

    df['edited'] = False
    for i in range(len(df)):
        row = df.iloc[i]
        st.markdown(f"**SKU:** {row['Handle']}")
        st.markdown(f"**Current Description:** {row['desc']}")
        
        chat_prompt = f"""Give me a compelling SEO description for a {row.get('fabric', 'saree')} saree based on: \"{row['desc']}, {row['product_type']}\""""
        st.code(chat_prompt, language='text')

        new_desc = st.text_area(f"Paste new SEO description for SKU {row['Handle']}:", key=f'desc_input_{i}')
        
        if st.button(f"✅ Submit for {row['Handle']}", key=f'submit_{i}'):
            df.at[i, 'desc (product.metafields.custom.desc)'] = new_desc
            df.at[i, 'SEO Description'] = new_desc
            df.at[i, 'Body (HTML)'] = new_desc
            df.at[i, 'edited'] = True
            st.success(f"Updated description for {row['Handle']}")
            save_data(df[df['edited']], key)
            st.rerun()

# Choose product type
tab = st.selectbox("Choose Product Type", ['Wedding', 'Trending'])

if tab == 'Wedding':
    df = load_data(WEDDING_KEY)
    seo_editor_app("Wedding", df, UPDATED_WEDDING)

elif tab == 'Trending':
    df = load_data(TRENDING_KEY)
    seo_editor_app("Trending", df, UPDATED_TRENDING)
