import pandas as pd
import glob
import os

def generate_tickers():
    print("Searching for CBOE volume CSV files...")
    # Find any monthly_volume*.csv files in the current directory
    csv_files = glob.glob("monthly_volume*.csv")
    
    if not csv_files:
        print("No CBOE volume CSV found. Skipping dynamic ticker generation. Will use existing tickers.csv.")
        return
        
    # Pick the most recent one based on file modification time
    latest_csv = max(csv_files, key=os.path.getmtime)
    print(f"Using {latest_csv} to generate tickers...")
    
    try:
        df = pd.read_csv(latest_csv)
        
        # Ensure required columns exist
        if 'Underlying' not in df.columns or 'Average Daily Volume' not in df.columns:
            print(f"Error: Required columns not found in {latest_csv}")
            return
            
        # Drop rows with NaN in Underlying or Average Daily Volume
        df = df.dropna(subset=['Underlying', 'Average Daily Volume'])
        
        # Some average daily volumes might be strings with commas, so convert to numeric
        if df['Average Daily Volume'].dtype == object:
            df['Average Daily Volume'] = pd.to_numeric(df['Average Daily Volume'].str.replace(',', ''), errors='coerce')
            
        # Sort by Average Daily Volume descending
        df = df.sort_values(by='Average Daily Volume', ascending=False)
        
        # Keep unique Underlying symbols
        df = df.drop_duplicates(subset=['Underlying'])
        
        # Take the top 1000
        top_tickers = df.head(1000)
        
        # Write to tickers.csv
        tickers_df = pd.DataFrame({"Ticker": top_tickers['Underlying']})
        tickers_df.to_csv("tickers.csv", index=False)
        
        print(f"Successfully generated tickers.csv with {len(tickers_df)} highly liquid tickers based on CBOE Options Volume.")
        
    except Exception as e:
        print(f"Failed to generate tickers: {e}")

if __name__ == "__main__":
    generate_tickers()
