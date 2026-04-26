import pandas as pd

def merge_datasets():
    # Define file paths
    base_dir = r"c:\Users\user\Desktop\3Y\S02\GP\project\pm25-air-quality\data"
    file1_path = rf"{base_dir}\dataset_with_landuse.csv"
    file2_path = rf"{base_dir}\gee_features_daily_updated.csv"
    file3_path = rf"{base_dir}\combined_gee_pm25.csv"

    print("Loading datasets...")
    # 1. Load the datasets
    df_landuse = pd.read_csv(file1_path)
    df_gee = pd.read_csv(file2_path)
    df_combined = pd.read_csv(file3_path)

    # 2. Rename coordinate columns in the GEE dataset to match the others
    df_gee = df_gee.rename(columns={'lat': 'latitude', 'lon': 'longitude'})

    # 3. Set up the merge keys
    merge_keys = ['date', 'latitude', 'longitude']

    # 4. Handle overlapping columns 
    # Keep the columns from df_combined as the base, drop overlapping from df_landuse
    common_landuse = set(df_combined.columns).intersection(set(df_landuse.columns)) - set(merge_keys)
    df_landuse = df_landuse.drop(columns=list(common_landuse))
    
    print("Merging dataset_with_landuse...")
    # Merge df_combined with df_landuse (exact match on keys, no tolerance)
    merged_df = pd.merge(
        df_combined, 
        df_landuse, 
        how='inner', 
        on=merge_keys
    )
    
    # Drop overlapping columns from df_gee
    common_gee = set(merged_df.columns).intersection(set(df_gee.columns)) - set(merge_keys)
    df_gee = df_gee.drop(columns=list(common_gee))
    
    print("Merging gee_features_daily_updated...")
    # Merge the result with df_gee (exact match on keys, no tolerance)
    final_merged_df = pd.merge(
        merged_df, 
        df_gee, 
        how='inner', 
        on=merge_keys
    )

    print(f"Merge complete! Final dataset shape: {final_merged_df.shape}")
    
    # 5. Save the final dataset
    output_path = rf"{base_dir}\final dataset.csv"
    final_merged_df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    merge_datasets()
