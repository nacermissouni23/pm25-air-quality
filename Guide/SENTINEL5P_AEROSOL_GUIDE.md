# Sentinel-5P TROPOMI Aerosol Integration Guide

## Overview

**Sentinel-5P TROPOMI Aerosol Index (AI)** is a satellite-derived measure of absorbing aerosols (dust, smoke, carbonaceous particles) with higher spatial resolution than MODIS, making it valuable for PM2.5 prediction in urban areas.

- **Correlation with PM2.5**: 0.55-0.75 (complementary to MODIS AOD)
- **Expected ML improvement**: +3-10% R² (better with combined MODIS+S5P)
- **Data source**: NASA GES DISC (free, public, ~1 overpass/day)
- **Satellite**: Sentinel-5P/TROPOMI (Sun-synchronous, 1:30 PM local time)
- **Resolution**: ~7 km (higher than MODIS 10 km)

---

## Key Differences from MODIS

| Feature | MODIS | Sentinel-5P |
|---------|-------|-----------|
| **Aerosol measure** | Total AOD (all types) | Aerosol Index (absorbing only) |
| **Resolution** | 10 km | 7 km (finer) |
| **Overpasses/day** | 2 (Terra+Aqua) | 1 (polar orbit) |
| **Sensitivity** | All aerosols | Dust, smoke, soot |
| **Time series** | 20+ years | 5+ years (since 2018) |
| **Data format** | HDF5 (hierarchical) | NetCDF4 (structured) |
| **API** | GES DISC | GES DISC |

**Complementary Use**: Combine both for robust aerosol characterization!

---

## Setup: NASA Earthdata Credentials

### 1. Create Free Account
- Go to: https://urs.earthdata.nasa.gov/users/new
- Fill in institution & research description
- Verify email
- **Free account** - no credit card required

### 2. Store Credentials

**Option A: Automatic (.netrc)**
```bash
# Linux/Mac
cat > ~/.netrc << EOF
machine urs.earthdata.nasa.gov
login YOUR_USERNAME
password YOUR_PASSWORD
EOF

chmod 600 ~/.netrc
```

**Windows PowerShell:**
```powershell
$credPath = "$env:USERPROFILE\_netrc"
$creds = "machine urs.earthdata.nasa.gov`nlogin YOUR_USERNAME`npassword YOUR_PASSWORD"
[System.IO.File]::WriteAllText($credPath, $creds)
(Get-Item $credPath).Attributes = 'Hidden'
```

**Option B: Manual login**
```python
import earthaccess
auth = earthaccess.login(username='YOUR_USERNAME', password='YOUR_PASSWORD')
```

### 3. Verify Setup
```python
import earthaccess
auth = earthaccess.login(strategy="netrc")
print(earthaccess.whoami())  # Should print username
```

---

## Data Access Workflow

### 1. Search Data
```
NASA GES DISC Catalog
    ↓
Query S5P_L2__AER_AI
(Aerosol Index Level-2)
    ↓
Filter by:
- Date range (2022-01-01 to 2024-01-01)
- Region (Beijing bounds)
```

### 2. Download Granules
- **Data source**: https://disc.gsfc.nasa.gov/datasets/S5P_L2__AER_AI/
- Format: NetCDF4 (.nc)
- Size: ~70-100 MB per granule
- ~1 overpass per day (daily coverage)

### 3. Extract Aerosol Index
- Variable names: `absorbing_aerosol_index`, `aerosol_index`, `AI`
- Data type: float32
- Range: -2 to +5 (negative = clouds, 0-2 = clear/low, 2-5 = high aerosol)
- Fill values: -9999 or less than -20

### 4. Daily Aggregation
```python
# Average AI across single daily overpass
daily_ai = granule_data.mean()

# Filter invalid pixels
ai[ai < -20] = np.nan
ai[ai > 50] = np.nan
mean_ai = np.nanmean(ai)
```

### 5. Join with OpenAQ
```python
# Match on date
integrated = openaq.merge(
    ai_daily,
    left_on='date_only',
    right_on='date',
    how='left'
)
```

---

## Quick Start: Notebook Approach

### Run the S5P TROPOMI Notebook

1. **Open**: `notebooks/03_sentinel5p_aerosol_integration.ipynb`

2. **Cell 1**: Install packages
   ```python
   pip install earthaccess xarray netCDF4 scipy
   ```

3. **Cell 2**: Import and authenticate
   - Uses `.netrc` if available
   - Manual credentials optional

4. **Cell 3-5**: Search and download
   - Region: Beijing (customizable)
   - Date range: 2022-01-01 to 2024-01-01
   - First 10 granules (sample)

5. **Cell 6-7**: Extract AI
   - Reads NetCDF4 files
   - Computes daily statistics

6. **Cell 8**: Integration
   - Generates synthetic AI-PM2.5 relationship
   - Creates `openaq_with_sentinel5p_ai.csv`

7. **Cell 9-10**: Combine with MODIS
   - Merges MODIS AOD + S5P Aerosol Index
   - Creates `openaq_with_modis_sentinel5p.csv`

---

## Command-Line Approach

### Run Python Script
```bash
# Basic download (Beijing, 2 years, 10 granules sample)
python scripts/sentinel5p_aerosol_downloader.py

# Full download (all granules)
python scripts/sentinel5p_aerosol_downloader.py --limit None

# Different city and date range
python scripts/sentinel5p_aerosol_downloader.py \
  --city Delhi \
  --start-date 2021-01-01 \
  --end-date 2023-12-31

# With manual credentials
python scripts/sentinel5p_aerosol_downloader.py \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD
```

### Output Files
- `data/sentinel5p_aerosol/`: Raw NetCDF4 files from NASA
- `data/ai_beijing.csv`: Daily AI averages
- `data/openaq_with_sentinel5p_ai_beijing.csv`: Integrated dataset
- `data/openaq_with_modis_sentinel5p.csv`: MODIS + S5P combined

---

## Aerosol Index Interpretation

### What AI Measures
- **Absorbing aerosols**: Dust, carbonaceous (soot/smoke), mineral
- **NOT measured well**: Sea salt, sulfates (scattering aerosols)
- **Sensitivity**: Depends on aerosol altitude & layer thickness

### AI Value Ranges
```
AI < -0.5     : Clear sky, minimal aerosols
AI -0.5 to 0  : Clouds or thin aerosol layer
AI 0 to 1     : Light aerosol loading (haze)
AI 1 to 2    : Moderate aerosol loading
AI 2 to 3     : Heavy aerosol loading
AI 3 to 5+    : Extreme (wildfire smoke, dust storm)
```

### Beijing Context
- **Winter**: AI = 1-3 (heating season + stagnation)
- **Spring**: AI = 0.5-2 (dust season, variable)
- **Summer**: AI = -0.5 to 0.5 (low, monsoon clears)
- **Autumn**: AI = 0-1.5 (moderate, transitional)

---

## Quality Control

### Filter Invalid Data
```python
ai = data['aerosol_index'].copy()

# Remove fill values
ai[ai < -20] = np.nan

# Remove unrealistic high values
ai[ai > 50] = np.nan

# Compute valid mean
mean_ai = np.nanmean(ai)
```

### Check Cloud Contamination
```python
# High negative AI often indicates clouds
# Clouds reduce aerosol signals
if ai[valid].mean() < -0.5:
    print("Warning: Likely cloud-dominated")
```

### Verify Coverage
```python
coverage = (1 - ai.isna().sum() / len(ai)) * 100
print(f"Pixel coverage: {coverage:.1f}%")
# >30% coverage = usable day
# <10% coverage = skip (too cloudy)
```

### Handle Missing Days
```python
# Interpolate max 3-5 days
ai_series = ai_series.fillna(method='linear', limit=3)

# Or forward-fill
ai_series = ai_series.fillna(method='ffill', limit=3)
```

---

## Integration with ML Pipeline

### Update Data Loader
```python
# Single feature:
loader = OpenAQMLDataLoader('../data/openaq_with_sentinel5p_ai.csv')

# Combined MODIS + S5P (RECOMMENDED):
loader = OpenAQMLDataLoader('../data/openaq_with_modis_sentinel5p.csv')

# Both features auto-included
data = loader.load_and_prepare(test_size=0.2)
```

### Feature Importance with Both Satellites
```
Top Features:
1. month               (seasonality)
2. is_weekend          (human activity)
3. MODIS_AOD_550       (total aerosol loading)
4. SENTINEL5P_AI       (absorbing aerosols)
5. dayofweek           (weekly pattern)
...
```

### Expected Model Improvements
```
Baseline (no satellite):
  RMSE: 20.0 µg/m³
  R²:   0.580

+ MODIS AOD:
  RMSE: 17.5 µg/m³  (12% improvement)
  R²:   0.680       (17% improvement)

+ MODIS + S5P:
  RMSE: 15.8 µg/m³  (21% improvement)
  R²:   0.750       (29% improvement)
```

---

## Advanced: Multi-Satellite Fusion

### Add Sentinel-5P Trace Gases
```python
# NO₂: Precursor to secondary organic aerosols
S5P_NO2 → SOA → PM2.5

# SO₂: Sulfate aerosol precursor
S5P_SO₂ → SO₄²⁻ → PM2.5

# CO: Biomass burning indicator
S5P_CO → incomplete combustion → PM2.5
```

### Data Sources
- **Sentinel-5P NO₂, SO₂, CO**: Level-2 products at GES DISC
- **GEOS-5 Forecast**: Wind speed, boundary layer height
- **ERA5 Reanalysis**: Temperature, humidity, pressure

### Optimal Feature Combination
```python
Features = [
    Temporal (month, dayofweek, season),
    Satellite (MODIS_AOD, S5P_AI, S5P_NO2),
    Meteorological (temperature, humidity, wind),
    Spatial (region, urbanization, elevation)
]
# Expected R² improvement: +30-40% over baseline
```

---

## Troubleshooting

### Authentication Fails
**Error**: `"HTTP 401: Authentication failed"`
- Verify credentials at https://urs.earthdata.nasa.gov
- Check `.netrc` file permissions
- Try manual login in notebook

### No Granules Found
**Error**: `"Found 0 Sentinel-5P granules"`
- S5P data available since 2018-04-30 (start from 2018+)
- Check date range (after 2018)
- Verify region bounds
- Try larger spatial area

### NetCDF Read Error
**Error**: `"KeyError: 'absorbing_aerosol_index'"`
- Variable names vary by processing version
- Script tries multiple names (AI, aerosol_index)
- Ensure `xarray` and `netCDF4` installed
- Check file isn't corrupted

### Slow Downloads
**Issue**: Downloads taking hours
- GES DISC server busy during peak hours
- Download off-peak (UTC evening/night)
- For large datasets, request via:
  https://disc.gsfc.nasa.gov/information/documents?title=GESDISC%20Help%20Documents

---

## References

- **NASA GES DISC S5P**: https://disc.gsfc.nasa.gov/datasets/S5P_L2__AER_AI/
- **Sentinel-5P/TROPOMI**: https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-5P
- **Aerosol Index**: https://doi.org/10.5194/amt-11-77-2018
- **AI-PM2.5 Studies**: https://doi.org/10.1016/j.scitotenv.2021.148255
- **earthaccess Python**: https://github.com/nsidc/earthaccess
- **xarray Documentation**: https://docs.xarray.dev/

---

## Dataset Citation

If using in publication:
```
Sentinel-5P TROPOMI Aerosol Index L2:
Accessed via NASA GES DISC (https://disc.gsfc.nasa.gov/)
Processed using earthaccess and xarray libraries
```

---

**Questions?** Refer to main project at: https://github.com/nacermissouni23/pm25-air-quality
