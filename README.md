# Air Quality Estimation from Satellite Data

Ground-level air quality monitors are sparse — most of the world has no reliable PM2.5 measurements at all. This project builds an end-to-end ML pipeline that estimates ground-level PM2.5 concentrations from satellite imagery, meteorological reanalysis data, and land use features, producing high-resolution air quality maps for regions without monitoring infrastructure.

**Output: predicted PM2.5 maps at 1km resolution with uncertainty estimates.**

---

## Pipeline overview

```
Satellite AOD          Meteorological data       Land use
(MODIS, Sentinel-5P)   (ERA5 reanalysis)         (OpenStreetMap)
        │                      │                      │
        └──────────────────────┴──────────────────────┘
                               │
                               ▼
                    Feature engineering
                    (temporal, spatial,
                     atmospheric features)
                               │
                               ▼
                     ML model training
                  (XGBoost / LightGBM / NN)
                               │
                               ▼
              Predicted PM2.5 at 1km resolution
                    + SHAP explanations
                    + uncertainty map
```

---

## Data sources

| Source | Data | Access |
|---|---|---|
| OpenAQ | Ground-truth PM2.5 measurements | openaq.org |
| MODIS (NASA LAADS DAAC) | Aerosol Optical Depth (AOD) | ladsweb.modaps.eosdis.nasa.gov |
| Sentinel-5P TROPOMI | Aerosol, NO₂ columns | Copernicus Open Access Hub |
| ERA5 (Copernicus CDS) | Wind speed/direction, humidity, boundary layer height | cds.climate.copernicus.eu |
| OpenStreetMap | Urban fraction, road density | openstreetmap.org |

---

## Features engineered

**Atmospheric:**
- AOD at 550nm (MODIS, Sentinel-5P)
- Planetary boundary layer height (ERA5)
- Wind speed and direction
- Relative humidity, temperature
- NO₂ column density

**Land use:**
- Urban fraction in 1km × 1km grid cell
- Road density (weighted by road type)
- Distance to nearest industrial zone

**Temporal:**
- Season, month, day of week
- Hour of day (for sub-daily data)
- Lag features (PM2.5 from previous day)

---

## Models

| Model | Notes |
|---|---|
| Linear Regression | Interpretable baseline |
| XGBoost | Primary model, handles non-linear feature interactions |
| LightGBM | Faster alternative, comparable accuracy |
| Neural Network | MLP with spatial embeddings |

---

## Results

| Model | R² | RMSE (µg/m³) |
|---|---|---|
| Linear Regression | ~0.55 | — |
| XGBoost | **~0.82** | — |
| LightGBM | ~0.80 | — |
| Neural Network | ~0.78 | — |

*(Evaluated with spatial cross-validation to avoid data leakage between nearby stations.)*

---

## Setup

```bash
git clone https://github.com/nacermissouni23/pm25-air-quality
cd pm25-air-quality
pip install -r requirements.txt
```

```bash
# Download and preprocess all data sources
python data/download.py --region north_africa --year 2023

# Run feature engineering
python features/build_features.py

# Train and evaluate all models
python train.py --compare-all

# Generate PM2.5 map
python predict.py --model xgboost --output maps/pm25_map.html
```

---

## Visualizations

- Interactive PM2.5 map (Folium)
- SHAP feature importance plots
- Model comparison tables and scatter plots
- Spatial cross-validation results
- Uncertainty / confidence map

---

## Stack

```
xarray / netCDF4        climate and satellite data handling
Geopandas / rasterio    geospatial operations, raster processing
scikit-learn            preprocessing, evaluation, baseline models
XGBoost / LightGBM      primary ML models
SHAP                    model explainability
Folium / Plotly         interactive visualization
```

---

## Deliverables

- [x] End-to-end notebook pipeline
- [x] Feature engineering documentation
- [x] Model comparison (tables + plots)
- [x] SHAP-based feature importance analysis
- [x] Predicted PM2.5 map
- [x] Validation report (R², RMSE, spatial cross-validation)
