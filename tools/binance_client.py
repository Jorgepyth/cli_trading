import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

class BinanceTradingClient:
    def __init__(self, use_testnet=True):
        """
        Initializes the Binance Client.
        Defaults to Testnet for safety.
        """
        load_dotenv()
        
        # Load appropriate keys based on environment toggle
        if use_testnet:
            api_key = os.getenv("BINANCE_TESTNET_API_KEY")
            api_secret = os.getenv("BINANCE_TESTNET_API_SECRET")
        else:
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")
            
        if not api_key or not api_secret:
            raise ValueError("API Keys are missing from environment variables.")

        self.client = Client(api_key, api_secret, testnet=use_testnet)
        
    def ping(self):
        """Tests connectivity to the exchange."""
        try:
            return self.client.ping()
        except BinanceAPIException as e:
            print(f"Failed to ping Binance: {e}")
            return None
            
    def get_account_balance(self, asset="USDT"):
        """Retrieves the flexible balance for a given asset."""
        try:
            # Using futures_account for USDT-M Futures
            account = self.client.futures_account()
            for asset_info in account['assets']:
                if asset_info['asset'] == asset:
                    return float(asset_info['availableBalance'])
            return 0.0
        except BinanceAPIException as e:
            print(f"Error fetching balance: {e}")
            return 0.0

    def get_mark_price(self, symbol="BTCUSDT"):
        """Gets current mark price for the symbol."""
        try:
            info = self.client.futures_mark_price(symbol=symbol)
            return float(info['markPrice'])
        except BinanceAPIException as e:
            print(f"Error fetching mark price: {e}")
            return 0.0
            
    def get_leverage(self, symbol):
        """Fetches the current leverage for a given symbol."""
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            if positions:
                return int(positions[0]['leverage'])
            return None
        except BinanceAPIException as e:
            print(f"Error fetching leverage: {e}")
            return None

    def get_open_positions(self):
        """Fetches all currently open positions with non-zero amounts."""
        try:
            positions = self.client.futures_position_information()
            open_positions = []
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    open_positions.append({
                        'symbol': pos['symbol'],
                        'amount': float(pos['positionAmt']),
                        'entryPrice': float(pos['entryPrice']),
                        'markPrice': float(pos['markPrice']),
                        'unRealizedProfit': float(pos['unRealizedProfit']),
                        'leverage': int(pos['leverage']),
                        'marginType': pos['marginType']
                    })
            return open_positions
        except BinanceAPIException as e:
            print(f"Error fetching open positions: {e}")
            return []

    def execute_futures_order(self, symbol, side, order_type, quantity, price=None, stop_price=None, reduce_only=False):
        """
        Executes a futures order. Currently supports basic execution.
        """
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity,
            }
            if reduce_only:
                params['reduceOnly'] = "true"
            if price and order_type in ['LIMIT', 'STOP', 'TAKE_PROFIT']:
                params['price'] = price
            if order_type == 'LIMIT':
                params['timeInForce'] = 'GTC'  # Binance Futures requires this for LIMIT orders
            if stop_price and order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT']:
                params['stopPrice'] = stop_price
                
            response = self.client.futures_create_order(**params)
            return response
        except BinanceAPIException as e:
            print(f"API Error executing order: {e}")
            return None
