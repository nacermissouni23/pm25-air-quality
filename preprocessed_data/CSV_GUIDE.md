# Preprocessed Data CSV Guide

This directory contains all preprocessed datasets and scaler objects ready for machine learning model training and evaluation. This guide explains each file and its purpose.

---

## Core Modeling Files (Feature-Target Split)

These files are the primary datasets you'll use for training, validation, and testing your models.

### **X_train.csv** (29,011 rows × 31 features)
- **Purpose:** Input features for training your model
- **Usage:** `model.fit(X_train, y_train)`
- **When to use:** 
  - Fit/train all models on this data
  - Use with TimeSeriesSplit for cross-validation
  - Calculate training error metrics
- **Note:** This is the only data the scalers were fit on (no data leakage)

### **y_train.csv** (29,011 rows)
- **Purpose:** Target variable (PM2.5 measurements) for training
- **Usage:** Paired with X_train for model fitting
- **Statistics:**
  - Mean: ~50 μg/m³ (varies by location/season)
  - Contains only valid PM2.5 values (≥ 0)
  - No missing values

### **X_val.csv** (4,144 rows × 31 features)
- **Purpose:** Input features for overfitting monitoring during development
- **Usage:** `val_predictions = model.predict(X_val)`
- **When to use:**
  - Monitor model performance DURING hyperparameter tuning
  - Track if validation error diverges from training error (sign of overfitting)
  - Early stopping if validation metric plateaus
- **Important:** Validation set comes temporally AFTER training data
- **Do NOT use for:** Final model evaluation (use test set instead)

### **y_val.csv** (4,144 rows)
- **Purpose:** Target variable for validation
- **Usage:** Compare predictions: `y_val_pred = model.predict(X_val); calculate_metrics(y_val, y_val_pred)`
- **When to use:** Calculate validation metrics (MSE, RMSE, MAE, R²) to monitor for overfitting

### **X_test.csv** (8,290 rows × 31 features)
- **Purpose:** Input features for final model evaluation (HELD OUT)
- **Usage:** `test_predictions = best_model.predict(X_test)`
- **When to use:** ONLY after model selection is complete
- **Critical:** Never use test data during training, hyperparameter tuning, or model selection
- **Important:** This represents future unseen data

### **y_test.csv** (8,290 rows)
- **Purpose:** Target variable for final evaluation
- **Usage:** Final performance assessment: `final_metrics = calculate_metrics(y_test, y_test_pred)`
- **When to use:** Report final model performance (only once, at the very end)
- **Note:** Test data is temporally AFTER both training and validation data

---

## Full Dataset Backup Files (Optional)

These files contain complete rows with all original columns, useful for post-analysis and interpretation.

### **train_preprocessed.csv** (29,011 rows × full columns)
- **Purpose:** Complete training data with all original features and metadata
- **Includes:** Date, location, sensor info, all engineered features, target
- **Usage:** 
  - Post-analysis: Temporal trends, geographic patterns
  - Feature importance interpretation
  - Debugging or understanding predictions
- **Do NOT use for:** Model training (use X_train/y_train instead)

### **val_preprocessed.csv** (4,144 rows × full columns)
- **Purpose:** Complete validation data with all columns
- **Usage:** Same as train_preprocessed.csv but for validation set

### **test_preprocessed.csv** (8,290 rows × full columns)
- **Purpose:** Complete test data with all columns
- **Usage:** Same as train_preprocessed.csv but for test set
- **Note:** Use sparingly; keep test set blind until final evaluation

---

## Scaler Objects (for Inference/Production)

These `.pkl` files contain fitted scaler objects for transforming new data during inference.

### **standard_scaler.pkl**
- **Purpose:** StandardScaler object fitted on training data
- **Features scaled:** `temperature_celsius`, `wind_u`, `wind_v`, `wind_magnitude`
- **Usage in production:**
  ```python
  import joblib
  standard_scaler = joblib.load('standard_scaler.pkl')
  new_data[standard_features] = standard_scaler.transform(new_data[standard_features])
  ```
- **Important:** Always use `.transform()` (not `.fit_transform()`) on new data

### **robust_scaler.pkl**
- **Purpose:** RobustScaler object fitted on training data
- **Features scaled:** Pollution features + interactions prone to outliers
  - `pressure_mb`, `NO2`, `CO`, `O3`, `AOD`
  - `pollution_index`, `aod_pollution_interaction`, etc.
- **Usage:** Same as standard_scaler.pkl
- **Why RobustScaler?** These features have sensor noise and pollution spikes; median/IQR approach is more robust than mean/std

### **scaling_config.pkl**
- **Purpose:** Configuration dictionary mapping features to scaler types
- **Contains:**
  ```python
  {
    'standard_scaler_features': [...],
    'robust_scaler_features': [...],
    'no_scale_features': [...]
  }
  ```
- **Usage:** Programmatically apply correct scaler to each feature group
  ```python
  config = joblib.load('scaling_config.pkl')
  for feature in config['standard_scaler_features']:
      new_data[feature] = standard_scaler.transform(new_data[[feature]])
  ```

---

## Data Split Timeline

The temporal ordering ensures no data leakage:

```
Timeline (Nov 2016 → Apr 2026)

[TRAINING] ─────────────────────── [VALIDATION] ── [TEST]
Nov 2016 - Feb 2023               Feb - Jun 2023   Jun 2023 - Apr 2026
29,011 samples                     4,144 samples    8,290 samples
(70%)                              (10%)            (20%)
```

**Key property:** Train → Val → Test in chronological order, no overlap

---

## Typical ML Workflow

### 1. **Hyperparameter Tuning & Model Selection**
```python
from sklearn.model_selection import TimeSeriesSplit

# Load training data
X_train = pd.read_csv('X_train.csv')
y_train = pd.read_csv('y_train.csv').squeeze()

# Cross-validate with TimeSeriesSplit (respects temporal order)
tscv = TimeSeriesSplit(n_splits=5)
for train_idx, val_idx in tscv.split(X_train):
    X_fold_train, X_fold_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
    y_fold_train, y_fold_val = y_train.iloc[train_idx], y_train.iloc[val_idx]
    
    # Train model
    model.fit(X_fold_train, y_fold_train)
    
    # Monitor validation performance
    val_pred = model.predict(X_fold_val)
    val_score = calculate_metrics(y_fold_val, val_pred)
```

### 2. **Monitor for Overfitting**
```python
# After training on full training set:
X_val = pd.read_csv('X_val.csv')
y_val = pd.read_csv('y_val.csv').squeeze()

train_pred = model.predict(X_train)
val_pred = model.predict(X_val)

train_error = mse(y_train, train_pred)
val_error = mse(y_val, val_pred)

gap = val_error - train_error
if gap > 0.05 * train_error:
    print("WARNING: Overfitting detected!")
```

### 3. **Final Evaluation (Only Once)**
```python
# ONLY after model selection is complete
X_test = pd.read_csv('X_test.csv')
y_test = pd.read_csv('y_test.csv').squeeze()

# Make predictions
test_pred = best_model.predict(X_test)

# Calculate final metrics
final_metrics = {
    'MSE': mse(y_test, test_pred),
    'RMSE': np.sqrt(mse(y_test, test_pred)),
    'MAE': mean_absolute_error(y_test, test_pred),
    'R2': r2_score(y_test, test_pred)
}

print("Final Test Set Performance:")
for metric, value in final_metrics.items():
    print(f"  {metric}: {value:.4f}")
```

### 4. **Production Inference**
```python
import joblib

# Load fitted scalers
standard_scaler = joblib.load('standard_scaler.pkl')
robust_scaler = joblib.load('robust_scaler.pkl')
config = joblib.load('scaling_config.pkl')

# Load best model
best_model = joblib.load('best_model.pkl')

# For new data:
def predict_pm25(new_data):
    # Scale using training scalers (do NOT refit)
    new_data[config['standard_scaler_features']] = standard_scaler.transform(
        new_data[config['standard_scaler_features']]
    )
    new_data[config['robust_scaler_features']] = robust_scaler.transform(
        new_data[config['robust_scaler_features']]
    )
    
    # Predict
    predictions = best_model.predict(new_data)
    return predictions
```

---

## Feature Information

### 31 Total Features (after scaling)

**Geographic (2, no scaling):**
- `latitude`, `longitude`

**Meteorological (4):**
- Scaled: `temperature_celsius`, `wind_u`, `wind_v`, `wind_magnitude`
- No scaling: (none)

**Pollution (4):**
- All scaled with RobustScaler: `NO2`, `CO`, `O3`, `AOD`

**Temporal (11, no scaling):**
- Categorical: `year`, `month`, `day`, `dayofweek`, `dayofyear`, `quarter`, `week`
- Cyclical: `month_sin`, `month_cos`, `dow_sin`, `dow_cos`

**Engineered (10):**
- Scaled: `pollution_index`, `aod_pollution_interaction`, `temp_pollution_interaction`, `pressure_pollution_interaction`
- No scaling: `wind_direction`, `temp_pressure_interaction`, `pm25_lag1`, `temp_lag1`, `pollution_lag1`

---

## Data Quality Summary

| Metric | Value |
|--------|-------|
| Original rows (merged) | 41,718 |
| Invalid PM25 removed | 273 |
| Final dataset | 41,445 |
| Missing values after preprocessing | 0 |
| Train/Val/Test split | 70% / 10% / 20% |
| Temporal overlap | NONE (proper causality) |
| Scalers fit on | Training data ONLY |
| Target range | 0.0 - ~500 μg/m³ |

---

## Common Issues & Solutions

### Issue: "Shape mismatch between X and y"
**Solution:** Make sure you're using consistent row counts:
```python
X_train = pd.read_csv('X_train.csv')
y_train = pd.read_csv('y_train.csv').squeeze()  # .squeeze() converts to Series
assert len(X_train) == len(y_train), "Mismatch!"
```

### Issue: "Scalers not available during inference"
**Solution:** Always save scalers after training:
```python
joblib.dump(standard_scaler, 'standard_scaler.pkl')
joblib.dump(robust_scaler, 'robust_scaler.pkl')
joblib.dump(scaling_config, 'scaling_config.pkl')
```

### Issue: "Getting different results when reusing test set"
**Cause:** Test set should NEVER be touched during model development
**Solution:** Keep strict separation:
- Training: X_train, y_train only
- Tuning: Use TimeSeriesSplit on training data
- Monitoring: X_val, y_val only
- Final eval: X_test, y_test (ONLY ONCE)

### Issue: "Overfitting detected"
**Solution:** 
- Use simpler model (fewer parameters)
- Increase regularization (L1/L2 penalty)
- Use dropout/early stopping
- Add more training data if possible
- Feature selection (remove redundant features)

---

## Next Steps

1. **Load data** using `pd.read_csv()`
2. **Train models** on X_train/y_train with TimeSeriesSplit
3. **Select best model** based on X_val/y_val performance
4. **Evaluate ONLY on X_test/y_test** for final metrics
5. **Save artifacts:**
   - Trained model: `joblib.dump(model, 'best_model.pkl')`
   - Scalers: Already saved in this folder
6. **Deploy:** Use scaler objects + model for production predictions

---

**Generated:** April 17, 2026  
**Preprocessing Version:** 7-Phase ML Pipeline with Temporal Split & Data Leakage Prevention
