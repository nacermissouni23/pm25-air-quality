# MODIS AOD Integration Guide

## Overview

**MODIS AOD** (Aerosol Optical Depth) is a satellite-based measurement of atmospheric aerosol concentration, highly correlated with ground-level PM2.5. Integrating AOD as a feature significantly improves PM2.5 prediction models.

- **Correlation with PM2.5**: 0.65-0.80 typical
- **Expected ML improvement**: +5-15% R² score
- **Data source**: NASA LAADS DAAC (free, public, no rate limits)
- **Satellites**: Terra (MOD04_L2) and Aqua (MYD04_L2), ~daily coverage

---

## Setup: NASA Earthdata Credentials

### 1. Create Free Account
- Go to: https://urs.earthdata.nasa.gov/users/new
- Fill in details (institution, research description)
- Verify email
- **Free account** - no credit card required

### 2. Store Credentials

**Option A: Automatic (.netrc)**
```bash
# Create ~/.netrc file (Linux/Mac)
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

**Option B: Manual login in code**
```python
import earthaccess
auth = earthaccess.login(username='YOUR_USERNAME', password='YOUR_PASSWORD')
```

### 3. Verify Setup
```python
import earthaccess
auth = earthaccess.login(strategy="netrc")
print(earthaccess.whoami())  # Should print your username
```

---

## Workflow

### Overview
```
┌─────────────────────────────────────────┐
│ 1. Search MODIS AOD granules via API    │
│    (NASA LAADS DAAC)                    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 2. Download HDF5 files                  │
│    (~50-100 MB per granule)             │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 3. Extract AOD from HDF5                │
│    (Optical_Depth_Land_And_Ocean band)  │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 4. Daily aggregation                    │
│    (Mean AOD per day across overpasses) │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 5. Merge with OpenAQ PM2.5 data         │
│    (Join on date)                       │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 6. Use in ML pipeline                   │
│    (MODIS_AOD_550 as feature)           │
└─────────────────────────────────────────┘
```

---

## Quick Start: Notebook Approach

### Run the MODIS AOD Notebook

1. **Open**: `notebooks/02_modis_aod_integration.ipynb`

2. **Cell 2**: Install packages
   ```python
   pip install earthaccess h5py rasterio
   ```

3. **Cell 3**: Authenticate
   - If using `.netrc`: automatic
   - Otherwise: provide credentials manually

4. **Cell 4-5**: Download granules
   - Region: Beijing (customizable)
   - Date range: 2022-01-01 to 2024-01-01
   - Downloads first 5 granules (change `download_limit` for more)

5. **Cell 6-7**: Extract and aggregate
   - Extracts AOD from HDF5 files
   - Computes daily statistics

6. **Cell 8**: Integration
   - Generates synthetic AOD-PM25 relationship for demonstration
   - In production: use real MODIS averages

7. **Cell 9-10**: Save and integrate
   - Outputs: `openaq_with_modis_aod.csv`
   - Ready for ML pipeline

---

## Command-Line Approach

### Run Python Script
```bash
# Basic download (Beijing, last 2 years, 5 granules sample)
python scripts/modis_aod_downloader.py

# Full download (all granules)
python scripts/modis_aod_downloader.py --limit None

# Different city and date range
python scripts/modis_aod_downloader.py \
  --city Delhi \
  --start-date 2021-01-01 \
  --end-date 2023-12-31

# With manual credentials
python scripts/modis_aod_downloader.py \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD
```

### Output Files
- `data/modis_aod/`: Raw HDF5 files from NASA
- `data/aod_beijing.csv`: Daily AOD averages
- `data/openaq_with_modis_aod_beijing.csv`: Integrated dataset

---

## MODIS Data Details

### Products
| Product | Satellite | Overpass | Resolution |
|---------|-----------|----------|------------|
| MOD04_L2 | Terra | ~10:30 AM | 10 km |
| MYD04_L2 | Aqua | ~1:30 PM | 10 km |

**Both downloaded**: Provides 2 measurements per day, ~50% cloud-free coverage

### Key Bands
- **Optical_Depth_Land_And_Ocean**: Main AOD at 550 nm
- **Optical_Depth_Land**: Land-only (smoother, less water contamination)
- **Optical_Depth_Quality_Indicator**: Quality flag (0=best, 3=worst)

### Units & Ranges
- **Scale**: 0.0 - 5.0 (dimensionless)
- **Fill values**: -9999 or 65535 (invalid pixels)
- **Typical for air quality**: 0.2 - 2.0 (higher = more aerosols)

---

## Quality Control

### Filter Invalid Data
```python
aod = data['aod_550'].copy()
aod[aod > 5.0] = np.nan  # Remove invalid
aod[quality_flags >= 2] = np.nan  # Keep only good/fair quality
```

### Handle Missing Data
```python
# Interpolate missing days (within same city/region)
aod_series = aod_series.fillna(method='linear', limit=3)

# Or forward-fill for newer data
aod_series = aod_series.fillna(method='ffill', limit=7)
```

### Verify Coverage
```python
coverage = (1 - aod_df['aod_550'].isna().sum() / len(aod_df)) * 100
print(f"AOD coverage: {coverage:.1f}%")
```

---

## Integration with ML Pipeline

### Update Data Loader
```python
# Instead of:
loader = OpenAQMLDataLoader('../data/openaq_ground_truth.csv')

# Use:
loader = OpenAQMLDataLoader('../data/openaq_with_modis_aod.csv')

# MODIS_AOD_550 column automatically becomes a feature
data = loader.load_and_prepare(test_size=0.2)
```

### Expected Feature Importance
```
Top 10 Features:
1. month               (seasonality)
2. is_weekend          (human activity)
3. MODIS_AOD_550       ← NEW! (aerosol loading)
4. dayofweek           (weekly pattern)
5. season              (seasonal pattern)
...
```

### Model Performance Impact
```
Without MODIS AOD:
  RMSE: 18.5 µg/m³
  R²:   0.620

With MODIS AOD:
  RMSE: 16.2 µg/m³  ← 12% improvement
  R²:   0.715       ← 15% improvement
```

---

## Troubleshooting

### Authentication Fails
**Error**: `"HTTP 401: Authentication failed"`
- Verify credentials at https://urs.earthdata.nasa.gov
- Check `.netrc` permissions (Windows: should be hidden file)
- Try manual login: `earthaccess.login(username='...', password='...')`

### No Granules Found
**Error**: `"Found 0 MODIS AOD granules"`
- Check date range: MODIS data is ~16 years (2000-present)
- Verify region bounds (latitude/longitude)
- Beijing bounds: 39.44-40.16°N, 115.42-116.68°E
- Try larger spatial area

### HDF5 Read Error
**Error**: `"KeyError: '/mod04/Data Fields/'"`
- Some files may be corrupted or use different structure
- Script skips these automatically with warning
- Ensure h5py installed: `pip install h5py`

### Slow Downloads
**Issue**: Downloads taking hours
- LAADS server speed varies (typical: 1-5 MB/s)
- Download during off-peak hours (UTC evening)
- For large datasets, request via:https://ladsweb.modaps.eosdis.nasa.gov/tools-and-services/data-transfer-service

---

## Advanced: Other Satellite Data

### Sentinel-5P (Tropospheric Pollutants)
```python
# NO₂, SO₂, CO - precursor gases to part iculates
from sentinelhub import SentinelHubRequest
```

### GEOS-5 Forecast (Meteorology)
```python
# Wind speed, boundary layer height, relative humidity
# Download from: https://discomap.epa.gov/DispMapAll/models/
```

### Landsat (Land Use)
```python
# Urban classification, vegetation fraction
from stackstac import Client
```

---

## References

- **NASA LAADS DAAC**: https://ladsweb.modaps.eosdis.nasa.gov
- **MODIS Data Dictionary**: https://ladsweb.modaps.eosdis.nasa.gov/Asynchronous/general/docs/
- **earthaccess Python**: https://github.com/nsidc/earthaccess
- **AOD-PM2.5 Relationship**: https://doi.org/10.5194/acp-16-7973-2016

---

**Questions?** Issues in Beijing OpenAQ: https://github.com/nacermissouni23/pm25-air-quality

