import pandas as pd

def merge_datasets():
    # Define file paths
    base_dir = r"C:\Users\sarah\Desktop\Groupe Project\pm25-air-quality\Global_approach\data"
    combined_path = rf"{base_dir}\combined_gee_pm25.csv"
    land_features_path = rf"{base_dir}\land_features.csv"

    print("Loading datasets...")
    df_combined = pd.read_csv(combined_path)
    df_landuse = pd.read_csv(land_features_path)

    # Keep the merge at location level only.
    # The combined dataset already contains one row per date/location,
    # while land features are static attributes that should be repeated
    # across all dates for the same coordinates.
    merge_keys = ['latitude', 'longitude']

    # Normalize coordinate column types so exact float/string mismatches do not block the join.
    for frame in (df_combined, df_landuse):
        frame['latitude'] = pd.to_numeric(frame['latitude'], errors='coerce').round(4)
        frame['longitude'] = pd.to_numeric(frame['longitude'], errors='coerce').round(4)

    # Drop duplicate land rows per location so the merge does not multiply records.
    df_landuse = df_landuse.drop_duplicates(subset=merge_keys, keep='first').copy()

    # Keep the combined dataset columns as the base, and only add land columns that do not already exist.
    overlapping_columns = set(df_combined.columns).intersection(df_landuse.columns) - set(merge_keys)
    df_landuse = df_landuse.drop(columns=list(overlapping_columns), errors='ignore')

    print("Merging land features onto combined PM25/GEE data...")
    final_merged_df = pd.merge(
        df_combined,
        df_landuse,
        how='left',
        on=merge_keys,
        validate='m:1'
    )

    print(f"Merge complete! Final dataset shape: {final_merged_df.shape}")
    print(f"Input rows: combined={len(df_combined):,}, land={len(df_landuse):,}")
    print(f"Output rows: {len(final_merged_df):,}")

    # Save the final dataset
    output_path = rf"{base_dir}\final_dataset_with_landuse.csv"
    final_merged_df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    merge_datasets()
