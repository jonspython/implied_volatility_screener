import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os

app = FastAPI()

RESULTS_FILE = "option_screen_results.csv"

@app.get("/", response_class=HTMLResponse)
def read_root():
    if not os.path.exists(RESULTS_FILE):
        return "<h1>No results generated yet.</h1>"
    
    try:
        df = pd.read_csv(RESULTS_FILE)
        html_table = df.to_html(index=False, classes="table table-striped", border=1)
        
        return f"""
        <html>
          <head>
            <title>IV Screener Results</title>
            <style>
              body {{ font-family: Arial, sans-serif; margin: 20px; }}
              .table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
              .table th, .table td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
              .table th {{ background-color: #f2f2f2; position: sticky; top: 0; }}
            </style>
          </head>
          <body>
            <h2>Implied Volatility Screener Results</h2>
            <p><a href="/download">Download CSV</a></p>
            <div style="height: 80vh; overflow: auto;">
                {html_table}
            </div>
          </body>
        </html>
        """
    except Exception as e:
        return f"<h1>Error reading results: {e}</h1>"

@app.get("/download")
def download_results():
    from fastapi.responses import FileResponse
    if os.path.exists(RESULTS_FILE):
        return FileResponse(RESULTS_FILE, media_type="text/csv", filename="option_screen_results.csv")
    return {"error": "File not found"}
