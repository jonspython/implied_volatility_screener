import pandas as pd
import requests
import io

import time

def fetch_top_losers(max_price=30, count=50):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Fetching top {count} losers under ${max_price} from Yahoo Finance...")
    
    eligible_tickers = []
    start = 0
    batch_size = 250
    
    try:
        while len(eligible_tickers) < count and start < 1000:
            url = f"https://finance.yahoo.com/markets/stocks/losers/?start={start}&count={batch_size}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            try:
                df_list = pd.read_html(io.StringIO(response.text))
            except ValueError:
                break
                
            if not df_list:
                break
                
            df = df_list[0]
            if 'Symbol' not in df.columns or 'Price' not in df.columns:
                break
                
            # Parse price (handles formats like '107.96 -15.29 (-12.41%)')
            df['Price_val'] = pd.to_numeric(df['Price'].astype(str).str.split(' ').str[0].str.replace(',', ''), errors='coerce')
            
            # Filter by price
            filtered = df[df['Price_val'] < max_price]
            eligible_tickers.extend(filtered['Symbol'].tolist())
            
            start += batch_size
            time.sleep(0.5)
            
        tickers = eligible_tickers[:count]
        
        if not tickers:
            print("No tickers found matching the criteria.")
            return
            
        # Write to tickers.csv
        tickers_df = pd.DataFrame({"Ticker": tickers})
        tickers_df.to_csv("tickers.csv", index=False)
        print(f"Successfully updated tickers.csv with {len(tickers)} tickers.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_top_losers()
