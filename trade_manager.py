
class TradeManager():
    def __init__(self, client):
        """初始化 Futures 的附加功能類別"""
        self.client = client

    def clean_redundant_orders(self):
        """清理多餘止損和止盈訂單"""
        # 獲取所有訂單
        open_orders = self.client.get_open_orders()
        # 獲取所有持倉
        positions = self.client.get_positions()
        pos_symbols = [pos['symbol'] for pos in positions]
        
        # 遍歷所有訂單，刪除不需要的止損和止盈訂單
        for order in open_orders:
            if order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET'] and order['symbol'] not in pos_symbols:
                self.client.cancel_order(order['symbol'], order['type'])
                
    
    def adjust_stop_loss(self, symbol, side, new_stop_loss_price):
        """調整止損價格 (先取消原有止損單，再設置新的止損單)"""
        # 獲取當前持倉
        positions = self.client.get_positions(symbol)
        if not positions:
            raise ValueError(f"No position found for symbol {symbol}")

        # 獲取當前止損單
        stop_loss_order = self.client.get_open_orders(symbol, type='STOP_MARKET')
        if stop_loss_order:
            # 取消原有止損單
            self.client.cancel_order(symbol, type='STOP_MARKET')

        # 設置新的止損單
        quantity = abs(float(positions[0]['positionAmt']))
        self.client.set_stop_loss_take_profit(symbol, side, quantity, stop_loss_price=new_stop_loss_price)
    
    
    def record_limit_sltp(self, symbol, side, stop_loss_price=None, take_profit_price=None):
        """記錄限價單的止損和止盈價格，待訂單成交後設置"""
        pass
    
    def check_limit_status(self):
        """檢查限價單是否成交，如果成交則設置止損和止盈"""
        pass
    
    
    
    