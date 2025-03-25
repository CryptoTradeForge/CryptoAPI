
class TradeManager():
    def __init__(self, future_client):
        """初始化 Binance 附加功能類別"""
        self.future_client = future_client

    def clean_redundant_orders(self):
        """清理多餘止損和止盈訂單"""
        pass
        
    def record_limit_sltp(self, symbol, side, stop_loss_price=None, take_profit_price=None):
        """記錄限價單的止損和止盈價格，待訂單成交後設置"""
        pass
    
    def check_limit_status(self):
        """檢查限價單是否成交，如果成交則設置止損和止盈"""
        pass
    
    def adjust_stop_loss(self, symbol, side, new_stop_loss_price):
        """調整止損價格 (先取消原有止損單，再設置新的止損單)"""
        pass
    
    