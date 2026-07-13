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
        
        import yfinance as yf
        import time
        
        # Keep unique Underlying symbols
        df = df.drop_duplicates(subset=['Underlying'])
        
        # Take the top 2000 to have a large enough pool for price filtering
        top_pool = df.head(2000)
        ticker_list = top_pool['Underlying'].tolist()
        
        print(f"Fetching recent prices for top-volume tickers to apply price filter...")
        
        eligible_tickers = []
        batch_size = 50
        
        for i in range(0, len(ticker_list), batch_size):
            batch = ticker_list[i:i+batch_size]
            print(f"Fetching batch {i//batch_size + 1}/{len(ticker_list)//batch_size}...")
            
            try:
                # threads=False to prevent immediate rate limit ban
                price_data = yf.download(batch, period="1d", progress=False, threads=False)
                
                if "Adj Close" in price_data:
                    close_prices = price_data["Adj Close"].iloc[-1]
                elif "Close" in price_data:
                    close_prices = price_data["Close"].iloc[-1]
                else:
                    close_prices = pd.Series(dtype=float)
                    
                for ticker in batch:
                    if ticker in close_prices and pd.notnull(close_prices[ticker]) and close_prices[ticker] < 20:
                        eligible_tickers.append(ticker)
                        
                if len(eligible_tickers) >= 500:
                    eligible_tickers = eligible_tickers[:500]
                    break
                    
                time.sleep(1) # short sleep to respect rate limits
            except Exception as e:
                print(f"Error fetching batch {i//batch_size + 1}: {e}")
                time.sleep(5) # longer sleep on error
        
        # Write to tickers.csv
        tickers_df = pd.DataFrame({"Ticker": eligible_tickers})
        tickers_df.to_csv("tickers.csv", index=False)
        
        print(f"Successfully generated tickers.csv with {len(tickers_df)} highly liquid tickers under $20.")
        
    except Exception as e:
        print(f"Failed to generate tickers: {e}")

if __name__ == "__main__":
    generate_tickers()
