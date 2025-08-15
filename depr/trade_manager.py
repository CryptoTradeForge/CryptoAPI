import json

class TradeManager():
    def __init__(self, client, limit_sltp_rec_path= "limit_sltp_rec.json"):
        """初始化 Futures 的附加功能類別"""
        self.client = client
        self.limit_sltp_rec_path = limit_sltp_rec_path

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
        # 讀取已有的記錄
        try:
            with open(self.limit_sltp_rec_path, 'r') as f:
                limit_sltp_rec = json.load(f)
        except FileNotFoundError:
            limit_sltp_rec = {}
        
        # 更新記錄
        limit_sltp_rec[symbol] = {
            'side': side,
            'stop_loss_price': stop_loss_price, 
            'take_profit_price': take_profit_price
            }
        
        # 寫入文件
        with open(self.limit_sltp_rec_path, 'w') as f:
            json.dump(limit_sltp_rec, f, indent=4)
    
    def check_limit_status(self):
        """檢查限價單是否成交，如果成交則設置止損和止盈"""
        try:
            with open(self.limit_sltp_rec_path, 'r') as f:
                limit_sltp_rec = json.load(f)
        except FileNotFoundError:
            return

        to_del = []  # 用於記錄已處理的訂單
        for symbol, sltp_data in limit_sltp_rec.items():
            # 獲取當前持倉
            positions = self.client.get_positions(symbol)
            if not positions:
                print(f"No position found for symbol {symbol}, skipping...")
                continue
            
            # 檢查是否有止損或止盈訂單
            orders = self.client.get_open_orders(symbol)
            if any(order['type'] == 'STOP_MARKET' for order in orders) and sltp_data['stop_loss_price']:
                self.client.cancel_order(symbol, type='STOP_MARKET')
            if any(order['type'] == 'TAKE_PROFIT_MARKET' for order in orders) and sltp_data['take_profit_price']:
                self.client.cancel_order(symbol, type='TAKE_PROFIT_MARKET')
            
            quantity = abs(float(positions[0]['positionAmt']))
            self.client.set_stop_loss_take_profit(symbol, sltp_data['side'], quantity, stop_loss_price=sltp_data['stop_loss_price'], take_profit_price=sltp_data['take_profit_price'])
            
            to_del.append(symbol)
        
        # 刪除已處理的訂單
        for symbol in to_del:
            del limit_sltp_rec[symbol]
       
        # 寫入文件
        with open(self.limit_sltp_rec_path, 'w') as f:
            json.dump(limit_sltp_rec, f)
            
                
    
    
    