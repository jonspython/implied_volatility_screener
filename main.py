import pandas as pd
import os
import uvicorn
from implied_vol_screener import option_screen
from notifier import send_email_report
from ticker_generator import generate_tickers

def run_screener():
    print("Starting Screener Process...")
    
    # Generate tickers dynamically from CBOE volume file (if available)
    generate_tickers()
    
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
            
            # Format columns for CSV output
            csv_df = results_df.copy()
            pct_columns = [
                "Historical Volatility", "Implied Volatility", "EV Volatility", 
                "3-Year Return", "Premium %", "OTM %", "Annualized Yield", 
                "Bid/Ask Spread %", "10-Day (H-L)/C", "30-Day (H-L)/C"
            ]
            for col in pct_columns:
                if col in csv_df.columns:
                    csv_df[col] = (csv_df[col] * 100).map(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")
                    
            # Format dollar amounts
            dollar_columns = ["Current Price", "52-Week High", "52-Week Low", "Strike", "Bid", "Ask", "Midpoint"]
            for col in dollar_columns:
                if col in csv_df.columns:
                    csv_df[col] = csv_df[col].map(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")
                    
            # Format large integers with commas
            int_columns = ["Market Cap", "Enterprise Value", "Option Volume", "Open Interest"]
            for col in int_columns:
                if col in csv_df.columns:
                    csv_df[col] = csv_df[col].map(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
            
            # Format IV/HV as a simple 2-decimal number
            if "IV / HV" in csv_df.columns:
                csv_df["IV / HV"] = csv_df["IV / HV"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
                
            csv_df.to_csv(results_file, index=False)
            print(f"Saved formatted results to {results_file}")
            
            # Send Email Notification using the original unformatted numeric DataFrame
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
