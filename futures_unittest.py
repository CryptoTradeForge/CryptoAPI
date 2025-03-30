import unittest
import logging
import warnings
from futures.binance_api import BinanceFutures

# Setting up basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestFuturesAPI")

class TestFuturesAPI(unittest.TestCase):
    # Default trading pair - can be modified through constructor
    SYMBOL = "ETHUSDT"
    
    def __init__(self, future_client, methodName='runTest', symbol=None):
        """Initialize the test case with optional custom symbol"""
        super().__init__(methodName)
        self.symbol = symbol or self.SYMBOL
        self.future_client = future_client
        
    def setUp(self):
        """Setup before each test case"""
        logger.info(f"🔧 Setting up test environment for {self.symbol}")
        warnings.simplefilter("ignore", category=ResourceWarning)  # Ignoring ResourceWarning
        
    def tearDown(self):
        """Cleanup after each test case"""
        pass
    
    def test_get_historical_data(self):
        """Test historical data retrieval functionality"""
        interval = "15m"
        limit = 10
        
        try:
            logger.info(f"📊 Testing historical data retrieval: {self.symbol}, {interval}, limit: {limit}")
            klines = self.future_client.get_historical_data(self.symbol, interval, limit)
            
            self.assertEqual(len(klines), limit, f"Should return {limit} data points")
            self.assertIsInstance(klines, list, "Return value should be a list")
            
            if (klines):
                first_kline = klines[0]
                self.assertIsInstance(first_kline, list, "K-line data should be a list")
                logger.info("✅ Historical data retrieval test passed")
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}")
            raise

    def test_fetch_usdt_balance(self):
        """Test USDT balance retrieval functionality"""
        try:
            logger.info("💰 Testing USDT balance retrieval")
            balance = self.future_client.fetch_usdt_balance()
            
            self.assertIsInstance(balance, dict, "Return value should be a dictionary")
            self.assertIn("free", balance, "Should include available balance")
            self.assertIn("used", balance, "Should include used balance")
            self.assertIn("total", balance, "Should include total balance")
            logger.info("✅ USDT balance retrieval test passed")
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}")
            raise
    
    def test_limit_order_workflow(self):
        """Test limit order workflow: Get price, place limit order, query order, cancel order"""
        side = "BUY"
        amount = 50
        leverage = 5
        
        try:
            logger.info(f"🔄 Testing order workflow using pair: {self.symbol}")
            
            logger.info("📈 Getting current price")
            current_price = self.future_client.get_price(self.symbol)
            self.assertIsInstance(current_price, float, "Price should be a float")
            self.assertGreater(current_price, 0, "Price should be greater than 0")
            logger.info(f"Current price: {current_price}")
            
            limit_price = round(current_price * 0.9, 2)
            logger.info(f"Limit order price: {limit_price}")
            
            logger.info("📝 Placing limit order")
            self.future_client.place_limit_order(self.symbol, side, limit_price, leverage, amount)
            logger.info(f"Limit order placed: {side} {amount} {self.symbol} @ {limit_price}")
            
            logger.info("🔍 Getting open orders")
            open_orders = self.future_client.get_open_orders(self.symbol, type="LIMIT")
            self.assertIsInstance(open_orders, list, "Open orders should be a list")
            self.assertGreater(len(open_orders), 0, "Open orders should not be empty")
            logger.info(f"✅ Successfully retrieved open orders: {len(open_orders)}")
            
            self.assertEqual(open_orders[0]["symbol"], self.symbol, "Order symbol should match")
            self.assertEqual(open_orders[0]["side"], side, "Order side should match")
            self.assertAlmostEqual(float(open_orders[0]["price"]), limit_price, places=1, msg="Order price should match")
            
            order_id = open_orders[0]["orderId"]
            logger.info(f"✅ Successfully retrieved order ID: {order_id}")
            
            logger.info("🌟 Cancelling order")
            self.future_client.cancel_order(self.symbol, type="LIMIT")
            
            open_orders_after = self.future_client.get_open_orders(self.symbol)
            order_exists_after = any(o["orderId"] == order_id for o in open_orders_after)
            self.assertFalse(order_exists_after, "Order should be cancelled and not in open orders list")
            logger.info("✅ Successfully confirmed order cancellation")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}")
            self.future_client.cancel_order(self.symbol, type="LIMIT")
            raise
    
    def test_market_order_workflow(self):
        """Test market order workflow: Place market order, get positions, close position"""
        side = "SELL"
        amount = 50
        leverage = 5
        current_price = self.future_client.get_price(self.symbol)
        take_profit_price = round(current_price * 0.9, 2)
        stop_loss_price = round(current_price * 1.1, 2)
        
        try:
            logger.info(f"🔄 Testing market order workflow using pair: {self.symbol}")
            
            logger.info("📝 Placing market order")
            self.future_client.place_market_order(self.symbol, side, leverage, amount, stop_loss_price, take_profit_price)
            logger.info(f"Market order placed: {side} {amount} {self.symbol}")
            
            logger.info("🔍 Checking positions")
            positions = self.future_client.get_positions(self.symbol)
            self.assertIsInstance(positions, list, "Positions should be a list")
            self.assertGreater(len(positions), 0, "Positions should not be empty")
            logger.info(f"✅ Successfully retrieved positions: {len(positions)}")
            
            self.assertEqual(positions[0]["symbol"], self.symbol, "Position symbol should match")
            self.assertEqual(positions[0]["side"], side, "Position side should match")
            logger.info("✅ Successfully confirmed position")
            
            logger.info("🔍 Checking stop loss and take profit orders")
            stop_loss_order = self.future_client.get_open_orders(self.symbol, type="STOP_MARKET")
            take_profit_order = self.future_client.get_open_orders(self.symbol, type="TAKE_PROFIT_MARKET")
            
            self.assertIsInstance(stop_loss_order, list, "Stop loss order should be a list")
            self.assertIsInstance(take_profit_order, list, "Take profit order should be a list")
            logger.info("✅ Successfully retrieved stop loss and take profit orders")
            
            logger.info("🌟 Closing position")
            self.future_client.close_position(self.symbol, side)
            
            positions_after = self.future_client.get_positions(self.symbol)
            position_exists_after = any(p["symbol"] == self.symbol for p in positions_after)
            self.assertFalse(position_exists_after, "Position should be closed")
            logger.info("✅ Successfully confirmed position closure")
            
            stop_loss_order_after = self.future_client.get_open_orders(self.symbol, type="STOP_MARKET")
            take_profit_order_after = self.future_client.get_open_orders(self.symbol, type="TAKE_PROFIT_MARKET")
            
            self.assertFalse(stop_loss_order_after, "Stop loss order should be cancelled")
            self.assertFalse(take_profit_order_after, "Take profit order should be cancelled")
            logger.info("✅ Successfully confirmed stop loss and take profit order cancellation")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}")
            self.future_client.close_position(self.symbol, side)
            raise
            
if __name__ == "__main__":
    # Specify the symbol to test with
    env_path = ".env"  # Path to your .env file
    test_symbol = "ETHUSDT"  # Change this to test different pairs
    future_client = BinanceFutures(env_path=env_path)
    
    print(f"🧪 Running tests for {test_symbol}")
    
    # Create test suite and specify test method order
    suite = unittest.TestSuite()
    suite.addTest(TestFuturesAPI(future_client, "test_get_historical_data", symbol=test_symbol))
    suite.addTest(TestFuturesAPI(future_client, "test_fetch_usdt_balance", symbol=test_symbol))
    suite.addTest(TestFuturesAPI(future_client, "test_limit_order_workflow", symbol=test_symbol))
    suite.addTest(TestFuturesAPI(future_client, "test_market_order_workflow", symbol=test_symbol))
    
    # Run tests using TextTestRunner
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

