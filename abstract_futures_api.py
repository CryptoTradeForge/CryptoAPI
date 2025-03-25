from abc import ABC, abstractmethod

class AbstractFuturesAPI(ABC):
    """
    抽象基礎類別，為期貨交易定義標準介面。
    所有具體交易所實現 (如 Binance, Bybit 等) 應該繼承此類別。
    """
    
    @abstractmethod
    def place_market_order(self, symbol, position_type, amount, leverage, stop_loss_price=None, take_profit_price=None):
        """
        市價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            amount (float): 交易金額 (USDT)
            leverage (int): 槓桿倍數
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格
        """
        pass
    
    @abstractmethod
    def place_limit_order(self, symbol, position_type, amount, price, leverage):
        """
        限價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            amount (float): 交易金額 (USDT)
            price (float): 限價
            leverage (int): 槓桿倍數
        """
        pass
    
    @abstractmethod
    def close_position(self, symbol, position_type):
        """
        平倉指定倉位
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
        """
        pass
    
    @abstractmethod
    def set_stop_loss_take_profit(self, symbol, side, amount, stop_loss_price=None, take_profit_price=None):
        """
        設置止損和止盈
        
        Args:
            symbol (str): 交易對名稱
            side (str): 倉位方向
            amount (float): 交易金額 (USDT)
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格
        """
        pass
    
    @abstractmethod
    def get_positions(self, symbol=None):
        """
        獲取持倉資訊
        
        Args:
            symbol (str, optional): 交易對名稱，若不指定則獲取所有持倉
            
        Returns:
            list: 持倉資訊
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol=None, type=None):
        """
        獲取未成交訂單
        
        Args:
            symbol (str, optional): 交易對名稱
            type (str, optional): 訂單類型
            
        Returns:
            list: 訂單列表
        """
        pass
    
    @abstractmethod
    def fetch_usdt_balance(self):
        """
        獲取USDT餘額
        
        Returns:
            dict: 包含可用餘額、已用餘額和總餘額的字典
        """
        pass
    
    @abstractmethod
    def get_price(self, symbol):
        """
        獲取當前價格
        
        Args:
            symbol (str): 交易對名稱
            
        Returns:
            float: 當前價格
        """
        pass
    
    @abstractmethod
    def cancel_order(self, symbol, type=None):
        """
        取消訂單
        
        Args:
            symbol (str): 交易對名稱
            type (str, optional): 訂單類型
        """
        pass
    
    @abstractmethod
    def get_historical_data(self, symbol, interval, limit, closed=True):
        """
        獲取歷史K線數據
        
        Args:
            symbol (str): 交易對名稱
            interval (str): 時間間隔
            limit (int): 數量限制
            closed (bool): 是否只獲取已關閉的K線
            
        Returns:
            list: K線數據列表
        """
        pass
