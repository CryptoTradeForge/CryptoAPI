import os
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from abstract_futures_api import AbstractFuturesAPI

class BinanceFutures(AbstractFuturesAPI):
    def __init__(self, env_path=".env"):
        """初始化 Binance Futures 交易類別"""
        
        self.env_path = env_path
        self.env = load_dotenv(self.env_path)
        self.binance_api_key = os.getenv("BINANCE_API_KEY")
        self.binance_api_secret = os.getenv("BINANCE_API_SECRET")
        self._initialize_client()

    def _initialize_client(self):
        """初始化 Binance 客戶端"""
        self.client = Client(
            api_key=self.binance_api_key,
            api_secret=self.binance_api_secret,
        )

    def set_stop_loss_take_profit(self, symbol, side, stop_loss_price=None, take_profit_price=None):
        """設置止損和止盈條件單"""
        symbol = self._modify_symbol_name(symbol)
        try:
            # 檢查是否有持倉
            position = self.get_positions(symbol=symbol)
            if not position or float(position[0]["notional"]) <= 0:
                print("無持倉，跳過設置止損止盈單。")
                return
            else:
                amount = float(position[0]["notional"])
            
            # 止損單設置
            if stop_loss_price:
                stop_side = "SELL" if side.upper() == "BUY" or side == "LONG" else "BUY"
                self.client.futures_create_order(
                    symbol=symbol,
                    side=stop_side,
                    type="STOP_MARKET",
                    quantity=amount,
                    stopPrice=stop_loss_price,
                    reduceOnly=True,
                    timeInForce="GTC"
                )
                print(f"設置 {symbol} {side} 止損單成功，止損價格：{stop_loss_price}")
                
            # 止盈單設置
            if take_profit_price:
                tp_side = "SELL" if side.upper() == "BUY" or side == "LONG" else "BUY"
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp_side,
                    type="TAKE_PROFIT_MARKET",
                    quantity=amount,
                    stopPrice=take_profit_price,
                    reduceOnly=True,
                    timeInForce="GTC"
                )
                print(f"設置 {symbol} {side} 止盈單成功，止盈價格：{take_profit_price}")
                
        except BinanceAPIException as e:
            print(f"設置止損止盈單失敗: {e}")
            
            # 平倉
            self.close_position(symbol, "LONG" if side == "BUY" else "SHORT")
            raise Exception(f"設置止損止盈單失敗: {e}")


    def place_market_order(self, symbol, position_type, amount, leverage, stop_loss_price=None, take_profit_price=None):
        """開倉操作（多頭或空頭）"""
        try:
            symbol = self._modify_symbol_name(symbol)
            side = "BUY" if position_type.upper() == "LONG" or position_type == "BUY" else "SELL"
            price = self.get_price(symbol)
            quantity = amount / price
            
            # Get symbol info to handle precision and step sizes
            symbol_info = self.client.get_symbol_info(symbol)
            filters = symbol_info["filters"]
            
            # Get precision for quantity (LOT_SIZE) and price (PRICE_FILTER)
            tick_size = next(filter for filter in filters if filter['filterType'] == 'PRICE_FILTER')['tickSize']
            step_size = next(filter for filter in filters if filter['filterType'] == 'LOT_SIZE')['stepSize']
            
            price_precision = self._get_precision_from_step(tick_size)
            quantity_precision = self._get_precision_from_step(step_size)
            
            # Round quantity and price to the correct precision
            quantity = float('{:.{}f}'.format(quantity, quantity_precision))
            price = float('{:.{}f}'.format(price, price_precision))
            
            # 設定槓桿
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            
            # 設定保證金模式
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
            except BinanceAPIException as e:
                if "No need to change margin type." not in str(e):
                    raise e
            
            # 市價開倉
            self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity
            )
            
            print(f"開 {position_type} 倉成功，數量：{quantity}，價格：{price}")
            # 設置止損止盈
            self.set_stop_loss_take_profit(symbol, side, stop_loss_price, take_profit_price)
            
        except BinanceAPIException as e:
            raise Exception(f"開 {position_type} 市價單失敗：{e}")


    def place_limit_order(self, symbol, position_type, amount, price, leverage):
        """限價開倉"""
        try:
            # Modify symbol name for API
            symbol = self._modify_symbol_name(symbol)
            
            # Determine the side (BUY or SELL)
            side = "BUY" if position_type.upper() == "LONG" or position_type.upper() == "BUY" else "SELL"
            
            # Calculate the quantity to buy/sell (amount divided by price)
            quantity = amount / price
            
            # Get symbol info to handle precision and step sizes
            symbol_info = self.client.get_symbol_info(symbol)
            filters = symbol_info["filters"]
            
            # Get precision for quantity (LOT_SIZE) and price (PRICE_FILTER)
            tick_size = next(filter for filter in filters if filter['filterType'] == 'PRICE_FILTER')['tickSize']
            step_size = next(filter for filter in filters if filter['filterType'] == 'LOT_SIZE')['stepSize']
            
            price_precision = self._get_precision_from_step(tick_size)
            quantity_precision = self._get_precision_from_step(step_size)
            
            # Round quantity and price to the correct precision
            quantity = float('{:.{}f}'.format(quantity, quantity_precision))
            price = float('{:.{}f}'.format(price, price_precision))
            
            # Set leverage
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            
            # Set margin type to ISOLATED if not already set
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
            except BinanceAPIException as e:
                if "No need to change margin type." not in str(e):
                    raise e
            
            # Place the limit order
            self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                quantity=quantity,
                price=price,
                timeInForce="GTC"
            )
            
        except BinanceAPIException as e:
            raise Exception(f"開 {position_type} 限價單失敗：{e}")


    def close_position(self, symbol, position_type):
        """平倉並取消相關止盈止損條件單"""
        try:
            symbol = self._modify_symbol_name(symbol)
            position = self.get_positions(symbol=symbol)
            
            
            if not position or position[0]["side"] != position_type:
                print("無可用持倉，跳過平倉操作。")
                return
            
            quantity = float(position[0]["notional"])
            quantity = quantity if position_type == "BUY" else -quantity
            
            # Get symbol info to handle precision and step sizes
            symbol_info = self.client.get_symbol_info(symbol)
            filters = symbol_info["filters"]
            
            # Get precision for quantity (LOT_SIZE) and price (PRICE_FILTER)
            step_size = next(filter for filter in filters if filter['filterType'] == 'LOT_SIZE')['stepSize']
            
            quantity_precision = self._get_precision_from_step(step_size)
            
            # Round quantity and price to the correct precision
            quantity = float('{:.{}f}'.format(quantity, quantity_precision))
            
            # 執行平倉
            side = "SELL" if (position_type == "long" or position_type == "BUY") else "BUY"
            self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity,
                reduceOnly=True
            )
        except BinanceAPIException as e:
            print(f"平倉失敗：{e}")
        
        try:
            # 取消相關訂單
            self._cancel_related_orders(symbol)
        except BinanceAPIException as e:
            raise Exception(f"平 {position_type} 倉失敗：{e}")
    
    def get_positions(self, symbol=None):
        """獲取指定交易對或全部持倉資訊"""
        try:
            positions = self.client.futures_position_information()
            symbol = self._modify_symbol_name(symbol) if symbol else None
            
            # add "side" to each position
            for pos in positions:
                pos["side"] = "BUY" if float(pos["positionAmt"]) > 0 else "SELL"
            
            if symbol:
                    return [pos for pos in positions if pos["symbol"] == symbol]
            else:
                    return positions
            
        except BinanceAPIException as e:
            if symbol:
                raise Exception(f"獲取 {symbol} 持倉失敗：{e}")
            else:
                raise Exception(f"獲取所有持倉失敗：{e}")
    
    def get_open_orders(self, symbol=None, type=None):
        """獲取指定交易對或全部的訂單"""
        try:
            if (symbol):
                symbol = self._modify_symbol_name(symbol)
                orders = self.client.futures_get_open_orders(symbol=symbol)
                
                if type:
                    orders = [order for order in orders if order["type"] == type]
                return orders
            else:
                orders = self.client.futures_get_open_orders()
                if type:
                    orders = [order for order in orders if order["type"] == type]
                return orders
            
        except BinanceAPIException as e:
            if symbol:
                raise Exception(f"獲取 {symbol} 訂單失敗：{e}")
            else:
                raise Exception(f"獲取所有訂單失敗：{e}")
    
    def fetch_usdt_balance(self):
        """獲取帳戶餘額資訊"""
        try:
            account_info = self.client.futures_account()
            for asset in account_info["assets"]:
                if asset["asset"] == "USDT":
                    return {
                        "free": float(asset["availableBalance"]), 
                        "used": float(asset["initialMargin"]),
                        "total": float(asset["walletBalance"])
                    }
            
            raise ValueError("USDT 資產不存在")
        
        except BinanceAPIException as e:
            print(f"獲取餘額失敗：{e}")
            self._log_error("global", "獲取餘額", e)
            return None

    def get_price(self, symbol):
        """獲取指定交易對的最新價格"""
        try:
            symbol = self._modify_symbol_name(symbol)
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        
        except BinanceAPIException as e:
            raise Exception(f"獲取 {symbol} 價格失敗：{e}")

    
    
    def cancel_order(self, symbol, type=None):
        """取消指定交易對的訂單"""
        try:
            symbol = self._modify_symbol_name(symbol)
            orders = self.get_open_orders(symbol=symbol, type=type)
            
            for order in orders:
                self.client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
                print(f"取消 {symbol} 訂單成功： {order['orderId']}")
        
        except BinanceAPIException as e:
            raise Exception(f"取消 {symbol} 訂單失敗：{e}")
    
    def get_historical_data(self, symbol, interval, limit, closed=True):
        """獲取歷史數據"""
        symbol = self._modify_symbol_name(symbol)
        try:
            if closed:
                limit += 1
            
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            if closed:
                klines = klines[:-1]  # 去除當前 K 線
            return klines
        
        except BinanceAPIException as e:
            raise Exception(f"獲取 {symbol} 歷史數據失敗：{e}")
    
    # 輔助方法 --------------------------------------------------
    def _cancel_related_orders(self, symbol):
        """取消 symbol 的所有止損和止盈訂單"""
        try:
            symbol = self._modify_symbol_name(symbol)
            for order in self.get_open_orders(symbol=symbol) or []:
                if order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                    self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                    print(f"取消 {symbol} {order['type']} 訂單成功： {order['orderId']}")
        except BinanceAPIException as e:
            print(f"取消 {symbol} 訂單失敗：{e}")

    def _modify_symbol_name(self, symbol):
        """將交易對名稱轉換為 Binance API 支援的格式"""
        return symbol.replace("/", "").upper()

    def _get_precision_from_step(self, step_str):
        """從 step_str 中獲取精度"""
        step_str = str(float(step_str))
        if '.' not in step_str:
            return 0
        decimal_part = step_str.split('.')[1]
        if decimal_part.replace('0', '') == '1':
            return decimal_part.find('1')
        return 0
