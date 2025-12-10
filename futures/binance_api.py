import os
import time
import requests
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN
from typing import Optional, List, Dict, Any, Tuple
from logging import getLogger

from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.enums import HistoricalKlinesType

from .base import AbstractFuturesAPI


# 定義用於識別止損止盈訂單的類型集合
CLOSING_ORDER_TYPES = {
    "STOP", "STOP_MARKET",
    "TAKE_PROFIT", "TAKE_PROFIT_MARKET",
    "TRAILING_STOP_MARKET"
}


class BinanceFutures(AbstractFuturesAPI):
    """
    Binance Futures 交易API封裝 class
    
    提供完整的幣安期貨交易功能，包括：
    - 市價與限價開倉
    - 止損止盈條件單設置
    - 倉位管理與平倉
    - 訂單管理
    - 資產查詢
    - 歷史數據獲取
    - 多餘訂單清理
    
    Features:
    - 統一的返回格式 {"success": bool, "action": str, "details": {...}, "error_message": str}
    - 自動精度處理，符合Binance API要求
    - 自動設置逐倉模式 (ISOLATED)
    - logger 只針對交易方法使用 (查詢方法不使用logger，直接拋出異常)
    
    Usage:
        api = BinanceFutures(api_key="your_key", api_secret="your_secret", logger=your_logger)
        result = api.place_market_order("BTCUSDT", "LONG", 10, 100.0, stop_loss_price=95000.0)
    """
    
    def __init__(self, api_key=None, api_secret=None, logger = None, env_path=".env"):
        """
        初始化 Binance Futures 交易類別

        Args:
            api_key (str, optional): Binance API Key，若不提供則從環境變數讀取
            api_secret (str, optional): Binance API Secret，若不提供則從環境變數讀取
            logger (Logger, optional): 日誌記錄器實例，若不提供則使用預設logger
            env_path (str, optional): 環境變數文件路徑，默認為 ".env"

        Raises:
            FileNotFoundError: 環境變數文件不存在
            ValueError: 環境變數文件格式錯誤或API憑證不完整
            PermissionError: 無法讀取環境變數文件
        """

        if logger is None:
            self.logger = getLogger(__name__)
        else:
            self.logger = logger

        # 追蹤已設置為 ISOLATED 模式的交易對
        self._isolated_symbols = set()

        if api_key and api_secret:
            self.binance_api_key = api_key
            self.binance_api_secret = api_secret
        else:
            self.logger.warning("No Binance API key or secret provided. Using environment variables.")
            if not os.path.exists(env_path):
                self.logger.error(f"Environment file {env_path} not found.")
                raise FileNotFoundError(f"Environment file {env_path} not found.")
            if not os.path.isfile(env_path):
                self.logger.error(f"{env_path} is not a file.")
                raise ValueError(f"{env_path} is not a file.")
            if not os.access(env_path, os.R_OK):
                self.logger.error(f"Cannot read environment file {env_path}.")
                raise PermissionError(f"Cannot read environment file {env_path}.")

            self.env = load_dotenv(env_path)
            self.binance_api_key = os.getenv("BINANCE_API_KEY")
            self.binance_api_secret = os.getenv("BINANCE_API_SECRET")

            if not self.binance_api_key or not self.binance_api_secret:
                self.logger.error("Binance API key or secret not found in environment variables.")
                raise ValueError("Binance API key or secret not found in environment variables.")

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

    def _set_isolated_margin(self, symbol: str) -> None:
        """
        設置交易對為 ISOLATED 保證金模式（僅在首次交易時執行）

        Args:
            symbol (str): 交易對名稱

        Note:
            - 只在該交易對首次交易時設置一次
            - 使用 _isolated_symbols 集合追蹤已設置的交易對
            - 避免重複設置導致 5 秒冷卻期問題
        """
        if symbol not in self._isolated_symbols:
            try:
                self.client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
                self._isolated_symbols.add(symbol)
                self.logger.info(f"{symbol} 已設置為 ISOLATED 保證金模式")
            except BinanceAPIException as e:
                if "No need to change margin type." in str(e):
                    # 已經是 ISOLATED 模式，記錄下來避免下次再嘗試
                    self._isolated_symbols.add(symbol)
                    self.logger.info(f"{symbol} 已經是 ISOLATED 保證金模式")
                else:
                    raise e
            print(f"{symbol} 設置為 ISOLATED 保證金模式，等待 7 秒以避免 API 請求過快...")
            time.sleep(7)  # 避免 API 請求過快
    
    # 交易方法 --------------------------------------------------
    def set_stop_loss_take_profit(self, symbol: str, side: str,
                                stop_loss_price: Optional[float] = None,
                                take_profit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        設置止損和止盈條件單

        Args:
            symbol (str): 交易對名稱
            side (str): 倉位方向 ("BUY"/"SELL" 或 "LONG"/"SHORT")
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格

        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": {
                    "symbol": str,
                    "side": str,
                    "stop_loss_price": str or None,
                    "take_profit_price": str or None,
                    "stop_loss_set": bool,
                    "take_profit_set": bool
                },
                "error_message": str (only when failed)
            }
        """
        symbol = self._modify_symbol_name(symbol)
        result = {
            "success": False,
            "action": f"Set stop-loss and take-profit orders for {symbol} {side} position",
            "details": {
                "symbol": symbol,
                "side": side,
                "stop_loss_price": stop_loss_price,
                "take_profit_price": take_profit_price
            }
        }

        try:
            # Get symbol info to handle precision and step sizes
            price_precision, _ = self._get_symbol_precision(symbol)

            # 止損單設置
            if stop_loss_price:
                # Round stop loss price to the correct precision
                processed_stop_loss_price = self._truncate_to_precision(stop_loss_price, price_precision)

                result["details"]["stop_loss_price"] = processed_stop_loss_price

                # Determine the side for stop loss order
                stop_side = "SELL" if side.upper() == "BUY" or side.upper() == "LONG" else "BUY"
                sl_info = self.client.futures_create_algo_order(
                    symbol=symbol,
                    side=stop_side,
                    type="STOP_MARKET",
                    triggerPrice=processed_stop_loss_price,
                    closePosition=True,
                    workingType='MARK_PRICE',
                    priceProtect=False
                )
                # print(f"設置 {symbol} {side} 止損單成功，止損價格：{processed_stop_loss_price}")
                self.logger.info(f"設置 {symbol} {side} 止損單成功，止損價格：{processed_stop_loss_price}，訂單ID：{sl_info.get('algoId')}")
                result["details"]["stop_loss_set"] = True
                result["details"]["stop_loss_algoId"] = sl_info.get("algoId")

            # 止盈單設置
            if take_profit_price:
                # Round take profit price to the correct precision
                processed_take_profit_price = self._truncate_to_precision(take_profit_price, price_precision)

                result["details"]["take_profit_price"] = processed_take_profit_price

                # Determine the side for take profit order
                tp_side = "SELL" if side.upper() == "BUY" or side.upper() == "LONG" else "BUY"
                tp_info = self.client.futures_create_algo_order(
                    symbol=symbol,
                    side=tp_side,
                    type="TAKE_PROFIT_MARKET",
                    triggerPrice=processed_take_profit_price,
                    closePosition=True,
                    workingType='MARK_PRICE',
                    priceProtect=False
                )
                # print(f"設置 {symbol} {side} 止盈單成功，止盈價格：{processed_take_profit_price}")
                self.logger.info(f"設置 {symbol} {side} 止盈單成功，止盈價格：{processed_take_profit_price}，訂單ID：{tp_info.get('algoId')}")
                result["details"]["take_profit_set"] = True
                result["details"]["take_profit_algoId"] = tp_info.get("algoId")
            
            result["success"] = True
            return result
                
        except BinanceAPIException as e:
            # print(f"{symbol} {side} 設置止損止盈單失敗：{e}")
            self.logger.error(f"{symbol} {side} 設置止損止盈單失敗：{e}")
            result["error_message"] = str(e)
            
            # 平倉
            self.close_position(symbol, "BUY" if side.upper() == "BUY" or side.upper() == "LONG" else "SELL")
            return result


    def place_market_order(self, symbol: str, position_type: str, leverage: int, amount: float, 
                          stop_loss_price: Optional[float] = None, 
                          take_profit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        市價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            leverage (int): 槓桿倍數
            amount (float): 交易金額 (USDT)
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": {
                    "symbol": str,
                    "position_type": str,
                    "leverage": int,
                    "amount": float,
                    "price": str,
                    "quantity": str,
                    "stop_loss_price": str or None,
                    "take_profit_price": str or None
                },
                "error_message": str (only when failed)
            }
            
        Note:
            - 自動設置為逐倉模式 (ISOLATED)
            - 若提供止損/止盈價格，會在開倉成功後自動設置相關條件單
            - 若止損/止盈設置失敗，會自動平倉並返回錯誤
        """
        result = {
            "success": False,
            "action": f"Place market {position_type} order for {symbol}",
            "details": {
                "symbol": symbol,
                "position_type": position_type,
                "leverage": leverage,
                "amount": amount,
                "stop_loss_price": stop_loss_price,
                "take_profit_price": take_profit_price
            }
        }
        
        try:
            symbol = self._modify_symbol_name(symbol)
            side = "BUY" if position_type.upper() == "LONG" or position_type.upper() == "BUY" else "SELL"
            
            # 取得價格並計算數量
            price = self.get_price(symbol)
            quantity = amount / price
            
            # Get symbol info to handle precision and step sizes
            price_precision, quantity_precision = self._get_symbol_precision(symbol)
            
            # 處理精度並更新到 details
            result["details"]["price"] = self._truncate_to_precision(price, price_precision)
            result["details"]["quantity"] = self._truncate_to_precision(quantity, quantity_precision)
            
            # 使用處理後的值
            quantity = result["details"]["quantity"]
            price = result["details"]["price"]
            
            # 設定槓桿
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # 設定保證金模式（僅在首次交易時）
            self._set_isolated_margin(symbol)

            # 市價開倉
            info = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity
            )
            
            # print(f"開 {position_type} 倉成功，數量：{quantity}，價格：{price}")
            self.logger.info(f"{symbol} 開 {position_type} 市價單成功，數量：{quantity}，價格：{price}，訂單ID：{info.get('orderId')}")
            result["orderId"] = info.get("orderId")
            
            # 設置止損止盈
            sl_tp_result = self.set_stop_loss_take_profit(symbol, side, stop_loss_price, take_profit_price)
            
            # 檢查止損止盈設置結果
            if not sl_tp_result["success"]:
                # 止損止盈設置失敗，拋出異常讓外層處理
                raise Exception(f"⚠️ {symbol} {position_type} 止盈止損設置失敗: {sl_tp_result.get('error_message', 'Unknown error')} 請確認是否需要手動平倉。")
            
            # 更新止損止盈價格到 details
            if stop_loss_price and "stop_loss_price" in sl_tp_result["details"]:
                result["details"]["stop_loss_price"] = sl_tp_result["details"]["stop_loss_price"]
            if take_profit_price and "take_profit_price" in sl_tp_result["details"]:
                result["details"]["take_profit_price"] = sl_tp_result["details"]["take_profit_price"]
            
            result["success"] = True
            return result
            
        except BinanceAPIException as e:
            self.logger.error(f"{symbol} 開 {position_type} 市價單失敗：{e}")
            result["error_message"] = str(e)
            return result


    def place_limit_order(self, symbol: str, position_type: str, price: float, leverage: int, amount: float) -> Dict[str, Any]:
        """
        限價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            price (float): 限價價格
            leverage (int): 槓桿倍數
            amount (float): 交易金額 (USDT)
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": {
                    "symbol": str,
                    "position_type": str,
                    "price": str,
                    "leverage": int,
                    "amount": float,
                    "quantity": str
                },
                "error_message": str (only when failed)
            }
            
        Note:
            - 自動設置為逐倉模式 (ISOLATED)
            - 訂單類型為 GTC (Good Till Cancelled)
            - 限價單不會自動設置止損/止盈，需要單獨調用相關方法
        """
        result = {
            "success": False,
            "action": f"Place limit {position_type} order for {symbol}",
            "details": {
                "symbol": symbol,
                "position_type": position_type,
                "price": price,
                "leverage": leverage,
                "amount": amount
            }
        }
        
        try:
            # Modify symbol name for API
            symbol = self._modify_symbol_name(symbol)
            
            # Determine the side (BUY or SELL)
            side = "BUY" if position_type.upper() == "LONG" or position_type.upper() == "BUY" else "SELL"
            
            # Calculate the quantity to buy/sell (amount divided by price)
            quantity = amount / price
            
            # Get symbol info to handle precision and step sizes
            price_precision, quantity_precision = self._get_symbol_precision(symbol)
            
            # 處理精度並更新到 details
            result["details"]["price"] = self._truncate_to_precision(price, price_precision)
            result["details"]["quantity"] = self._truncate_to_precision(quantity, quantity_precision)
            
            # 使用處理後的值
            quantity = result["details"]["quantity"]
            price = result["details"]["price"]
            
            # Set leverage
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # 設定保證金模式（僅在首次交易時）
            self._set_isolated_margin(symbol)

            # Place the limit order
            info = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="LIMIT",
                quantity=quantity,
                price=price,
                timeInForce="GTC"
            )
            
            self.logger.info(f"{symbol} 開 {position_type} 限價單成功，數量：{quantity}，價格：{price}，訂單ID：{info.get('orderId')}")
            
            result["orderId"] = info.get("orderId")
            result["success"] = True
            return result
            
        except BinanceAPIException as e:
            self.logger.error(f"{symbol} 開 {position_type} 限價單失敗：{e}")
            result["error_message"] = str(e)
            return result


    def close_position(self, symbol: str, position_type: Optional[str] = None) -> Dict[str, Any]:
        """
        平倉指定倉位並取消相關止盈止損條件單
        
        Args:
            symbol (str): 交易對名稱
            position_type (str, optional): 倉位類型 ("LONG"/"SHORT") 或 ("BUY"/"SELL")，若不提供則平所有持倉
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": {
                    "symbol": str,
                    "position_type": str,
                    "position_found": bool,
                    "orders_cancelled": bool  # 是否成功取消相關止盈止損訂單
                },
                "error_message": str (only when failed)
            }
            
        Note:
            - 若無對應持倉，將返回成功狀態但 position_found 為 False
            - 只有在完全沒有該symbol持倉時才會取消止盈止損相關訂單
            - 若平倉後仍有其他持倉，則不會取消止盈止損訂單
        """
        result = {
                "success": False,
                "action": f"Close {position_type or 'any'} position for {symbol}",
                "details": {"symbol": symbol, "position_type": position_type}
            }

        try:
            symbol = self._modify_symbol_name(symbol)
            position = self.get_positions(symbol=symbol)

            if not position or float(position[0]["positionAmt"]) == 0:
                # 無持倉，直接返回成功
                result["success"] = True
                result["details"]["position_found"] = False
                return result

            pos = position[0]
            amt = float(pos["positionAmt"])
            current_side = "BUY" if amt > 0 else "SELL"

            # 判斷是否符合要平的倉位類型
            if position_type:
                pt = position_type.strip().upper()
                if pt in ("LONG", "BUY") and current_side != "BUY":
                    # 要求平多倉但當前為空倉，無需平倉
                    result["success"] = True
                    result["details"]["position_found"] = False
                    return result
                elif pt in ("SHORT", "SELL") and current_side != "SELL":
                    # 要求平空倉但當前為多倉，無需平倉
                    result["success"] = True
                    result["details"]["position_found"] = False
                    return result
                # 其他值忽略，不影響平倉

            # 執行平倉
            qty = abs(amt)
            _, qty_precision = self._get_symbol_precision(symbol)
            qty = self._truncate_to_precision(qty, qty_precision)

            side = "SELL" if amt > 0 else "BUY"

            info = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=qty,
                reduceOnly=True
            )

            result["orderId"] = info.get("orderId")

        except BinanceAPIException as e:
            result["error_message"] = str(e)
            return result

        # 平倉後取消止盈止損
        try:
            new_pos = self.get_positions(symbol=symbol)
            if not new_pos or float(new_pos[0]["positionAmt"]) == 0: # 確認已無持倉
                self._cancel_related_orders(symbol)
                result["details"]["orders_cancelled"] = True
            else:
                result["details"]["orders_cancelled"] = False # 仍有持倉，不取消訂單

            result["success"] = True
            return result

        except BinanceAPIException as e:
            result["error_message"] = str(e)
            return result

    
    def cancel_order(self, symbol: str, type: Optional[str] = None) -> Dict[str, Any]:
        """
        取消訂單
        
        Args:
            symbol (str): 交易對名稱
            type (str, optional): 訂單類型
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": {
                    "symbol": str,
                    "type": str or None,
                    "cancelled_orders": list,
                    "cancelled_count": int
                },
                "error_message": str (only when failed)
            }
        """
        result = {
            "success": False,
            "action": f"Cancel {type or 'all'} orders for {symbol}",
            "details": {
                "symbol": symbol,
                "type": type
            }
        }
        
        try:
            symbol = self._modify_symbol_name(symbol)
            
            orders = self.get_open_orders(symbol=symbol, type=type)
            
            cancelled_orders = []
            
            for order in orders:
                
                algoId = order.get("algoId")
                orderId = order.get("orderId")
                
                self.client.futures_cancel_order(symbol=symbol, algoId=algoId, orderId=orderId)
                cancelled_orders.append(algoId or orderId)
            
            result["success"] = True
            result["details"]["cancelled_orders"] = cancelled_orders
            result["details"]["cancelled_count"] = len(cancelled_orders)
            return result
        
        except BinanceAPIException as e:
            self.logger.error(f"{symbol} 取消訂單失敗：{e}")
            result["error_message"] = str(e)
            return result
    
    
    def clean_orphan_orders(self) -> Dict[str, Any]:
        """
        清理多餘訂單 (沒有持倉卻遺留的止盈/止損類訂單)
        
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": {
                    "cleaned_symbols": list,
                    "cleaned_count": int
                },
                "error_message": str (only when failed)
            }
        """
        result = {
            "success": False,
            "action": "Clean orphaned orders",
            "details": {}
        }
        
        try:
            cleaned_symbols = set()
            for order in self.get_open_orders():
                
                od_type = order.get("type") or order.get("orderType")
                if od_type not in CLOSING_ORDER_TYPES: # 只處理止盈止損類訂單
                    continue
                
                symbol = order['symbol']
                if symbol in cleaned_symbols: # 已處理過該交易對，跳過
                    continue
                
                if not self.get_positions(symbol=symbol): # 若該交易對無持倉，則取消相關訂單。若持倉存在，則不取消
                    self._cancel_related_orders(symbol)
                
                cleaned_symbols.add(symbol)
            
            result["success"] = True
            result["details"]["cleaned_symbols"] = cleaned_symbols
            result["details"]["cleaned_count"] = len(cleaned_symbols)
            
            return result
            
        except Exception as e:
            # print(f"清理多餘訂單失敗: {e}")
            self.logger.error(f"清理多餘訂單失敗: {e}")
            result["error_message"] = str(e)
            return result
    
    
    
    
    
    # 獲取資料方法 --------------------------------------------------
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
            
            for pos in positions:
                amt = float(pos["positionAmt"])
                if amt > 0:
                    pos["side"] = "BUY"
                elif amt < 0:
                    pos["side"] = "SELL"
                else:
                    self.logger.warning(f"{pos['symbol']} 持倉數量為 0，標記為 NONE")
                    pos["side"] = "NONE"
            
            return [p for p in positions if symbol is None or p["symbol"] == symbol]
        
        except BinanceAPIException as e:
            raise Exception(f"獲取持倉失敗：{e}")
    
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
            
            normal_orders = self.client.futures_get_open_orders(symbol=symbol)  # 當前委託
            algo_orders = self.client.futures_get_open_algo_orders(symbol=symbol)  # 條件單
            orders = normal_orders + algo_orders
            
            if (type):
                orders = [
                    order for order in orders
                    if (order.get("type") or order.get("orderType")) == type
                ]
            
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
                "free": float,   # 可用餘額
                "used": float,   # 已用餘額 (初始保證金)
                "total": float   # 總餘額 (錢包餘額)
            }
            
        Raises:
            Exception: 獲取USDT餘額失敗時拋出異常
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
            raise Exception(f"獲取USDT餘額失敗：{e}")
    

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


    def check_symbol_availability(self, symbol: str) -> bool:
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


    def get_historical_data(
            self,
            symbol: str,
            interval: str,
            limit: Optional[int] = None,
            closed: bool = True,
            show: bool = False,
            since: Optional[int] = None
        ) -> List[List[Any]]:
        """
        獲取歷史K線數據

        Args:
            symbol (str): 交易對名稱
            interval (str): 時間間隔，如 "1m", "5m", "1h", "1d" 等
            limit (int, optional): 數量限制。若與 since 同時存在，則從 since 開始最多取 limit 根
            closed (bool, optional): 是否只獲取已關閉的K線。默認為True
            show (bool, optional): 是否顯示獲取進度。默認為False
            since (int, optional): 從這個時間戳（毫秒）開始取得K線資料

        Returns:
            list: K線數據列表，每個元素為包含 [開盤時間, 開盤價, 最高價, 最低價, 收盤價, 交易量, 收盤時間, ...] 的列表

        Raises:
            Exception: 獲取歷史數據失敗時拋出異常
            
        Note:
            - 自動驗證交易對是否為有效的永續合約
            - 當 show=True 時，進度信息會通過 print 輸出
            - 若 closed=True，將不包含當前未關閉的K線
            - 若 limit 與 since 同時提供，將從指定時間開始獲取最多 limit 根K線
        """
        symbol = self._modify_symbol_name(symbol)
        max_limit = 1000
        all_klines = []

        if not self.check_symbol_availability(symbol):
            raise Exception(f"{symbol} 不是有效的永續合約")

        try:
            if closed and not since and limit:
                limit += 1

            if since:
                fetch_limit = max_limit if limit is None else min(max_limit, limit)
                start_time = since

                while True:
                    if show:
                        print(f"Fetching klines from {start_time} for {symbol}...")

                    # klines = self.client.get_historical_klines(
                    #     symbol=symbol,
                    #     interval=interval,
                    #     limit=fetch_limit,
                    #     start_str=start_time,
                    #     klines_type=HistoricalKlinesType.FUTURES
                    # )
                    klines = self._get_historical_klines_with_rate_limit(
                        symbol=symbol,
                        interval=interval,
                        limit=fetch_limit,
                        start_str=start_time
                    )

                    if not klines:
                        break

                    all_klines.extend(klines)

                    if limit and len(all_klines) >= limit:
                        all_klines = all_klines[:limit]
                        break

                    if len(klines) < fetch_limit:
                        break  # 沒有更多資料了

                    start_time = klines[-1][0] + 1  # 下一次從最後一根之後開始

                if closed and all_klines and all_klines[-1][6] > int(time.time() * 1000):
                    all_klines = all_klines[:-1]

                return all_klines

            # 沒有 since，沿用舊邏輯往回抓
            if closed and limit:
                limit += 1
            remaining = limit

            while remaining > 0:
                if show:
                    print(f"Fetching {remaining} OHLCV data for {symbol}...")

                fetch_limit = min(max_limit, remaining)

                if all_klines:
                    time_diff = all_klines[1][0] - all_klines[0][0]
                    since_ts = all_klines[0][0] - time_diff * fetch_limit
                    # klines = self.client.get_historical_klines(
                    #     symbol=symbol,
                    #     interval=interval,
                    #     limit=fetch_limit,
                    #     start_str=since_ts,
                    #     klines_type=HistoricalKlinesType.FUTURES
                    # )
                    klines = self._get_historical_klines_with_rate_limit(
                        symbol=symbol,
                        interval=interval,
                        limit=fetch_limit,
                        start_str=since_ts
                    )
                else:
                    # klines = self.client.get_historical_klines(
                    #     symbol=symbol,
                    #     interval=interval,
                    #     limit=fetch_limit,
                    #     klines_type=HistoricalKlinesType.FUTURES
                    # )
                    klines = self._get_historical_klines_with_rate_limit(
                        symbol=symbol,
                        interval=interval,
                        limit=fetch_limit
                    )

                if not klines:
                    break

                all_klines = klines + all_klines
                remaining -= fetch_limit

                if len(set([x[0] for x in all_klines])) != len(all_klines):
                    raise Exception(f"Duplicate timestamp found in fetched klines for {symbol} with interval {interval}, limit {limit}")

                if show:
                    print(f"Fetched {len(all_klines)} OHLCV data for {symbol}, remaining: {remaining}")

            if not all_klines or (limit and len(all_klines) < limit):
                raise Exception(f"獲取 {symbol} 歷史數據失敗，數據不足：{len(all_klines)} < {limit}")

            if closed:
                all_klines = all_klines[:-1]

            return all_klines

        except BinanceAPIException as e:
            raise Exception(f"獲取 {symbol} 歷史數據失敗：{e}")
    
    
    
    
    
    # 輔助方法 --------------------------------------------------
    def _cancel_related_orders(self, symbol: str) -> None:
        """
        取消 symbol 的所有止損和止盈訂單
        
        Args:
            symbol (str): 交易對名稱
        
        Raises:
            BinanceAPIException: 取消訂單失敗時拋出異常
        
        Note:
            - 只取消 STOP_MARKET 和 TAKE_PROFIT_MARKET 類型的訂單
            - 成功取消的訂單會記錄到 info 級別日誌
        """
        try:
            symbol = self._modify_symbol_name(symbol)
            
            for order in self.get_open_orders(symbol=symbol) or []:
                
                if order.get("type") in CLOSING_ORDER_TYPES: # 如果有 'type' 欄位，代表是一般訂單
                    self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
                    self.logger.info(f"取消 {symbol} {order['type']} 訂單成功： {order['orderId']}")
                
                elif order.get("orderType") in CLOSING_ORDER_TYPES: # 如果有 'orderType' 欄位，代表是條件單
                    self.client.futures_cancel_order(symbol=symbol, algoId=order['algoId'])
                    self.logger.info(f"取消 {symbol} {order['orderType']} 條件單成功： {order['algoId']}")
                
        except BinanceAPIException as e:
            # print(f"取消 {symbol} 訂單失敗：{e}")
            self.logger.error(f"取消 {symbol} 止盈止損訂單失敗：{e}")
            raise e


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
    
    
    def _get_historical_klines_with_rate_limit(
            self,
            symbol: str,
            interval: str,
            limit: Optional[int] = None,
            start_str: Optional[int] = None
        ) -> List[List[Any]]:
        """
        獲取歷史K線數據，處理速率限制
        
        Args:
            symbol (str): 交易對名稱
            interval (str): 時間間隔
            limit (int, optional): 數量限制
            start_str (int, optional): 開始時間戳（毫秒）
            
        Returns:
            list: K線數據列表
        """
        
        params = {
            "symbol": symbol,
            "interval": interval
        }
        
        if limit:
            params["limit"] = limit
        if start_str:
            params["startTime"] = start_str
        
        response = requests.get(
            f"https://fapi.binance.com/fapi/v1/klines",
            params=params
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            retry_after = int(response.headers.get("retry-after", "1")) + 1
            self.logger.warning(f"Rate limit exceeded when fetching klines for {symbol}. Retrying after {retry_after} seconds.")
            time.sleep(retry_after)
            return self._get_historical_klines_with_rate_limit(
                symbol,
                interval,
                limit,
                start_str
            )
        else:
            self.logger.error(f"Failed to fetch klines for {symbol}. Status code: {response.status_code}, Response: {response.text}")
            raise Exception(f"Failed to fetch klines for {symbol}. Status code: {response.status_code}")