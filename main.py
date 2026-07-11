import pandas as pd
import os
import uvicorn
from implied_vol_screener import option_screen
from notifier import send_email_report

def run_screener():
    print("Starting Screener Process...")
    
    # Load tickers
    tickers_file = "tickers.csv"
    if not os.path.exists(tickers_file):
        print(f"Error: {tickers_file} not found.")
        return
        
    try:
        tickers_df = pd.read_csv(tickers_file)
        # Handle simple list or header-based csv
        if 'Ticker' in tickers_df.columns:
            ticker_list = tickers_df['Ticker'].dropna().tolist()
        else:
            ticker_list = tickers_df.iloc[:, 0].dropna().tolist()
    except Exception as e:
        print(f"Failed to load {tickers_file}: {e}")
        return

    # Cap to max 1000 for safety, though Render background worker might be needed for very large lists
    ticker_list = ticker_list[:1000]
    
    print(f"Loaded {len(ticker_list)} tickers. Running screen...")
    
    try:
        results_df = option_screen(ticker_list, max_workers=20)
        
        if not results_df.empty:
            results_file = "option_screen_results.csv"
            results_df.to_csv(results_file, index=False)
            print(f"Saved results to {results_file}")
            
            # Send Email Notification
            send_email_report(results_df)
        else:
            print("No results were generated.")
    except Exception as e:
        print(f"Critical error running screener: {e}")

if __name__ == "__main__":
    import sys
    # If run with 'cron' argument, it acts as a script
    if len(sys.argv) > 1 and sys.argv[1] == "cron":
        run_screener()
    else:
        # Otherwise it can just serve the Fast API or maybe we shouldn't mix them?
        # Actually standard practice is to run FastAPI via uvicorn in a Procfile or start command.
        # This script can be run directly `python main.py cron` by Render Cron Job.
        print("Use 'python main.py cron' to run the screener.")
        print("To run the web app, use 'uvicorn app:app --host 0.0.0.0 --port 8000'")
