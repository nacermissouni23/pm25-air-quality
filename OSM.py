import osmnx as ox
import pandas as pd

def extract_features(lat, lon, radius=2000):
    # Default zeros
    n_buildings = 0
    road_length = 0
    industrial_count = 0
    green_count = 0
    
    try:
        # Buildings
        buildings = ox.features_from_point((lat, lon), tags={'building': True}, dist=radius)
        n_buildings = len(buildings) if not buildings.empty else 0
    except:
        pass
    
    try:
        # Roads
        roads = ox.features_from_point((lat, lon), tags={'highway': True}, dist=radius)
        if not roads.empty and 'geometry' in roads.columns:
            roads_proj = roads.to_crs(epsg=3857)
            road_length = roads_proj.geometry.length.sum() / 1000
    except:
        pass
    
    try:
        # Industrial
        industrial = ox.features_from_point((lat, lon), tags={'landuse': 'industrial'}, dist=radius)
        industrial_count = len(industrial) if not industrial.empty else 0
    except:
        pass
    
    try:
        # Green space
        green = ox.features_from_point((lat, lon), tags={'leisure': 'park', 'landuse': 'forest', 'natural': 'tree'}, dist=radius)
        green_count = len(green) if not green.empty else 0
    except:
        pass
    
    return pd.DataFrame([{
        'building_density': n_buildings,
        'road_density_km': road_length,
        'industrial_presence': industrial_count,
        'green_space_fraction': green_count
    }])
