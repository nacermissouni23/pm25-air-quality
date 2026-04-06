"""
MODIS AOD Data Download and Integration Script

Downloads Aerosol Optical Depth (AOD) data from NASA LAADS DAAC
and integrates it with OpenAQ PM2.5 measurements for ML applications.

Usage:
    python modis_aod_downloader.py --start-date 2022-01-01 --end-date 2024-01-01 --city Beijing

Requirements:
    - NASA Earthdata account (free): https://urs.earthdata.nasa.gov/users/new
    - earthaccess, h5py, rasterio packages
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import h5py
import warnings

warnings.filterwarnings('ignore')


class MODISAODDownloader:
    """Download and process MODIS AOD data from NASA LAADS DAAC."""
    
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
    
    def download(self, city, start_date, end_date, output_dir='../data/modis_aod', limit=None):
        """
        Download MODIS AOD granules for specified region and date range.
        
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
        
        print(f"\nSearching MODIS AOD data:")
        print(f"  City: {city}")
        print(f"  Bounds: {bounds['west']:.2f}°E - {bounds['east']:.2f}°E, "
              f"{bounds['south']:.2f}°N - {bounds['north']:.2f}°N")
        print(f"  Dates: {start_date} to {end_date}")
        
        # Search
        results = self.earthaccess.search_data(
            short_name=['MYD04_L2', 'MOD04_L2'],
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
    
    def extract_aod(self, h5_file):
        """
        Extract AOD and geolocation from HDF5 file.
        
        Returns:
            dict with aod_550, latitude, longitude
        """
        try:
            with h5py.File(h5_file, 'r') as f:
                # Different field names for Terra (MOD) vs Aqua (MYD)
                try:
                    aod = f['/mod04/Data Fields/Optical_Depth_Land_And_Ocean'][:]
                    lat = f['/mod04/Geolocation Fields/Latitude'][:]
                    lon = f['/mod04/Geolocation Fields/Longitude'][:]
                except KeyError:
                    aod = f['/myd04/Data Fields/Optical_Depth_Land_And_Ocean'][:]
                    lat = f['/myd04/Geolocation Fields/Latitude'][:]
                    lon = f['/myd04/Geolocation Fields/Longitude'][:]
                
                return {
                    'aod_550': aod,
                    'latitude': lat,
                    'longitude': lon
                }
        except Exception as e:
            print(f"Warning: Could not read {Path(h5_file).name}: {e}")
            return None
    
    def process_granules(self, file_list):
        """
        Process downloaded granules and compute mean AOD.
        
        Returns:
            DataFrame with date-wise AOD statistics
        """
        aod_records = []
        
        for h5_file in file_list:
            data = self.extract_aod(h5_file)
            if not data:
                continue
            
            aod = data['aod_550'].copy()
            aod[aod > 5.0] = np.nan  # Remove invalid
            
            mean_aod = np.nanmean(aod)
            valid_pix = np.sum(~np.isnan(aod))
            
            # Extract date from filename (format: YYYYDDD)
            filename = Path(h5_file).stem
            try:
                year_day = filename.split('.')[1]
                year = int(year_day[:4])
                day_of_year = int(year_day[4:])
                date = pd.Timestamp(f'{year}-01-01') + pd.Timedelta(days=day_of_year-1)
            except:
                date = None
            
            aod_records.append({
                'date': date,
                'aod_550': mean_aod,
                'valid_pixels': valid_pix,
                'filename': Path(h5_file).name
            })
        
        aod_df = pd.DataFrame(aod_records).dropna(subset=['date'])
        aod_df['date'] = pd.to_datetime(aod_df['date'])
        
        return aod_df.sort_values('date')
    
    def integrate_with_openaq(self, openaq_csv, aod_df, output_csv=None):
        """
        Integrate AOD with OpenAQ PM2.5 data.
        
        Args:
            openaq_csv: Path to OpenAQ CSV
            aod_df: DataFrame with AOD data
            output_csv: Path to save integrated data
        
        Returns:
            Integrated DataFrame
        """
        print(f"\nIntegrating MODIS AOD with OpenAQ data...")
        
        openaq = pd.read_csv(openaq_csv)
        openaq['date'] = pd.to_datetime(openaq['date'])
        openaq['date_only'] = openaq['date'].dt.date
        
        # Merge on date
        aod_daily = aod_df.groupby('date_only').agg({
            'aod_550': 'mean',
            'valid_pixels': 'sum'
        }).reset_index()
        aod_daily['date_only'] = pd.to_datetime(aod_daily['date_only'])
        
        integrated = openaq.merge(
            aod_daily[['date_only', 'aod_550']],
            left_on='date_only',
            right_on='date_only',
            how='left'
        )
        
        # Fill missing AOD with interpolation
        integrated['aod_550'] = integrated.groupby('city')['aod_550'].transform(
            lambda x: x.fillna(x.interpolate())
        )
        
        missing = integrated['aod_550'].isna().sum()
        print(f"✓ Integrated {len(integrated)} records")
        print(f"  AOD coverage: {(1 - missing/len(integrated))*100:.1f}%")
        print(f"  Correlation with PM2.5: {integrated['value'].corr(integrated['aod_550']):.3f}")
        
        if output_csv:
            integrated.to_csv(output_csv, index=False)
            print(f"✓ Saved to: {output_csv}")
        
        return integrated


def main():
    parser = argparse.ArgumentParser(
        description='Download MODIS AOD data and integrate with OpenAQ PM2.5'
    )
    parser.add_argument('--city', default='Beijing', 
                       choices=['Beijing', 'Delhi', 'Shanghai'],
                       help='City/region to download')
    parser.add_argument('--start-date', default='2022-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-01-01',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=5,
                       help='Max granules to download (None for all)')
    parser.add_argument('--username',
                       help='NASA Earthdata username')
    parser.add_argument('--password',
                       help='NASA Earthdata password')
    parser.add_argument('--openaq-csv', 
                       default='../data/openaq_ground_truth.csv',
                       help='Path to OpenAQ CSV file')
    parser.add_argument('--output-dir',
                       default='../data/modis_aod',
                       help='Output directory for MODIS files')
    
    args = parser.parse_args()
    
    # Download
    downloader = MODISAODDownloader(args.username, args.password)
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
    aod_df = downloader.process_granules(files)
    print(f"✓ Processed {len(aod_df)} days of AOD data")
    print(f"\nAOD Statistics:")
    print(aod_df['aod_550'].describe())
    
    # Integrate
    if Path(args.openaq_csv).exists():
        output_csv = f'../data/openaq_with_modis_aod_{args.city}.csv'
        integrated = downloader.integrate_with_openaq(
            args.openaq_csv,
            aod_df,
            output_csv
        )
    else:
        print(f"Warning: {args.openaq_csv} not found. Save AOD for later integration.")
        aod_df.to_csv(f'../data/aod_{args.city}.csv', index=False)


if __name__ == '__main__':
    main()
