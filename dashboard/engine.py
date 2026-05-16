import pandas as pd
import numpy as np
import csv
import plotly.express as px
import plotly.graph_objects as go
import json
import joblib
import streamlit as st
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import GEE
import OSM



class Engine:
    def __init__(self):
        # Determine the absolute path to the dashboard directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.model_path = os.path.join(current_dir, "models", "xgb_model.pkl")
        self.database_dir = os.path.join(current_dir, "database")
        self.hist_path = os.path.join(self.database_dir, "hist_data.csv")
        self.wilaya_coords_path = os.path.join(self.database_dir, "wilaya_coordinates.csv")
        self.geojson_path = os.path.join(self.database_dir, "dz.json")
        self.config_path = os.path.join(self.database_dir, "config.json")
        self.predicted_data_path = os.path.join(self.database_dir, "predicted_data.csv")

        #loading the model
        self.model = joblib.load(self.model_path)
        # Ensure database directory exists
        os.makedirs(self.database_dir, exist_ok=True)

        # Column schema shared by temp_data, predicted_data, and hist_data
        self.columns = [
            "date", "datetime_utc", "id", "latitude", "longitude",
            "temperature_celsius", "pressure_mb", "wind_u", "wind_v",
            "NO2", "CO", "O3", "AOD", "sensor_name",
            "building_density", "road_density_km", "industrial_presence",
            "green_space_fraction", "relative_humidity", "wilaya"
        ]
        # Start with an empty temp DataFrame (written to disk when data arrives)
        self.temp_data = pd.DataFrame(columns=self.columns)
        
        #initialize the history data file in /database
        if os.path.exists(self.hist_path):
            self.hist_data = pd.read_csv(self.hist_path)
        else:
            self.hist_data = pd.DataFrame(columns=self.columns)
            self.hist_data.to_csv(self.hist_path, index=False)
            
        #read the wilaya coordinates mapping from /database
        self.wilaya_coords = pd.read_csv(self.wilaya_coords_path)
        # Start with an empty predicted DataFrame (includes Prediction column)
        self.predicted_data = pd.DataFrame(columns=self.columns + ["Prediction"])
        #load the GeoJSON for wilaya boundaries (used for choropleth map)
        with open(self.geojson_path, "r", encoding="utf-8") as f:
            self.geojson = json.load(f)
        #load config.json
        with open(self.config_path, "r") as f:
            self.config = json.load(f)
        self.low_range = self.config['low_range']
        self.medium_range = self.config['medium_range']
        self.high_range = self.config['high_range']

    # Helper functions
    def get_coordinates(self, wilaya):
        #get the coordinates of the wilaya from the wilaya_coords dataframe
        return self.wilaya_coords[self.wilaya_coords['wilaya'] == wilaya][['latitude', 'longitude']].values[0]
    #################################################################################333
    def get_features(self, wilaya,date):
        #use the get_coordinate function to get the coordinates
        #Logic to use api's to get the data 
        #add everything into temp_data and save it to csv
        coords = self.get_coordinates(wilaya)
        lat = coords[0]
        lon = coords[1]
        features = self.data_extractor_helper(lat,lon,date, wilaya)
        return features


    def data_extractor_helper(self,lat,lon,date, wilaya):
        '''
        Calls GEE and OSM APIs to retrieve the features for the given latitude, longitude, and date.
        Returns a DataFrame with the features ready for prediction.
        '''
        GEE_features = self.get_GEE_features(lat, lon, date)
        OSM_features = self.get_OSM_features(lat, lon)

        if GEE_features is not None and OSM_features is not None:
            features = pd.concat([GEE_features, OSM_features], axis=1)
            features['latitude'] = lat
            features['longitude'] = lon
            features['date'] = date
            features['wilaya'] = wilaya
            features['sensor_name'] = "Unknown"
            features['id'] = 1
            # Add wilaya to columns if not present
            cols = self.columns + (['wilaya'] if 'wilaya' not in self.columns else [])
            return features[cols]  # Ensure the order of columns matches the model's expectations
        return None
    
    def get_GEE_features(self, lat, lon, date):
        return GEE.extract_features(lat, lon, str(date))
    
    def get_OSM_features(self, lat, lon):
        return OSM.extract_features(lat, lon, radius=2000)
    ################################################################################33333333
    
    def make_prediction(self,wilaya,date):
        past = self.get_from_history(wilaya, str(date))
        if not past.empty: return past

        predictions = self.get_from_predictions(wilaya, str(date))
        if not predictions.empty: return predictions

        #make the prediction
        temp_data = self.get_features(wilaya,date)
        if temp_data is None:
            return None
            
        # Extract only the numerical features expected by the model in the correct order
        model_features = [
            'latitude', 'longitude', 'temperature_celsius', 'pressure_mb', 'wind_u',
            'wind_v', 'NO2', 'CO', 'O3', 'AOD', 'building_density', 'road_density_km',
            'industrial_presence', 'green_space_fraction', 'relative_humidity'
        ]
        
        # Filter and force cast all columns to floats (turns None/objects into np.nan natively for XGBoost)
        features_for_pred = temp_data[model_features].apply(pd.to_numeric, errors='coerce').astype(float)
        
        prediction = self.model.predict(features_for_pred)
        
        temp_data['Prediction'] = prediction
        
        if self.predicted_data.empty or self.predicted_data.dropna(how='all', axis=1).empty:
            self.predicted_data = temp_data.copy()
        else:
            self.predicted_data = pd.concat([self.predicted_data, temp_data], ignore_index=True)
        self.predicted_data.to_csv(self.predicted_data_path, index=False)

        #append the predicted data to the history data
        if self.hist_data.empty or self.hist_data.dropna(how='all', axis=1).empty:
            self.hist_data = temp_data.copy()
        else:
            self.hist_data = pd.concat([self.hist_data, temp_data], ignore_index=True).drop_duplicates(subset=["wilaya", "date"], keep="last")
        self.hist_data.to_csv(self.hist_path, index=False)
        return temp_data


        
    def get_from_predictions(self,wilaya,date):
        if self.predicted_data.empty or 'wilaya' not in self.predicted_data.columns: return pd.DataFrame()
        return self.predicted_data[(self.predicted_data['wilaya'] == wilaya) & (self.predicted_data['date'] == date)]

    def get_from_history(self,wilaya,date):
        if self.hist_data.empty or 'wilaya' not in self.hist_data.columns: return pd.DataFrame()
        return self.hist_data[(self.hist_data['wilaya'] == wilaya) & (self.hist_data['date'] == str(date))]


    def initialize_map(self, date, wilaya="All"):
        #make the predictions for the given date
        if wilaya == "All":
            target_wilayas = self.wilaya_coords['wilaya'].tolist()
        else:
            target_wilayas = [wilaya]

        for w in target_wilayas:
            prediction_result = self.make_prediction(w, date)
            if prediction_result is None:
                raise Exception(f"Satellite data is not yet available for {date}. Please select an older date.")
            
        #get the predictions for the given date from both history and new predictions
        historical_matches = self.hist_data[self.hist_data['date'] == str(date)] if not self.hist_data.empty and 'date' in self.hist_data.columns else pd.DataFrame()
        predicted_matches = self.predicted_data[self.predicted_data['date'] == str(date)] if not self.predicted_data.empty and 'date' in self.predicted_data.columns else pd.DataFrame()
        
        if not historical_matches.empty or not predicted_matches.empty:
            predictions_for_date = pd.concat([historical_matches, predicted_matches]).drop_duplicates(subset=["wilaya", "date"], keep="last")
        else:
            predictions_for_date = pd.DataFrame()
        
        # Merge coordinates with the predictions
        if not predictions_for_date.empty and 'wilaya' in predictions_for_date.columns:
            map_data = pd.merge(self.wilaya_coords, predictions_for_date, on='wilaya', how='inner')
        else:
            # Fallback if predicted_data isn't fully structured yet
            if wilaya == "All":
                map_data = self.wilaya_coords.copy()
            else:
                map_data = self.wilaya_coords[self.wilaya_coords['wilaya'] == wilaya].copy()
            map_data['Prediction'] = 0 

        # Determine zoom and center based on selection
        if wilaya != "All" and wilaya in self.wilaya_coords['wilaya'].values:
            coords = self.get_coordinates(wilaya)
            center = {"lat": float(coords[0]), "lon": float(coords[1])}
            zoom = 7
        else:
            center = {"lat": 28.0339, "lon": 1.6596}  # Approximate center of Algeria
            zoom = 4

        #create a choropleth map that colors the full surface of each wilaya
        #using the GeoJSON boundaries from dz.json
        fig = px.choropleth_mapbox(
            map_data,
            geojson=self.geojson,
            locations='wilaya',                     # column in map_data to match
            featureidkey='properties.name',          # key in GeoJSON to match
            color='Prediction',
            color_continuous_scale='YlOrRd',
            range_color=(0, map_data['Prediction'].max() if map_data['Prediction'].max() > 0 else 50),
            hover_name='wilaya',
            hover_data={'latitude': True, 'longitude': True, 'Prediction': ':.2f'},
            zoom=zoom,
            center=center,
            opacity=0.7,
            title=f'Algeria PM2.5 Predictions for {date}' if wilaya == "All" else f'{wilaya} PM2.5 Prediction for {date}',
            labels={'Prediction': 'PM2.5 (µg/m³)'}
        )
        
        fig.update_layout(
            mapbox_style="carto-positron",
            margin={"r": 0, "t": 40, "l": 0, "b": 0},
            height=700
        )
        
        return fig
    
    #Helper functions
    #function for the wilayas dropdown in the dashboard
    def get_wilayas(self):
        return self.wilaya_coords['wilaya'].tolist()
        
    
        
        