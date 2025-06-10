import os
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.enums import HistoricalKlinesType
from typing import Optional, List, Dict, Union, Any, Tuple

from .base import AbstractFuturesAPI

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
            
            # Get symbol info to handle precision and step sizes
            price_precision, quantity_precision = self._get_symbol_precision(symbol)
            
            # 止損單設置
            if stop_loss_price:
                
                # Round stop loss price and quantity to the correct precision
                stop_loss_price = self._truncate_to_precision(stop_loss_price, price_precision)
                quantity = self._truncate_to_precision(quantity, quantity_precision)
                
                # Determine the side for stop loss order
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
                
                # Round take profit price and quantity to the correct precision
                take_profit_price = self._truncate_to_precision(take_profit_price, price_precision)
                quantity = self._truncate_to_precision(quantity, quantity_precision)
                
                # Determine the side for take profit order
                tp_side = "SELL" if side.upper() == "BUY" or side == "LONG" else "BUY"
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp_side,
                    type="TAKE_PROFIT_MARKET",
                    quantity=str(quantity),
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
            price_precision, quantity_precision = self._get_symbol_precision(symbol)
            
            # Round quantity and price to the correct precision
            quantity = self._truncate_to_precision(quantity, quantity_precision)
            price = self._truncate_to_precision(price, price_precision)
            
            
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
            price_precision, quantity_precision = self._get_symbol_precision(symbol)
            
            # Round quantity and price to the correct precision
            quantity = self._truncate_to_precision(quantity, quantity_precision)
            price = self._truncate_to_precision(price, price_precision)
            
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
            quantity = self._truncate_to_precision(quantity, quantity_precision)
            
            
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

    
    
    def get_historical_data(self, symbol: str, interval: str, limit: int, closed: bool = True, show=False) -> List[List[Any]]:
        """
        獲取歷史K線數據
        
        Args:
            symbol (str): 交易對名稱
            interval (str): 時間間隔，如 "1m", "5m", "1h", "1d" 等
            limit (int): 數量限制
            closed (bool, optional): 是否只獲取已關閉的K線。默認為True
            show (bool, optional): 是否顯示獲取進度。默認為False
            
        Returns:
            list: K線數據列表
            
        Raises:
            Exception: 獲取歷史數據失敗時拋出異常
        """
        symbol = self._modify_symbol_name(symbol)
        max_limit = 1000  # Binance API 單次請求上限
        all_klines = []
        
        if not self._check_symbol_availability(symbol):
            raise Exception(f"{symbol} 不是有效的永續合約")
        
        try:
            if (closed):
                limit += 1
            
            remaining = limit
            
            while remaining > 0:
                
                if show:
                    print(f"Fetching {remaining} OHLCV data for {symbol}...")
                
                fetch_limit = min(max_limit, remaining)
                
                if all_klines:
                    time_diff = all_klines[1][0] - all_klines[0][0]
                    since = all_klines[0][0] - time_diff * fetch_limit
                    
                    klines = self.client.get_historical_klines(symbol=symbol, interval=interval, limit=fetch_limit, start_str=since, klines_type=HistoricalKlinesType.FUTURES)
                else:
                    klines = self.client.get_historical_klines(symbol=symbol, interval=interval, limit=fetch_limit, klines_type=HistoricalKlinesType.FUTURES)
            
                if not klines:
                    break
                
                all_klines = klines + all_klines
                remaining -= fetch_limit
                
                if len(set([x[0] for x in all_klines])) != len(all_klines):
                    print("Duplicate timestamps found, stopping fetch.")
                    raise Exception("Duplicate timestamp found")
                
                if show:
                    print(f"Fetched {len(all_klines)} OHLCV data for {symbol}, remaining: {remaining}")
            
            if not all_klines or len(all_klines) < limit:
                print(f"獲取 {symbol} 歷史數據失敗，數據不足：{len(all_klines)} < {limit}")
                raise Exception(f"獲取 {symbol} 歷史數據失敗，數據不足：{len(all_klines)} < {limit}")
            
            if (closed):
                all_klines = all_klines[:-1]  # 去除當前 K 線
            
            return all_klines
        
        except BinanceAPIException as e:
            raise Exception(f"獲取 {symbol} 歷史數據失敗：{e}")
    
    
    def clean_orphan_orders(self) -> None:
        """
        清理多餘訂單 (已觸發止損或止盈反向訂單可能會被留下)
        """
        
        for order in self.get_open_orders():
            symbol = order['symbol']
            # 要排除 限價單
            if order['type'] == 'limit':
                continue
            if not self.get_positions(symbol=symbol):
                self._cancel_related_orders(symbol)
    
    
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

    @staticmethod
    def _get_precision_from_step(step_str: str) -> int:
        """
        從 tick_size 或 step_size 中獲取精度（有效的小數位數）
        
        Args:
            step_str (str): 如 "0.00001000" 或 "1.00000000"
            
        Returns:
            int: 精度值（幾位小數）
        """
        d = Decimal(step_str)
        d_normalized = d.normalize() 
        
        if d_normalized == d_normalized.to_integral():
            return 0 # 是整數，不需要精度
        
        return abs(d_normalized.as_tuple().exponent)

    @staticmethod
    def _truncate_to_precision(value: float, precision: int) -> str:
        """
        把浮點數 value 截斷到指定精度，並轉成字串，避免 Binance 報錯。
        """
        format_str = '1.' + '0' * precision  # e.g., '1.00000'
        return str(Decimal(str(value)).quantize(Decimal(format_str), rounding=ROUND_DOWN))

    def _get_symbol_precision(self, symbol: str) -> Tuple[int, int]:
        """
        獲取交易對的價格和數量精度
        
        Args:
            symbol (str): 交易對名稱
            
        Returns:
            tuple: (價格精度, 數量精度)
        """
        
        all_symbols_info = self.client.futures_exchange_info()["symbols"]
        symbol_info = next((s for s in all_symbols_info if s['symbol'] == symbol), None)
        
        if not symbol_info:
            raise ValueError(f"{symbol} 不存在或不是有效的永續合約")
        
        filters = symbol_info["filters"]
        
        tick_size = next((f['tickSize'] for f in filters if f['filterType'] == 'PRICE_FILTER'), None)
        step_size = next((f['stepSize'] for f in filters if f['filterType'] == 'LOT_SIZE'), None)
        
        price_precision = self._get_precision_from_step(tick_size)
        quantity_precision = self._get_precision_from_step(step_size)
        
        return price_precision, quantity_precision
    
    def _check_symbol_availability(self, symbol: str) -> bool:
        """
        檢查交易對是否為有效的永續合約
        Args:
            symbol (str): 交易對名稱
        Returns:
            bool: 如果是有效的永續合約則返回 True，否則返回 False
        """
        info = self.client.futures_exchange_info()
        valid_futures = {
            sym['symbol']
            for sym in info['symbols']
            if sym['contractType'] == 'PERPETUAL' and sym['status'] == 'TRADING'
        }
        return symbol in valid_futures