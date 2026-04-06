"""
OpenAQ ML Data Loader

Single unified method to load, clean, engineer features, and prepare PM2.5 data for ML.

Usage:
    from openaq_loader import OpenAQMLDataLoader
    
    loader = OpenAQMLDataLoader('openaq_ground_truth.csv')
    data = loader.load_and_prepare(test_size=0.2)
    
    X_train = data['X_train']
    y_train = data['y_train']
    X_test = data['X_test']
    y_test = data['y_test']
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Optional, List
import json


class OpenAQMLDataLoader:
    """Single unified loader for PM2.5 ground-truth data preparation."""
    
    def __init__(self, csv_file: str = 'openaq_ground_truth.csv'):
        """
        Initialize loader with CSV file path.
        
        Args:
            csv_file: Path to OpenAQ measurements CSV file
        """
        self.csv_file = csv_file
        self.df = None
        self.X_train = None
        self.y_train = None
        self.X_test = None
        self.y_test = None
        self.feature_names = None
        self.train_df = None
        self.test_df = None
    
    def load_and_prepare(self, test_size: float = 0.2) -> Dict:
        """
        Load data, clean, engineer features, and create train/test split.
        
        All-in-one method that handles:
        1. Loading CSV file
        2. Data cleaning and validation
        3. Feature engineering (temporal, spatial)
        4. Train/test split
        5. Creating numpy arrays for ML
        
        Args:
            test_size: Fraction of data for testing (default: 0.2)
            
        Returns:
            Dictionary containing:
                - X_train, y_train: Training data
                - X_test, y_test: Test data
                - feature_names: List of feature column names
                - train_df, test_df: Full DataFrames
        """
        self._load()
        self._clean()
        self._engineer_features()
        self._train_test_split(test_size)
        self._create_feature_matrices()
        
        return self.get_data()
    
    def _load(self) -> None:
        """Load CSV file."""
        if not Path(self.csv_file).exists():
            raise FileNotFoundError(
                f"CSV file not found: {self.csv_file}\n\n"
                f"Solution 1: Fetch data from OpenAQ API:\n"
                f"  from openaq import OpenAQ\n"
                f"  api = OpenAQ()\n"
                f"  cities = ['Beijing', 'Delhi', 'London']\n"
                f"  for city in cities:\n"
                f"    df = api.measurements(city=city, parameter='pm25', df=True)\n"
                f"    df.to_csv('{self.csv_file}', mode='a')\n\n"
                f"Solution 2: Download from explore.openaq.org"
            )
        
        self.df = pd.read_csv(self.csv_file)
    
    def _clean(self) -> None:
        """Clean and validate data."""
        # Remove duplicates
        self.df = self.df.drop_duplicates()
        
        # Ensure value is numeric
        if 'value' in self.df.columns:
            self.df['value'] = pd.to_numeric(self.df['value'], errors='coerce')
        
        # Remove null values
        self.df = self.df.dropna(subset=['value'])
        
        # Convert date to datetime
        if 'date' in self.df.columns:
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
    
    def _engineer_features(self) -> None:
        """Create ML-ready features."""
        # ========== TEMPORAL FEATURES ==========
        if 'date' in self.df.columns:
            self.df['year'] = self.df['date'].dt.year
            self.df['month'] = self.df['date'].dt.month
            self.df['day'] = self.df['date'].dt.day
            self.df['dayofweek'] = self.df['date'].dt.dayofweek  # 0=Mon, 6=Sun
            self.df['quarter'] = self.df['date'].dt.quarter
            self.df['is_weekend'] = self.df['dayofweek'].isin([5, 6]).astype(int)
            
            # Season: 0=Winter, 1=Spring, 2=Summer, 3=Fall
            seasons = [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 0]
            self.df['season'] = self.df['month'].map(lambda x: seasons[x-1])
        
        # ========== SPATIAL FEATURES ==========
        if 'region' in self.df.columns:
            region_dummies = pd.get_dummies(self.df['region'], prefix='region')
            self.df = pd.concat([self.df, region_dummies], axis=1)
        
        # ========== TARGET TRANSFORMATIONS ==========
        self.df['value_log'] = np.log1p(self.df['value'])  # Log transform
        
        # AQI Category (0-5 classification)
        def categorize_aqi(value):
            """Categorize PM2.5 using US EPA standards."""
            if value <= 12:
                return 0  # Good
            elif value <= 35.4:
                return 1  # Moderate
            elif value <= 55.4:
                return 2  # Unhealthy for Sensitive Groups
            elif value <= 150.4:
                return 3  # Unhealthy
            elif value <= 250.4:
                return 4  # Very Unhealthy
            else:
                return 5  # Hazardous
        
        self.df['aqi_category'] = self.df['value'].apply(categorize_aqi)
    
    def _train_test_split(self, test_size: float) -> None:
        """Create stratified train/test split."""
        mask = np.random.rand(len(self.df)) < (1 - test_size)
        self.train_df = self.df[mask].reset_index(drop=True)
        self.test_df = self.df[~mask].reset_index(drop=True)
    
    def _create_feature_matrices(self) -> None:
        """Create numpy arrays for ML models."""
        # Columns to exclude from feature matrix
        exclude_cols = {
            # Target variables
            'value', 'aqi_category', 'value_log',
            # Identifiers
            'date', 'location', 'city', 'country', 'region',
            # Metadata
            'unit', 'parameter', 'coordinates', 'attribution'
        }
        
        # Select numeric columns as features
        self.feature_names = [
            col for col in self.train_df.columns
            if col not in exclude_cols and self.train_df[col].dtype in ['float64', 'int64']
        ]
        
        # Create numpy arrays
        self.X_train = self.train_df[self.feature_names].values
        self.y_train = self.train_df['value'].values
        self.X_test = self.test_df[self.feature_names].values
        self.y_test = self.test_df['value'].values
    
    def get_data(self) -> Dict:
        """Get all prepared data as dictionary."""
        return {
            'X_train': self.X_train,
            'y_train': self.y_train,
            'X_test': self.X_test,
            'y_test': self.y_test,
            'feature_names': self.feature_names,
            'train_df': self.train_df,
            'test_df': self.test_df
        }
    
    def get_summary(self) -> str:
        """Get formatted data summary."""
        summary = f"""
╔═══════════════════════════════════════════════════════════╗
║              PM2.5 Dataset Summary                        ║
╚═══════════════════════════════════════════════════════════╝

DATA SPLIT:
  Training samples:    {len(self.train_df):>8,}
  Test samples:        {len(self.test_df):>8,}
  Total:               {len(self.train_df) + len(self.test_df):>8,}

FEATURES:
  Total features:      {len(self.feature_names):>8}
  Feature names:       {', '.join(self.feature_names[:5])}...

PM2.5 STATISTICS (TRAINING SET):
  Mean:                {self.y_train.mean():>8.2f} µg/m³
  Median:              {np.median(self.y_train):>8.2f} µg/m³
  Std Dev:             {self.y_train.std():>8.2f} µg/m³
  Min:                 {self.y_train.min():>8.2f} µg/m³
  Max:                 {self.y_train.max():>8.2f} µg/m³
  Q1 (25%):            {np.percentile(self.y_train, 25):>8.2f} µg/m³
  Q3 (75%):            {np.percentile(self.y_train, 75):>8.2f} µg/m³

READY FOR ML:
  ✓ X_train, y_train   Ready for training
  ✓ X_test, y_test     Ready for evaluation
  ✓ feature_names      Column mapping
        """
        return summary

    def save_artifacts(self, prefix: str = '') -> None:
        """Save feature names and metadata for later use."""
        filename = f"{prefix}feature_names.json" if prefix else "feature_names.json"
        with open(filename, 'w') as f:
            json.dump({
                'feature_names': self.feature_names,
                'n_features': len(self.feature_names),
                'n_train': len(self.train_df),
                'n_test': len(self.test_df)
            }, f, indent=2)


def quick_load(csv_file: str = 'openaq_ground_truth.csv',
               test_size: float = 0.2) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Quick one-liner to load data.
    
    Usage:
        X_train, y_train, X_test, y_test, features = quick_load()
    """
    loader = OpenAQMLDataLoader(csv_file)
    data = loader.load_and_prepare(test_size)
    print(loader.get_summary())
    return data['X_train'], data['y_train'], data['X_test'], data['y_test'], data['feature_names']


if __name__ == '__main__':
    # Example usage
    try:
        loader = OpenAQMLDataLoader('openaq_ground_truth.csv')
        data = loader.load_and_prepare(test_size=0.2)
        print(loader.get_summary())
        print("✓ Ready for ML training!")
    except FileNotFoundError as e:
        print(f"Error: {e}")
