import os
import logging
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def ping_binance():
    # Load environment variables from .env
    # The .env should be at the root of the project
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    # Initialize client indicating we want to use the Testnet
    client = Client(api_key, api_secret, testnet=True)

    try:
        logging.info("Pinging Binance Futures Testnet...")
        # Note: We're doing Futures trading. The standard ping() might hit spot depending on python-binance version, 
        # but futures_ping() ensures we're hitting the futures endpoint.
        result = client.futures_ping()
        logging.info(f"Ping result: {result} (Empty dictionary means success)")
        
        time_res = client.futures_time()
        logging.info(f"Binance Futures Server Time: {time_res}")
        
        # Only try to fetch account details if keys look like they've been replaced
        if api_key and api_key != "[ENTER_KEY_HERE]":
            logging.info("Testing authentication with provided keys...")
            account = client.futures_account()
            logging.info("Successfully fetched Futures account details. Authentication works.")
        else:
            logging.info("Skipping authentication test - default or missing API keys in .env.")
            
    except BinanceAPIException as e:
        logging.error(f"Binance API Exception: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    ping_binance()
