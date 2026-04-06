# PM2.5 Data Loading - Single Unified Method

## Quick Start (< 5 minutes)

### Option 1: Using the Python Module (Recommended for scripts)

```python
from openaq_loader import quick_load

# One-liner to load everything
X_train, y_train, X_test, y_test, features = quick_load()

# Now train any ML model
from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor(n_estimators=100)
model.fit(X_train, y_train)
score = model.score(X_test, y_test)
print(f"R² Score: {score:.4f}")
```

### Option 2: Using the Notebook (ML_DataLoader.ipynb)

Simply run the cells in order. First cell loads everything:

```python
loader = OpenAQMLDataLoader('openaq_ground_truth.csv')
data = loader.load_and_prepare(test_size=0.2)

X_train = data['X_train']
y_train = data['y_train']
X_test = data['X_test']
y_test = data['y_test']
```

---

## What This Does

**Single unified method that handles all preprocessing:**

```
CSV Data
   ↓
Load        → Read openaq_ground_truth.csv
   ↓
Clean       → Remove duplicates, handle null values, validate types
   ↓
Features    → Temporal (year, month, dayofweek, season)
            → Spatial (region encoding)
            → Transformations (log, AQI category)
   ↓
Split       → Train/test split (80/20 or custom)
   ↓
Arrays      → Numpy arrays ready for ML models
```

---

## Example: Complete ML Workflow

```python
# 1. Load data (one line!)
from openaq_loader import quick_load
X_train, y_train, X_test, y_test, features = quick_load()

# 2. Train model
from sklearn.ensemble import GradientBoostingRegressor
model = GradientBoostingRegressor(n_estimators=100, max_depth=6)
model.fit(X_train, y_train)

# 3. Evaluate
from sklearn.metrics import mean_squared_error, r2_score
y_pred = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print(f"RMSE: {rmse:.2f} µg/m³")
print(f"R²:   {r2:.4f}")
```

---

## API Reference

### Full Class Usage

```python
from openaq_loader import OpenAQMLDataLoader

loader = OpenAQMLDataLoader(csv_file='openaq_ground_truth.csv')

# Load and prepare all in one call
data = loader.load_and_prepare(test_size=0.2)

# Access individual components
X_train = data['X_train']         # (n_samples, n_features)
y_train = data['y_train']         # (n_samples,)
X_test = data['X_test']           # (n_test, n_features)
y_test = data['y_test']           # (n_test,)
feature_names = data['feature_names']  # List of feature column names
train_df = data['train_df']        # Full DataFrame with all data
test_df = data['test_df']          # Test DataFrame

# Get summary
print(loader.get_summary())

# Save feature names for later
loader.save_artifacts(prefix='pm25_')
```

### Quick One-Liner

```python
from openaq_loader import quick_load

X_train, y_train, X_test, y_test, features = quick_load(
    csv_file='openaq_ground_truth.csv',
    test_size=0.2
)
```

---

## Features Automatically Created

### Temporal Features
- `year` - Year of measurement
- `month` - Month (1-12)
- `day` - Day of month
- `dayofweek` - Day of week (0=Monday, 6=Sunday)
- `quarter` - Quarter (1-4)
- `is_weekend` - Binary: weekend or weekday
- `season` - Season (0=Winter, 1=Spring, 2=Summer, 3=Fall)

### Spatial Features
- `region_*` - One-hot encoded regions (e.g., region_Beijing, region_Delhi)

### Target Features
- `value_log` - Log-transformed PM2.5 for models that benefit from it
- `aqi_category` - Categorical classification (0-5) based on EPA standards

---

## Compatible ML Frameworks

Works seamlessly with any framework:

```python
# Scikit-learn
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.svm import SVR

# XGBoost
from xgboost import XGBRegressor
model = XGBRegressor(n_estimators=100)
model.fit(X_train, y_train)

# LightGBM
from lightgbm import LGBMRegressor
model = LGBMRegressor(n_estimators=100)
model.fit(X_train, y_train)

# TensorFlow/Keras
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

from tensorflow import keras
model = keras.Sequential([
    keras.layers.Dense(128, activation='relu'),
    keras.layers.Dense(64, activation='relu'),
    keras.layers.Dense(1)
])
model.fit(X_train_scaled, y_train, epochs=50, batch_size=32)

# PyTorch
import torch
X_train_tensor = torch.FloatTensor(X_train)
y_train_tensor = torch.FloatTensor(y_train)
# ... define model and training loop
```

---

## Required Data File

**File:** `openaq_ground_truth.csv`

Create this file using the OpenAQ API:

```python
from openaq import OpenAQ
import pandas as pd

api = OpenAQ()

# Fetch from multiple regions
all_data = []
for city in ['Beijing', 'New Delhi', 'Los Angeles', 'London', 'Tokyo', 'Cairo']:
    df = api.measurements(city=city, parameter='pm25', df=True, limit=5000)
    all_data.append(df)

# Combine and save
combined = pd.concat(all_data, ignore_index=True)
combined.to_csv('openaq_ground_truth.csv', index=False)
```

Or download from: https://explore.openaq.org/getting-started

---

## Troubleshooting

**Q: "CSV file not found" error**
```python
# Make sure openaq_ground_truth.csv exists in current directory
# Or specify full path:
loader = OpenAQMLDataLoader('/path/to/openaq_ground_truth.csv')
```

**Q: How to get the feature names for inference?**
```python
# Access from data dictionary
feature_names = data['feature_names']
# Or from loader object
feature_names = loader.feature_names
# Use for preprocessing new data with same features
```

**Q: How to save the feature names for production?**
```python
loader.save_artifacts(prefix='pm25_')
# Creates: pm25_feature_names.json
```

**Q: How to use with different test size?**
```python
data = loader.load_and_prepare(test_size=0.15)  # 15% test instead of 20%
```

---

## Summary

**Single unified method** for all data loading needs:

1. ✓ **One Python module**: `openaq_loader.py`
2. ✓ **Two usage patterns**:
   - Quick: `quick_load()` for scripts
   - Full: `OpenAQMLDataLoader` class for fine control
3. ✓ **All preprocessing included**: clean, engineer, split, prepare
4. ✓ **Ready for any ML framework**: scikit-learn, XGBoost, TensorFlow, etc.

**Start training models in minutes!**
