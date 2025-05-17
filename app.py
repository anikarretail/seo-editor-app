def merge_and_save_full_df(full_df, updated_rows, key):
    try:
        # Load previous version of updated file if it exists
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        prev_df = pd.read_csv(io.BytesIO(obj['Body'].read()))
    except s3.exceptions.NoSuchKey:
        # No previous file, so start from full_df
        prev_df = full_df.copy()

    # Merge previous updates into full_df
    for col in ['desc (product.metafields.custom.desc)', 'SEO Description', 'Body (HTML)', 'seo_done']:
        if col in prev_df.columns:
            full_df[col] = full_df[col].combine_first(prev_df[col])

    # Overwrite the relevant rows from this batch
    for _, row in updated_rows.iterrows():
        mask = (full_df['Handle'] == row['Handle']) & (full_df['Image Src'] == row['Image Src'])
        for col in ['desc (product.metafields.custom.desc)', 'SEO Description', 'Body (HTML)', 'seo_done']:
            if col in row:
                full_df.loc[mask, col] = row[col]

    # Save full updated dataset
    buffer = io.StringIO()
    full_df.to_csv(buffer, index=False)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
