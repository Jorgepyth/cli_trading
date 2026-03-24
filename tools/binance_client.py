import os
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
import requests
import time
import hmac
import hashlib
import urllib.parse

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
        self.exchange_info = None

    def get_symbol_filters(self, symbol):
        """Fetches the required quantity and price precision filters for a symbol."""
        try:
            if not self.exchange_info:
                self.exchange_info = self.client.futures_exchange_info()
            
            filters = {'stepSize': 0.001, 'tickSize': 0.1} # Default
            for sym in self.exchange_info['symbols']:
                if sym['symbol'] == symbol:
                    for f in sym['filters']:
                        if f['filterType'] == 'LOT_SIZE':
                            filters['stepSize'] = float(f['stepSize'])
                        elif f['filterType'] == 'PRICE_FILTER':
                            filters['tickSize'] = float(f['tickSize'])
                    break
            return filters
        except Exception as e:
            print(f"Error fetching symbol filters: {e}")
            return {'stepSize': 0.001, 'tickSize': 0.1}

    def format_precision(self, value, step, round_type="truncate"):
        """Formats value to the step interval. Supports truncate or round."""
        import math
        decimals = int(round(-math.log10(step))) if step < 1 else 0
        factor = 10 ** decimals
        if round_type == "truncate":
            # Strict truncation (floor instead of round up)
            return math.floor(value * factor) / factor
        else:
            return round(value, decimals)
        
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
        Ejecuta la orden. Enruta automáticamente las órdenes condicionales al nuevo endpoint Algo.
        """
        try:
            filters = self.get_symbol_filters(symbol)
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
            }
            if quantity is not None:
                params['quantity'] = self.format_precision(quantity, filters['stepSize'], "truncate")
                
            if reduce_only:
                params['reduceOnly'] = "true"
            if price and order_type in ['LIMIT', 'STOP', 'TAKE_PROFIT']:
                params['price'] = self.format_precision(price, filters['tickSize'], "round")
            if order_type == 'LIMIT':
                params['timeInForce'] = 'GTC'
            if stop_price and order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT']:
                # The algoOrder endpoint specifically requires 'triggerPrice' instead of 'stopPrice'
                params['triggerPrice'] = self.format_precision(stop_price, filters['tickSize'], "round")
                
            # Intercepción para enrutamiento a la API Algo de Binance
            if order_type in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP', 'TAKE_PROFIT', 'TRAILING_STOP_MARKET']:
                params['algoType'] = 'CONDITIONAL'
                params['timestamp'] = int(time.time() * 1000)
                
                # Retrieve configured credentials
                api_key = self.client.API_KEY
                api_secret = self.client.API_SECRET
                
                # Determine Base URL
                if getattr(self.client, 'testnet', False) or self.client.FUTURES_URL == self.client.FUTURES_TESTNET_URL:
                    base_url = "https://testnet.binancefuture.com"
                else:
                    base_url = "https://fapi.binance.com"
                
                # Format parameters for query string
                query_string = urllib.parse.urlencode(params)
                
                # Generate SHA256 signature
                signature = hmac.new(
                    api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                # Form endpoint URL
                endpoint_url = f"{base_url}/fapi/v1/algoOrder?{query_string}&signature={signature}"
                
                headers = {
                    'X-MBX-APIKEY': api_key
                }
                
                http_response = requests.post(endpoint_url, headers=headers)
                response = http_response.json()
                
                if http_response.status_code != 200:
                    raise BinanceAPIException(http_response, http_response.status_code, response.get('msg', 'Algo API Error'))
            else:
                response = self.client.futures_create_order(**params)
                
            return response
        except BinanceAPIException as e:
            print(f"API Error executing order: {e}")
            return None

    def get_open_orders(self, symbol=None):
        """
        Recupera tanto las órdenes estándar como las órdenes Algo (TP/SL) para mantener la paridad en la CLI.
        """
        try:
            kwargs = {}
            if symbol:
                kwargs['symbol'] = symbol
                
            # 1. Órdenes Límite estándar
            standard_orders = self.client.futures_get_open_orders(**kwargs)
            
            # 2. Órdenes Condicionales (Algo)
            algo_orders = self.client._request_futures_api('get', 'openAlgoOrders', signed=True, data=kwargs)
            
            # Normalización del payload de respuesta: La API Algo devuelve 'algoId' en lugar de 'orderId'
            for order in algo_orders:
                order['orderId'] = order.get('algoId')
                
            return standard_orders + algo_orders
            
        except BinanceAPIException as e:
            print(f"Error fetching open orders: {e}")
            return []

    def cancel_order(self, symbol, order_id):
        """
        Intenta cancelar una orden en el endpoint estándar. Si falla por orden desconocida, intenta en el endpoint Algo.
        """
        try:
            return self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as e:
            # -2011: Unknown order sent (Indica que podría ser una orden Algo que reside en el otro endpoint)
            if e.code == -2011:
                try:
                    return self.client._request_futures_api('delete', 'algoOrder', signed=True, data={'symbol': symbol, 'algoId': order_id})
                except BinanceAPIException as algo_e:
                    print(f"Error cancelling algo order {order_id}: {algo_e}")
                    return None
            else:
                print(f"Error cancelling order {order_id}: {e}")
                return None
