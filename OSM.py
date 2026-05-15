import osmnx as ox
import pandas as pd
from tqdm import tqdm

# Load dataset
unique_coord = pd.read_csv('unique_locations.csv')

# Increase radius to 2000m
radius = 2000

features_list = []
for _, loc_row in tqdm(unique_coord.iterrows(), total=len(unique_coord), desc="Locations"):
    lat, lon = loc_row['latitude'], loc_row['longitude']
    
    # Default zeros for static land features
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
osm_features.to_csv('land_features.csv', index=False)
print(f"Done! Processed {len(unique_coord)} locations with {radius}m radius")