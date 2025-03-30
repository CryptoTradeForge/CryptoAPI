import os
import time
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException
from futures.base import AbstractFuturesAPI
from typing import Optional, List, Dict, Union, Any, Tuple

class BinanceFutures(AbstractFuturesAPI):
    def __init__(self, env_path: str = ".env"):
        """
        初始化 Binance Futures 交易類別
        
        Args:
            env_path (str, optional): 環境變數文件路徑. 默認值為 ".env"
        """
        
        self.env_path = env_path
        self.env = load_dotenv(self.env_path)
        self.binance_api_key = os.getenv("BINANCE_API_KEY")
        self.binance_api_secret = os.getenv("BINANCE_API_SECRET")
        self._initialize_client()

    def _initialize_client(self) -> None:
        """
        初始化 Binance 客戶端
        
        用從環境變數獲取的API key和secret來創建Binance客戶端實例
        """
        self.client = Client(
            api_key=self.binance_api_key,
            api_secret=self.binance_api_secret,
        )
        self.client.synced = True

    def set_stop_loss_take_profit(self, symbol: str, side: str, quantity: float, 
                                stop_loss_price: Optional[float] = None, 
                                take_profit_price: Optional[float] = None) -> None:
        """
        設置止損和止盈條件單
        
        Args:
            symbol (str): 交易對名稱
            side (str): 倉位方向 ("BUY"/"SELL" 或 "LONG"/"SHORT")
            quantity (float): 交易數量
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格
            
        Raises:
            Exception: 設置止損止盈單失敗時拋出異常
        """
        symbol = self._modify_symbol_name(symbol)
        try:
            # 止損單設置
            if stop_loss_price:
                stop_side = "SELL" if side.upper() == "BUY" or side == "LONG" else "BUY"
                self.client.futures_create_order(
                    symbol=symbol,
                    side=stop_side,
                    type="STOP_MARKET",
                    quantity=quantity,
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
                    quantity=quantity,
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


    def place_market_order(self, symbol: str, position_type: str, leverage: int, amount: float, 
                          stop_loss_price: Optional[float] = None, 
                          take_profit_price: Optional[float] = None) -> None:
        """
        市價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            leverage (int): 槓桿倍數
            amount (float): 交易金額 (USDT)
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格
            
        Raises:
            Exception: 開倉失敗時拋出異常
        """
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
            self.set_stop_loss_take_profit(symbol, side, quantity, stop_loss_price, take_profit_price)
            
        except BinanceAPIException as e:
            raise Exception(f"開 {position_type} 市價單失敗：{e}")


    def place_limit_order(self, symbol: str, position_type: str, price: float, leverage: int, amount: float) -> None:
        """
        限價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            price (float): 限價
            leverage (int): 槓桿倍數
            amount (float): 交易金額 (USDT)
            
        Raises:
            Exception: 開倉失敗時拋出異常
        """
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


    def close_position(self, symbol: str, position_type: str) -> None:
        """
        平倉指定倉位並取消相關止盈止損條件單
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            
        Raises:
            Exception: 平倉失敗時拋出異常
        """
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
    
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        獲取持倉資訊
        
        Args:
            symbol (str, optional): 交易對名稱，若不指定則獲取所有持倉
            
        Returns:
            list: 持倉資訊列表
            
        Raises:
            Exception: 獲取持倉失敗時拋出異常
        """
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
    
    def get_open_orders(self, symbol: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        獲取未成交訂單
        
        Args:
            symbol (str, optional): 交易對名稱
            type (str, optional): 訂單類型
            
        Returns:
            list: 訂單列表
            
        Raises:
            Exception: 獲取訂單失敗時拋出異常
        """
        try:
            
            if (symbol):
                symbol = self._modify_symbol_name(symbol)
                orders = self.client.futures_get_open_orders(symbol=symbol)
                
                if (type):
                    orders = [order for order in orders if order["type"] == type]
                return orders
            else:
                orders = self.client.futures_get_open_orders()
                if (type):
                    orders = [order for order in orders if order["type"] == type]
                return orders
            
        except BinanceAPIException as e:
            if (symbol):
                raise Exception(f"獲取 {symbol} 訂單失敗：{e}")
            else:
                raise Exception(f"獲取所有訂單失敗：{e}")
    
    def fetch_usdt_balance(self) -> Optional[Dict[str, float]]:
        """
        獲取USDT餘額
        
        Returns:
            dict: 包含可用餘額、已用餘額和總餘額的字典
            {
                "free": float, # 可用餘額
                "used": float, # 已用餘額
                "total": float # 總餘額
            }
            
        Raises:
            ValueError: USDT資產不存在時拋出
            BinanceAPIException: API調用失敗時捕獲
        """
        try:
            
            account_info = self.client.futures_account()
            for asset in account_info["assets"]:
                if (asset["asset"] == "USDT"):
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

    def get_price(self, symbol: str) -> float:
        """
        獲取當前價格
        
        Args:
            symbol (str): 交易對名稱
            
        Returns:
            float: 當前價格
            
        Raises:
            Exception: 獲取價格失敗時拋出異常
        """
        try:
            
            symbol = self._modify_symbol_name(symbol)
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        
        except BinanceAPIException as e:
            raise Exception(f"獲取 {symbol} 價格失敗：{e}")

    
    
    def cancel_order(self, symbol: str, type: Optional[str] = None) -> None:
        """
        取消訂單
        
        Args:
            symbol (str): 交易對名稱
            type (str, optional): 訂單類型
            
        Raises:
            Exception: 取消訂單失敗時拋出異常
        """
        try:
            symbol = self._modify_symbol_name(symbol)
            orders = self.get_open_orders(symbol=symbol, type=type)
            
            
            for order in orders:
                self.client.futures_cancel_order(symbol=symbol, orderId=order["orderId"])
                print(f"取消 {symbol} {type} 訂單成功： {order['orderId']}")
        
        except BinanceAPIException as e:
            raise Exception(f"取消 {symbol} 訂單失敗：{e}")
    
    def get_historical_data(self, symbol: str, interval: str, limit: int, closed: bool = True) -> List[List[Any]]:
        """
        獲取歷史K線數據
        
        Args:
            symbol (str): 交易對名稱
            interval (str): 時間間隔，如 "1m", "5m", "1h", "1d" 等
            limit (int): 數量限制
            closed (bool, optional): 是否只獲取已關閉的K線。默認為True
            
        Returns:
            list: K線數據列表
            
        Raises:
            Exception: 獲取歷史數據失敗時拋出異常
        """
        symbol = self._modify_symbol_name(symbol)
        try:
            if (closed):
                limit += 1
            
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            if (closed):
                klines = klines[:-1]  # 去除當前 K 線
            return klines
        
        except BinanceAPIException as e:
            raise Exception(f"獲取 {symbol} 歷史數據失敗：{e}")
    
    # 輔助方法 --------------------------------------------------
    def _cancel_related_orders(self, symbol: str) -> None:
        """
        取消 symbol 的所有止損和止盈訂單
        
        Args:
            symbol (str): 交易對名稱
            
        Raises:
            BinanceAPIException: 取消訂單失敗時捕獲但不拋出
        """
        try:
            symbol = self._modify_symbol_name(symbol)
            for order in self.get_open_orders(symbol=symbol) or []:
                if (order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']):
                    self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                    print(f"取消 {symbol} {order['type']} 訂單成功： {order['orderId']}")
        except BinanceAPIException as e:
            print(f"取消 {symbol} 訂單失敗：{e}")

    def _modify_symbol_name(self, symbol: str) -> str:
        """
        將交易對名稱轉換為 Binance API 支援的格式
        
        Args:
            symbol (str): 原始交易對名稱
            
        Returns:
            str: 轉換後的交易對名稱
        """
        return symbol.replace("/", "").upper()

    def _get_precision_from_step(self, step_str: str) -> int:
        """
        從 step_str 中獲取精度
        
        Args:
            step_str (str): 步長字符串
            
        Returns:
            int: 精度值
        """
        step_str = str(float(step_str))
        if ('.' not in step_str):
            return 0
        decimal_part = step_str.split('.')[1]
        if (decimal_part.replace('0', '') == '1'):
            return decimal_part.find('1')
        return 0
