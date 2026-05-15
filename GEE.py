import ee
import pandas as pd
import time

# Initialize GEE
ee.Authenticate()
ee.Initialize(project='group-project-493422')

# Load your coordinates
coords_df = pd.read_csv('unique_locations.csv')

# Load your unique dates from PM2.5 data
dates_df = pd.read_csv('unique_dates.csv')
dates_list = pd.to_datetime(dates_df['date']).dt.strftime('%Y-%m-%d').tolist()

# TEST MODE: Set to True to test with a few locations and dates
TEST_MODE = False
if TEST_MODE:
    coords_df = coords_df[:2]  # Only 2 locations
    dates_list = dates_list[:30]  # 30 dates
    print(f"TEST MODE: Processing {len(coords_df)} locations × {len(dates_list)} dates")

# Create GEE feature collection from coordinates
def create_points(df):
    features = []
    for idx, row in df.iterrows():
        point = ee.Feature(
            ee.Geometry.Point([row['longitude'], row['latitude']]),
            {'id': idx, 'latitude': row['latitude'], 'longitude': row['longitude']}
        )
        features.append(point)
    return ee.FeatureCollection(features)

points = create_points(coords_df)

# Function to extract features for a single date
def extract_features_for_date(date_str):
    date = ee.Date(date_str)
    next_date = date.advance(1, 'day')
        
    # AOD
    aod = ee.ImageCollection('MODIS/061/MCD19A2_GRANULES') \
        .filterDate(date, next_date) \
        .select('Optical_Depth_055') \
        .mean() \
        .multiply(0.001)
    
    # Combine
    combined = aod
    
    # Sample
    sampled = combined.sampleRegions(
        collection=points,
        scale=11132,
        properties=['id', 'latitude', 'longitude']
    )
    
    # Format output
    result = sampled.map(lambda f: f
        .set('date', date_str)
        .set('AOD', f.get('Optical_Depth_055'))
    )
    
    return result

# Process dates in batches (to avoid memory issues)
batch_size = 5
all_data = []

for i in range(0, len(dates_list), batch_size):
    batch_dates = dates_list[i:i+batch_size]
    print(f"Processing batch {i//batch_size + 1}/{(len(dates_list)//batch_size)+1}")
    
    batch_features = ee.FeatureCollection([])
    
    for date in batch_dates:
        daily_features = extract_features_for_date(date)
        batch_features = batch_features.merge(daily_features)
    
    # Convert to pandas
    try:
        url = batch_features.getDownloadURL(filename='download.csv')
        df_batch = pd.read_csv(url)
        
        if df_batch.empty:
            print(f"  Batch skipped: no data")
        else:
            all_data.append(df_batch)
            print(f"  Batch complete: {len(df_batch)} rows")
    except Exception as e:
        print(f"  Batch skipped: {str(e)}")
    
    time.sleep(3)  # Rate limiting: pause 3 seconds between batches

# Combine all batches
final_df = pd.concat(all_data, ignore_index=True)

# Ensure all desired columns exist (fill missing with NaN)
desired_columns = [
    'date', 'id', 'latitude', 'longitude',
    'AOD'
]
for col in desired_columns:
    if col not in final_df.columns:
        final_df[col] = None

final_df = final_df[desired_columns]

print(f"\nColumns in output: {list(final_df.columns)}")

# Save
final_df.to_csv('gee_features_daily.csv', index=False)
print(f"Saved {len(final_df)} rows")
print(f"Expected: {len(coords_df)} locations × {len(dates_list)} dates = {len(coords_df) * len(dates_list)} rows")