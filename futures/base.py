from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Union, Any

class AbstractFuturesAPI(ABC):
    """
    抽象基礎類別，為期貨交易定義標準介面。
    所有具體交易所實現 (如 Binance, Bybit 等) 應該繼承此類別。
    """
    
    @abstractmethod
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
                "details": dict,
                "error_message": str (only when failed)
            }
        """
        pass
    
    @abstractmethod
    def place_limit_order(self, symbol: str, position_type: str, price: float, leverage: int, amount: float) -> Dict[str, Any]:
        """
        限價開倉交易
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            price (float): 限價
            leverage (int): 槓桿倍數
            amount (float): 交易金額 (USDT)
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": dict,
                "error_message": str (only when failed)
            }
        """
        pass
    
    @abstractmethod
    def close_position(self, symbol: str, position_type: str) -> Dict[str, Any]:
        """
        平倉指定倉位
        
        Args:
            symbol (str): 交易對名稱
            position_type (str): 倉位類型 ("LONG"/"SHORT")
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": dict,
                "error_message": str (only when failed)
            }
        """
        pass
    
    @abstractmethod
    def set_stop_loss_take_profit(self, symbol: str, side: str, quantity: float, 
                                 stop_loss_price: Optional[float] = None, 
                                 take_profit_price: Optional[float] = None) -> Dict[str, Any]:
        """
        設置止損和止盈
        
        Args:
            symbol (str): 交易對名稱
            side (str): 倉位方向
            quantity (float): 交易數量
            stop_loss_price (float, optional): 止損價格
            take_profit_price (float, optional): 止盈價格
            
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": dict,
                "error_message": str (only when failed)
            }
        """
        pass
    
    @abstractmethod
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
                "details": dict,
                "error_message": str (only when failed)
            }
        """
        pass
    
    @abstractmethod
    def clean_orphan_orders(self) -> Dict[str, Any]:
        """
        清理多餘訂單
        
        Returns:
            dict: 操作結果
            {
                "success": bool,
                "action": str,
                "details": dict,
                "error_message": str (only when failed)
            }
        """
        pass
    
    @abstractmethod
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        獲取持倉資訊
        
        Args:
            symbol (str, optional): 交易對名稱，若不指定則獲取所有持倉
        Returns:
            list: 持倉資訊
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None, type: Optional[str] = None) -> List[Dict[str, Any]]:
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
        """
        pass
    
    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """
        獲取當前價格
        
        Args:
            symbol (str): 交易對名稱
        Returns:
            float: 當前價格
        """
        pass
    
    @abstractmethod
    def check_symbol_availability(self, symbol: str) -> bool:
        """
        檢查交易對是否為有效的永續合約
        
        Args:
            symbol (str): 交易對名稱
        Returns:
            bool: 如果是有效的永續合約則返回 True，否則返回 False
        """
        pass

    @abstractmethod
    def get_historical_data(self, symbol: str, interval: str, limit: Optional[int] = None, 
                           closed: bool = True, show: bool = False, 
                           since: Optional[int] = None) -> List[List[Any]]:
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
            list: K線數據列表
        """
        pass
