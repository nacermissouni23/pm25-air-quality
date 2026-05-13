import pandas as pd
import numpy as np
import csv
import plotly.express as px
import plotly.graph_objects as go
import json
import joblib
import streamlit as st
import os


class Engine:
    def __init__(self):
        #loading the model
        self.model = joblib.load("models/xgb_model.pkl")
        # Ensure database directory exists
        os.makedirs("database", exist_ok=True)
        # Column schema shared by temp_data, predicted_data, and hist_data
        self.columns = [
            "date", "datetime_utc", "id", "latitude", "longitude",
            "temperature_celsius", "pressure_mb", "wind_u", "wind_v",
            "NO2", "CO", "O3", "AOD", "sensor_name",
            "building_density", "road_density_km", "industrial_presence",
            "green_space_fraction", "relative_humidity"
        ]
        # Start with an empty temp DataFrame (written to disk when data arrives)
        self.temp_data = pd.DataFrame(columns=self.columns)
        #initialize the history data file in /database
        hist_path = "database/hist_data.csv"
        if os.path.exists(hist_path):
            self.hist_data = pd.read_csv(hist_path)
        else:
            self.hist_data = pd.DataFrame(columns=self.columns)
            self.hist_data.to_csv(hist_path, index=False)
        #read the wilaya coordinates mapping from /database
        self.wilaya_coords = pd.read_csv("database/wilaya_coordinates.csv")
        # Start with an empty predicted DataFrame (includes Prediction column)
        self.predicted_data = pd.DataFrame(columns=self.columns + ["Prediction"])
        #load the GeoJSON for wilaya boundaries (used for choropleth map)
        with open("database/dz.json", "r", encoding="utf-8") as f:
            self.geojson = json.load(f)
        #load config.json still don't know if it's needed
        with open("database/config.json", "r") as f:
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
        features = self.data_extractor_helper(lat,lon,date)
        return features


    def data_extractor_helper(self,lat,lon,date):
        #To be implemented
        return None
    ################################################################################33333333
    
    def make_prediction(self,wilaya,date):
        #make the prediction
        temp_data = self.get_features(wilaya,date)
        if temp_data is None:
            return None
        prediction = self.model.predict(temp_data)
        self.predicted_data['Prediction'] = prediction
        self.predicted_data.to_csv("database/predicted_data.csv", index=False)
        #append the predicted data to the history data
        self.hist_data = pd.concat([self.hist_data, self.predicted_data], ignore_index=True)
        self.hist_data.to_csv("database/hist_data.csv", index=False)
        return self.predicted_data
        
    def get_from_predictions(self,wilaya,date):
        return self.predicted_data[(self.predicted_data['Wilaya'] == wilaya) & (self.predicted_data['Date'] == date)]

    def get_from_history(self,wilaya,date):
        return self.hist_data[(self.hist_data['Wilaya'] == wilaya) & (self.hist_data['Date'] == date)]


    def initialize_map(self, date, wilaya="All"):
        #make the predictions for the given date
        if wilaya == "All":
            target_wilayas = self.wilaya_coords['wilaya'].tolist()
        else:
            target_wilayas = [wilaya]

        for w in target_wilayas:
            self.make_prediction(w, date)
            
        #get the predictions for the given date
        if not self.predicted_data.empty and 'date' in self.predicted_data.columns:
            predictions_for_date = self.predicted_data[self.predicted_data['date'] == str(date)]
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
        
    
        
        