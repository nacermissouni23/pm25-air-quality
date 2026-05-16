import ee
import pandas as pd
import time
from datetime import datetime, timedelta

def initialize_gee():
    try:
        # Lower the timeout to 10 seconds to fail fast instead of hanging for 2 minutes
        ee.Initialize(project='group-project-493422', opt_url='https://earthengine-highvolume.googleapis.com', http_timeout=10)
    except Exception as e:
        print("\n\n" + "="*50)
        print("GOOGLE EARTH ENGINE AUTHENTICATION REQUIRED OR NETWORK TIMEOUT.")
        print(f"Details: {e}")
        print("Because you are running inside Streamlit, we cannot show the login prompt.")
        print("Please run `python GEE.py` manually in the terminal to authenticate first!")
        print("="*50 + "\n\n")
        raise e

def extract_features(lat, lon, date_str):
    initialize_gee()
    
    point = ee.Feature(
        ee.Geometry.Point([lon, lat]),
        {'id': 1, 'lat': lat, 'lon': lon}
    )
    points = ee.FeatureCollection([point])
    
    date = ee.Date(date_str)
    next_date = date.advance(1, 'day')
    
    # Meteorology
    era5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR') \
    .filterDate(date, next_date) \
    .select(['temperature_2m', 'dewpoint_temperature_2m', 'surface_pressure', 
             'u_component_of_wind_10m', 'v_component_of_wind_10m']) \
    .mean()
    
    
    # Air Quality (will be null for pre-2018)
    no2 = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_NO2') \
        .filterDate(date, next_date) \
        .select('NO2_column_number_density') \
        .mean()
    
    co = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_CO') \
        .filterDate(date, next_date) \
        .select('CO_column_number_density') \
        .mean()
    
    o3 = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_O3') \
        .filterDate(date, next_date) \
        .select('O3_column_number_density') \
        .mean()
    
    # AOD
    aod = ee.ImageCollection('MODIS/061/MCD19A2_GRANULES') \
        .filterDate(date, next_date) \
        .select('Optical_Depth_055') \
        .map(lambda img: img.multiply(0.001)) \
        .mean()
    
    # Combine and unmask to prevent sampleRegions from dropping pixels with missing bands (e.g. due to cloud cover)
    combined = era5.addBands(no2).addBands(co).addBands(o3).addBands(aod).unmask(-9999)
    
    # Sample at points
    sampled = combined.sampleRegions(
        collection=points,
        scale=11132,
        properties=['id', 'lat', 'lon']
    )
    
    # Add date and convert units (handling potential nulls gracefully is done server-side)
    result = sampled.map(lambda f: f
        .set('date', date_str)
        .set('datetime_utc', ee.Date(date_str).format('YYYY-MM-dd HH:mm:ss'))
        .set('temperature_celsius', ee.Number(f.get('temperature_2m')).subtract(273.15))
        .set('dewpoint_celsius', ee.Number(f.get('dewpoint_temperature_2m')).subtract(273.15))
        .set('pressure_mb', ee.Number(f.get('surface_pressure')).divide(100))
        .set('wind_u', f.get('u_component_of_wind_10m'))
        .set('wind_v', f.get('v_component_of_wind_10m'))
        .set('NO2', f.get('NO2_column_number_density'))
        .set('CO', f.get('CO_column_number_density'))
        .set('O3', f.get('O3_column_number_density'))
        .set('AOD', f.get('Optical_Depth_055'))
    )

    # Calculate Relative Humidity using August-Roche-Magnus formula
    def calc_rh(f):
        t = ee.Number(f.get('temperature_celsius'))
        td = ee.Number(f.get('dewpoint_celsius'))
        # rh = 100 * exp((17.625 * td / (243.04 + td)) - (17.625 * t / (243.04 + t)))
        v_td = ee.Number(17.625).multiply(td).divide(ee.Number(243.04).add(td))
        v_t = ee.Number(17.625).multiply(t).divide(ee.Number(243.04).add(t))
        rh = ee.Number(100).multiply(v_td.subtract(v_t).exp())
        return f.set('relative_humidity', rh)

    result = result.map(calc_rh)
    
    try:
        info = result.getInfo()
    except Exception as e:
        print(f"GEE extraction failed (likely no data for date {date_str}): {e}")
        return None

    
    if not info or not info.get('features'):
        return None
        
    properties = info['features'][0]['properties']
    
    # Replace the -9999 unmask values with None (NaN)
    for k, v in properties.items():
        if v == -9999 or v == -9999.0:
            properties[k] = None

    if 'relative_humidity' not in properties:
        properties['relative_humidity'] = None
        
    return pd.DataFrame([properties])
