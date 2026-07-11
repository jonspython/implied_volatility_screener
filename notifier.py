import smtplib
import os
from email.message import EmailMessage
from datetime import datetime

def send_email_report(df):
    if df.empty:
        print("No results to send.")
        return

    # Filter for Annualized Yield > 100% (1.0)
    filtered_df = df[df['Annualized Yield'] > 1.0].copy()
    
    if filtered_df.empty:
        print("No tickers matched the criteria (Annualized Yield > 100%).")
        return

    # Sort descending by yield
    filtered_df = filtered_df.sort_values('Annualized Yield', ascending=False)
    
    # Take top 50 to avoid massive emails if market is crazy
    filtered_df = filtered_df.head(50)
    
    # Format to percentage for display
    filtered_df['Annualized Yield'] = (filtered_df['Annualized Yield'] * 100).map('{:.2f}%'.format)

    html_table = filtered_df.to_html(index=False, classes="table", border=1)

    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; }}
          .table {{ border-collapse: collapse; width: 100%; }}
          .table th, .table td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
          .table th {{ background-color: #f2f2f2; }}
        </style>
      </head>
      <body>
        <h2>High Implied Volatility Screen ({datetime.today().strftime('%Y-%m-%d')})</h2>
        <p>The following tickers have an annualized yield greater than 100%:</p>
        {html_table}
      </body>
    </html>
    """

    sender = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    recipient = "jonathan@hysharpe.com"
    
    if not sender or not password:
        print("SMTP_USER and/or SMTP_PASS environment variables are not set. Cannot send email.")
        # We can simulate sending email for testing without crashing
        print("Filtered tickers:", filtered_df["Ticker"].tolist())
        return

    msg = EmailMessage()
    msg['Subject'] = f"IV Screener Report - {datetime.today().strftime('%Y-%m-%d')}"
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content("Please enable HTML viewing to see the report.")
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print(f"Successfully sent report to {recipient}")
    except Exception as e:
        print(f"Failed to send email: {e}")
