"""
Sentinel-5P TROPOMI Aerosol Data Download and Integration Script

Downloads Aerosol Index (AI) data from NASA GES DISC
and integrates it with OpenAQ PM2.5 measurements for ML applications.

Usage:
    python sentinel5p_aerosol_downloader.py --start-date 2022-01-01 --end-date 2024-01-01 --city Beijing

Requirements:
    - NASA Earthdata account (free): https://urs.earthdata.nasa.gov/users/new
    - earthaccess, xarray, netCDF4 packages
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import xarray as xr
import warnings

warnings.filterwarnings('ignore')


class Sentinel5PAerosolDownloader:
    """Download and process Sentinel-5P TROPOMI aerosol data from NASA GES DISC."""
    
    # Define region bounds (latitude, longitude)
    REGIONS = {
        'Beijing': {'north': 40.16, 'south': 39.44, 'east': 116.68, 'west': 115.42},
        'Delhi': {'north': 29.00, 'south': 28.40, 'east': 77.40, 'west': 76.80},
        'Shanghai': {'north': 31.97, 'south': 30.70, 'east': 121.97, 'west': 120.50},
    }
    
    def __init__(self, username=None, password=None):
        """
        Initialize downloader with NASA credentials.
        
        Args:
            username: NASA Earthdata username
            password: NASA Earthdata password
        """
        self.username = username
        self.password = password
        self.auth = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with NASA Earthdata."""
        try:
            import earthaccess
            
            if self.username and self.password:
                self.auth = earthaccess.login(
                    username=self.username,
                    password=self.password
                )
            else:
                # Try automated netrc login
                self.auth = earthaccess.login(strategy="netrc")
            
            if self.auth:
                user = earthaccess.whoami()
                print(f"✓ Authenticated as: {user}")
                self.earthaccess = earthaccess
                return True
            else:
                print("✗ Authentication failed.")
                print("  Create account: https://urs.earthdata.nasa.gov/users/new")
                return False
        except ImportError:
            print("✗ earthaccess not installed.")
            print("  Run: pip install earthaccess")
            return False
    
    def download(self, city, start_date, end_date, output_dir='../data/sentinel5p_aerosol', limit=None):
        """
        Download Sentinel-5P TROPOMI aerosol granules for specified region and date range.
        
        Args:
            city: City name (Beijing, Delhi, Shanghai)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            output_dir: Output directory
            limit: Maximum granules to download (None = all)
        
        Returns:
            List of downloaded file paths
        """
        if city not in self.REGIONS:
            print(f"✗ Unknown city. Available: {list(self.REGIONS.keys())}")
            return []
        
        bounds = self.REGIONS[city]
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\nSearching Sentinel-5P TROPOMI Aerosol Index data:")
        print(f"  City: {city}")
        print(f"  Bounds: {bounds['west']:.2f}°E - {bounds['east']:.2f}°E, "
              f"{bounds['south']:.2f}°N - {bounds['north']:.2f}°N")
        print(f"  Dates: {start_date} to {end_date}")
        print(f"  Dataset: S5P_L2__AER_AI (Level-2 Aerosol Index)")
        print(f"  Resolution: ~7 km")
        
        # Search
        results = self.earthaccess.search_data(
            short_name='S5P_L2__AER_AI',
            temporal=(start_date, end_date),
            bounding_box=(
                bounds['west'],
                bounds['south'],
                bounds['east'],
                bounds['north']
            )
        )
        
        print(f"✓ Found {len(results)} granules")
        
        if not results:
            return []
        
        # Download
        if limit:
            results = results[:limit]
            print(f"  Downloading {limit} granules (sample)...")
        else:
            print(f"  Downloading all {len(results)} granules...")
        
        files = self.earthaccess.download(results, str(output_path))
        print(f"✓ Downloaded {len(files)} files")
        
        return files
    
    def extract_ai(self, nc_file):
        """
        Extract Aerosol Index and geolocation from NetCDF file.
        
        Returns:
            dict with aerosol_index, latitude, longitude, date
        """
        try:
            ds = xr.open_dataset(nc_file, group='PRODUCT')
            
            # Try different possible variable names
            ai_names = ['absorbing_aerosol_index', 'aerosol_index', 'AI']
            ai_data = None
            
            for name in ai_names:
                if name in ds.data_vars:
                    ai_data = ds[name].values
                    break
            
            if ai_data is None:
                print(f"Warning: Could not find aerosol index in {Path(nc_file).name}")
                return None
            
            # Get lat/lon
            lat = ds['latitude'].values
            lon = ds['longitude'].values
            
            # Extract date from filename (format: S5P_..._20220101_...)
            filename = Path(nc_file).stem
            try:
                date_str = filename.split('_')[1]
                date = pd.Timestamp(date_str[:8])
            except:
                date = None
            
            ds.close()
            
            return {
                'aerosol_index': ai_data,
                'latitude': lat,
                'longitude': lon,
                'date': date
            }
        except Exception as e:
            print(f"Warning: Could not read {Path(nc_file).name}: {e}")
            return None
    
    def process_granules(self, file_list):
        """
        Process downloaded granules and compute mean AI.
        
        Returns:
            DataFrame with date-wise AI statistics
        """
        ai_records = []
        
        for nc_file in file_list:
            data = self.extract_ai(nc_file)
            if not data:
                continue
            
            ai = data['aerosol_index'].astype(float).copy()
            ai[ai < -20] = np.nan  # Remove fill values
            ai[ai > 50] = np.nan   # Remove invalid high values
            
            mean_ai = np.nanmean(ai)
            
            if np.isnan(mean_ai):
                continue
            
            valid_pix = np.sum(~np.isnan(ai))
            
            ai_records.append({
                'date': data['date'],
                'aerosol_index': mean_ai,
                'valid_pixels': valid_pix,
                'filename': Path(nc_file).name
            })
        
        ai_df = pd.DataFrame(ai_records).dropna(subset=['date'])
        ai_df['date'] = pd.to_datetime(ai_df['date'])
        
        return ai_df.sort_values('date')
    
    def integrate_with_openaq(self, openaq_csv, ai_df, output_csv=None):
        """
        Integrate Aerosol Index with OpenAQ PM2.5 data.
        
        Args:
            openaq_csv: Path to OpenAQ CSV
            ai_df: DataFrame with AI data
            output_csv: Path to save integrated data
        
        Returns:
            Integrated DataFrame
        """
        print(f"\nIntegrating Sentinel-5P TROPOMI AI with OpenAQ data...")
        
        openaq = pd.read_csv(openaq_csv)
        openaq['date'] = pd.to_datetime(openaq['date'])
        openaq['date_only'] = openaq['date'].dt.date
        
        # Merge on date
        ai_daily = ai_df.groupby('date').agg({
            'aerosol_index': 'mean',
            'valid_pixels': 'sum'
        }).reset_index()
        ai_daily['date'] = pd.to_datetime(ai_daily['date']).dt.date
        
        integrated = openaq.merge(
            ai_daily[['date', 'aerosol_index']],
            left_on='date_only',
            right_on='date',
            how='left'
        )
        
        # Rename for clarity
        integrated = integrated.rename(columns={'aerosol_index': 'SENTINEL5P_AI'})
        
        # Fill missing AI with interpolation
        integrated['SENTINEL5P_AI'] = integrated.groupby('city')['SENTINEL5P_AI'].transform(
            lambda x: x.fillna(x.interpolate())
        )
        
        missing = integrated['SENTINEL5P_AI'].isna().sum()
        coverage = (1 - missing/len(integrated))*100
        
        print(f"✓ Integrated {len(integrated)} records")
        print(f"  AI coverage: {coverage:.1f}%")
        
        if 'value' in integrated.columns:
            corr = integrated['value'].corr(integrated['SENTINEL5P_AI'])
            print(f"  Correlation with PM2.5: {corr:.3f}")
        
        # Drop temporary date column
        if 'date' in integrated.columns and integrated['date_only'] is not None:
            integrated = integrated.drop('date', axis=1, errors='ignore')
        
        if output_csv:
            integrated.to_csv(output_csv, index=False)
            print(f"✓ Saved to: {output_csv}")
        
        return integrated


def main():
    parser = argparse.ArgumentParser(
        description='Download Sentinel-5P TROPOMI Aerosol Index and integrate with OpenAQ PM2.5'
    )
    parser.add_argument('--city', default='Beijing', 
                       choices=['Beijing', 'Delhi', 'Shanghai'],
                       help='City/region to download')
    parser.add_argument('--start-date', default='2022-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-01-01',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=10,
                       help='Max granules to download (None for all)')
    parser.add_argument('--username',
                       help='NASA Earthdata username')
    parser.add_argument('--password',
                       help='NASA Earthdata password')
    parser.add_argument('--openaq-csv', 
                       default='../data/openaq_ground_truth.csv',
                       help='Path to OpenAQ CSV file')
    parser.add_argument('--output-dir',
                       default='../data/sentinel5p_aerosol',
                       help='Output directory for Sentinel-5P files')
    
    args = parser.parse_args()
    
    # Download
    downloader = Sentinel5PAerosolDownloader(args.username, args.password)
    if not downloader.auth:
        return
    
    files = downloader.download(
        args.city,
        args.start_date,
        args.end_date,
        args.output_dir,
        args.limit
    )
    
    if not files:
        print("No files to process")
        return
    
    # Process
    print("\nProcessing granules...")
    ai_df = downloader.process_granules(files)
    print(f"✓ Processed {len(ai_df)} days of AI data")
    print(f"\nAerosol Index Statistics:")
    print(ai_df['aerosol_index'].describe())
    
    # Integrate
    if Path(args.openaq_csv).exists():
        output_csv = f'../data/openaq_with_sentinel5p_ai_{args.city}.csv'
        integrated = downloader.integrate_with_openaq(
            args.openaq_csv,
            ai_df,
            output_csv
        )
    else:
        print(f"Warning: {args.openaq_csv} not found. Save AI for later integration.")
        ai_df.to_csv(f'../data/ai_{args.city}.csv', index=False)


if __name__ == '__main__':
    main()
