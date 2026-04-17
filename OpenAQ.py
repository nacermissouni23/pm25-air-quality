import requests
import pandas as pd
from datetime import datetime, timedelta
import settings

API_KEY = settings.API_KEY

BASE_URL = "https://api.openaq.org/v3"

date_from = (datetime.now() - timedelta(days=1800)).isoformat()

# List of coordinates to fetch data for
LOCATIONS = [
    (36.1706, -5.3976, "Casablanca"),
    (36.7571, -4.5753, "Rabat"),
    (36.8422, -2.4612, "Tanger"),
    (37.16565, -3.60008, "Granada"),
    (37.60308, -0.97538, "Málaga"),
    (37.6936, -1.06464, "Motril"),
    (37.99359, -1.14472, "Vera"),
    (37.99102, -0.69008, "Mojacar"),
    (38.6394, -0.87238, "Almería"),
    (39.4776, -0.414, "Benidorm"),
    (39.7087, -0.2781, "Valencia"),
    (39.9986, -0.0731, "Castellón"),
    (39.769, 3.29, "Palma"),
    (40.00921, 3.8562, "Barcelona"),
    (39.26097, 9.13651, "Palermo"),
    (41.474, 2.0948, "Girona"),
    (41.11609, 1.19202, "Tarragona"),
    (43.41652, 5.22228, "Marseille"),
    (43.56248, 7.00722, "Antibes"),
    (42.67133, 9.43451, "Corsica"),
    (34.28899, 8.7616, "Tunis"),
    (35.28204, -2.94925, "Melilla"),
    (31.8747, -7.8907, "Laayoune"),
    (36.75649, 3.03772, "Algiers"),
]

for lat, lon, region_name in LOCATIONS:
    print(f"\n--- Fetching data for {region_name} ({lat}, {lon}) ---")
    
    response = requests.get(
        f"{BASE_URL}/locations",
        headers={"X-API-Key": API_KEY},
        params={
            "parameters_id": 2,  # PM2.5
            "coordinates": f"{lat},{lon}",  # latitude,longitude
            "radius": 25000,  # 25km max
            "limit": 100
        }
    )

    data = response.json()
    sensors = data.get("results", [])
    
    print(f"Found {len(sensors)} PM2.5 sensors within 25km")
    
    all_data = []
    
    for location in sensors:
        for sensor in location["sensors"]:
            if sensor["parameter"]["id"] == 2:
                sensor_id = sensor["id"]
                
                # Debug: Check if sensor has data
                url = f"{BASE_URL}/sensors/{sensor_id}/measurements"
                resp = requests.get(
                    url, 
                    headers={"X-API-Key": API_KEY}, 
                    params={"limit": 1, "date_from": date_from}
                )
                
                if resp.json().get("results"):
                    print(f"✅ Sensor {sensor_id} has data")
                    
                    # Get up to 50000 records per sensor
                    page = 1
                    records_per_sensor = 0
                    max_records_per_sensor = 50000
                    while records_per_sensor < max_records_per_sensor:
                        resp = requests.get(
                            url,
                            headers={"X-API-Key": API_KEY},
                            params={"limit": 1000, "page": page, "date_from": date_from}
                        )
                        data = resp.json()
                        results = data.get("results", [])
                        
                        if not results:
                            break

                        # # Debug: Print first measurement keys
                        # for m in results[:1]:
                        #     print(m.keys())  # See what fields exist
                        #     print (m['period'].keys())  # See what fields exist in period
                            
                        for m in results:
                            if records_per_sensor >= max_records_per_sensor:
                                break
                            all_data.append({
                                "sensor_name": location["name"],
                                "latitude": location["coordinates"]["latitude"],
                                "longitude": location["coordinates"]["longitude"],
                                "timestamp": m["period"]["datetimeFrom"],
                                "pm25": m["value"]
                            })
                            records_per_sensor += 1
                        
                        if records_per_sensor >= max_records_per_sensor:
                            break
                        page += 1
                else:
                    print(f"❌ Sensor {sensor_id} has NO data")
    
    # Save to CSV for this region
    if all_data:
        df = pd.DataFrame(all_data)
        filename = f"{region_name.replace(' ', '_')}.csv"
        df.to_csv(filename, index=False)
        print(f"✅ Saved {len(all_data)} records to {filename}")
    else:
        print(f"❌ No data collected for {region_name}")

print("\n✅ All regions processed!")



# Concatenate all regional CSVs into one final dataset
print("\n--- Concatenating all regions into final dataset ---")
import glob

all_files = glob.glob("*.csv")
# Filter to only region CSVs (exclude ones with numbers in name like pm25_recent_XXX.csv)
region_csvs = [f for f in all_files if any(region.replace(" ", "_") in f for lat, lon, region in LOCATIONS)]

final_data = []
for csv_file in region_csvs:
    try:
        df = pd.read_csv(csv_file)
        final_data.append(df)
        print(f"✅ Loaded {len(df)} records from {csv_file}")
    except Exception as e:
        print(f"❌ Error loading {csv_file}: {e}")

if final_data:
    combined_df = pd.concat(final_data, ignore_index=True)
    print(f"\nTotal hourly records: {len(combined_df)}")
    
    # Aggregate hourly to daily (mean PM2.5 per date per location)
    import ast
    combined_df['timestamp'] = combined_df['timestamp'].apply(ast.literal_eval)
    combined_df['date'] = pd.to_datetime(combined_df['timestamp'].apply(lambda x: x['utc'])).dt.date
    daily_df = combined_df.groupby(['date', 'latitude', 'longitude']).agg({
        'pm25': 'mean',
        'sensor_name': 'first'
    }).reset_index()
    
    print(f"Total daily records after aggregation: {len(daily_df)}")
    
    daily_df.to_csv("pm25_1800days.csv", index=False)
    print(f"✅ Saved {len(daily_df)} daily records to pm25_1800days.csv")
else:
    print("❌ No regional data to concatenate")