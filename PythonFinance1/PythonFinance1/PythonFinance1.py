import yfinance as yf
import mplfinance as mpf

ticker = input("Enter stock name (e.g., AAPL, MSFT): ").upper() # .upper() for consistent ticker format
aapl = yf.Ticker(ticker)
stock_data = aapl.history(start='2024-01-01', end='2024-05-20')
#df = yf.download(ticker, start='2024-01-01', end='2024-05-20') # Changed dates to be in the past

if stock_data.empty:
    print(f"Could not download data for {ticker}. Please check the ticker symbol.")
else:
    mpf.plot(stock_data, type='candle', style='charles', title=f'{ticker} Stock Chart', ylabel='Price')
