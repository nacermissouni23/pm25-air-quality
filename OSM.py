import osmnx as ox
import pandas as pd
from tqdm import tqdm

# Load dataset
df = pd.read_csv('combined_gee_pm25.csv')
unique_coords = df[['latitude', 'longitude']].drop_duplicates()

# Increase radius to 2000m
radius = 2000

features_list = []
for idx, row in tqdm(unique_coords.iterrows(), total=len(unique_coords)):
    lat, lon = row['latitude'], row['longitude']
    
    # Default zeros
    n_buildings = 0
    road_length = 0
    industrial_count = 0
    green_count = 0
    
    try:
        # Buildings
        buildings = ox.features_from_point((lat, lon), {'building': True}, dist=radius)
        n_buildings = len(buildings) if not buildings.empty else 0
    except:
        pass
    
    try:
        # Roads
        roads = ox.features_from_point((lat, lon), {'highway': True}, dist=radius)
        if not roads.empty and 'geometry' in roads.columns:
            roads_proj = roads.to_crs(epsg=3857)
            road_length = roads_proj.geometry.length.sum() / 1000
    except:
        pass
    
    try:
        # Industrial
        industrial = ox.features_from_point((lat, lon), {'landuse': 'industrial'}, dist=radius)
        industrial_count = len(industrial) if not industrial.empty else 0
    except:
        pass
    
    try:
        # Green space
        green = ox.features_from_point((lat, lon), {'leisure': 'park', 'landuse': 'forest', 'natural': 'tree'}, dist=radius)
        green_count = len(green) if not green.empty else 0
    except:
        pass
    
    features_list.append({
        'latitude': lat,
        'longitude': lon,
        'building_density': n_buildings,
        'road_density_km': road_length,
        'industrial_presence': industrial_count,
        'green_space_fraction': green_count
    })

# Merge
osm_features = pd.DataFrame(features_list)
df = df.merge(osm_features, on=['latitude', 'longitude'], how='left')
df.to_csv('dataset_with_landuse.csv', index=False)
print(f"Done! Processed {len(unique_coords)} locations with {radius}m radius")