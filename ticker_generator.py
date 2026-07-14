import pandas as pd
import glob
import os

def generate_tickers():
    print("Searching for CBOE volume CSV files...")
    # Find any monthly_volume*.csv or .xlsx files in the current directory
    csv_files = glob.glob("monthly_volume*.csv") + glob.glob("monthly_volume*.xlsx")
    
    if not csv_files:
        print("No CBOE volume CSV/XLSX found. Skipping dynamic ticker generation. Will use existing tickers.csv.")
        return
        
    # Pick the most recent one based on file modification time
    latest_csv = max(csv_files, key=os.path.getmtime)
    print(f"Using {latest_csv} to generate tickers...")
    
    try:
        if latest_csv.endswith(".xlsx"):
            df = pd.read_excel(latest_csv)
        else:
            df = pd.read_csv(latest_csv)
        
        # Ensure required columns exist
        if 'Underlying' not in df.columns:
            print(f"Error: 'Underlying' column not found in {latest_csv}")
            return
            
        if 'Average Daily Volume' not in df.columns:
            if 'Volume' in df.columns:
                df = df.rename(columns={'Volume': 'Average Daily Volume'})
            else:
                print(f"Error: Neither 'Average Daily Volume' nor 'Volume' found in {latest_csv}")
                return
                
        # Drop rows with NaN in Underlying or Average Daily Volume
        df = df.dropna(subset=['Underlying', 'Average Daily Volume'])
        
        # Some average daily volumes might be strings with commas, so convert to numeric
        if df['Average Daily Volume'].dtype == object:
            df['Average Daily Volume'] = pd.to_numeric(df['Average Daily Volume'].astype(str).str.replace(',', ''), errors='coerce')
            
        # Sort by Average Daily Volume descending
        df = df.sort_values(by='Average Daily Volume', ascending=False)
        
        import yfinance as yf
        import time
        
        # Keep unique Underlying symbols
        df = df.drop_duplicates(subset=['Underlying'])
        
        # Take the top 2000 to have a large enough pool for price filtering
        top_pool = df.head(2000)
        ticker_list = top_pool['Underlying'].tolist()
        
        print(f"Fetching recent prices for top-volume tickers to apply price filter...")
        
        eligible_tickers = []
        
        for i, ticker in enumerate(ticker_list):
            if i % 100 == 0:
                print(f"Processed {i}/{len(ticker_list)} tickers...")
                
            try:
                info = yf.Ticker(ticker).fast_info
                price = info.get('lastPrice')
                
                if price is not None and price < 20:
                    eligible_tickers.append(ticker)
                    
                if len(eligible_tickers) >= 1000:
                    break
                    
            except Exception as e:
                pass
        
        # Write to tickers.csv
        tickers_df = pd.DataFrame({"Ticker": eligible_tickers})
        tickers_df.to_csv("tickers.csv", index=False)
        
        print(f"Successfully generated tickers.csv with {len(tickers_df)} highly liquid tickers under $20.")
        
    except Exception as e:
        print(f"Failed to generate tickers: {e}")

if __name__ == "__main__":
    generate_tickers()
