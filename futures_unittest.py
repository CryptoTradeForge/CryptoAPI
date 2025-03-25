import unittest
import logging
import warnings
from binance_api import BinanceFutures

# Setting up basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestFuturesAPI")

class TestFuturesAPI(unittest.TestCase):
    # Configurable trading pair - can be modified here to test different pairs
    SYMBOL = "ETHUSDT"
    
    def setUp(self):
        """Setup before each test case"""
        logger.info("🔧 Setting up test environment")
        warnings.simplefilter("ignore", category=ResourceWarning)  # Ignoring ResourceWarning
        self.future_client = BinanceFutures()
        
    def tearDown(self):
        """Cleanup after each test case"""
        # logger.info("Cleaning up test environment")
        # Resource cleanup if needed
        pass
    
    def test_get_historical_data(self):
        """Test historical data retrieval functionality"""
        interval = "15m"
        limit = 10
        
        try:
            logger.info(f"📊 Testing historical data retrieval: {self.SYMBOL}, {interval}, limit: {limit}")
            klines = self.future_client.get_historical_data(self.SYMBOL, interval, limit)
            
            # More comprehensive assertions
            self.assertEqual(len(klines), limit, f"Should return {limit} data points")
            self.assertIsInstance(klines, list, "Return value should be a list")
            
            if (klines):
                # Check structure of first data point
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
            
            # More comprehensive assertions
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
            logger.info(f"🔄 Testing order workflow using pair: {self.SYMBOL}")
            
            # 1. Get current market price
            logger.info("📈 Getting current price")
            current_price = self.future_client.get_price(self.SYMBOL)
            self.assertIsInstance(current_price, float, "Price should be a float")
            self.assertGreater(current_price, 0, "Price should be greater than 0")
            logger.info(f"Current price: {current_price}")
            
            # 2. Calculate limit order price (90% of market price)
            limit_price = round(current_price * 0.9, 2)
            logger.info(f"Limit order price: {limit_price}")
            
            # 3. Place limit order
            logger.info("📝 Placing limit order")
            self.future_client.place_limit_order(self.SYMBOL, side, amount, limit_price, leverage)
            logger.info(f"Limit order placed: {side} {amount} {self.SYMBOL} @ {limit_price}")
            
            # 4. Get open orders
            logger.info("🔍 Getting open orders")
            open_orders = self.future_client.get_open_orders(self.SYMBOL, type="LIMIT")
            self.assertIsInstance(open_orders, list, "Open orders should be a list")
            self.assertGreater(len(open_orders), 0, "Open orders should not be empty")
            logger.info(f"✅ Successfully retrieved open orders: {len(open_orders)}")
            
            
            # Confirm the order we just placed exists in open orders
            self.assertEqual(open_orders[0]["symbol"], self.SYMBOL, "Order symbol should match")
            self.assertEqual(open_orders[0]["side"], side, "Order side should match")
            self.assertAlmostEqual(float(open_orders[0]["price"]), limit_price, places=1, msg="Order price should match")
            
            order_id = open_orders[0]["orderId"]
            logger.info(f"✅ Successfully retrieved order ID: {order_id}")
            
            # 5. Cancel order
            logger.info("🌟 Cancelling order")
            self.future_client.cancel_order(self.SYMBOL, type="LIMIT")
            
            # 6. Get open orders again to confirm cancellation
            open_orders_after = self.future_client.get_open_orders(self.SYMBOL)
            order_exists_after = any(o["orderId"] == order_id for o in open_orders_after)
            self.assertFalse(order_exists_after, "Order should be cancelled and not in open orders list")
            logger.info("✅ Successfully confirmed order cancellation")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}")
            
            # If test fails, cancel the order
            self.future_client.cancel_order(self.SYMBOL, type="LIMIT")
            raise
    
    def test_market_order_workflow(self):
        """Test market order workflow: Place market order, get positions, close position"""
        side = "SELL"
        amount = 50
        leverage = 5
        current_price = self.future_client.get_price(self.SYMBOL)
        take_profit_price = round(current_price * 0.9, 2)
        stop_loss_price = round(current_price * 1.1, 2)
        
        try:
            logger.info(f"🔄 Testing market order workflow using pair: {self.SYMBOL}")
            
            # 1. Place market order
            logger.info("📝 Placing market order")
            self.future_client.place_market_order(self.SYMBOL, side, amount, leverage, stop_loss_price, take_profit_price)
            logger.info(f"Market order placed: {side} {amount} {self.SYMBOL}")
            
            # 2. Check positions
            logger.info("🔍 Checking positions")
            positions = self.future_client.get_positions(self.SYMBOL)
            self.assertIsInstance(positions, list, "Positions should be a list")
            self.assertGreater(len(positions), 0, "Positions should not be empty")
            logger.info(f"✅ Successfully retrieved positions: {len(positions)}")
            
            # Confirm position exists
            self.assertEqual(positions[0]["symbol"], self.SYMBOL, "Position symbol should match")
            self.assertEqual(positions[0]["side"], side, "Position side should match")
            logger.info("✅ Successfully confirmed position")
            
            # 3. Check stop loss and take profit orders
            logger.info("🔍 Checking stop loss and take profit orders")
            stop_loss_order = self.future_client.get_open_orders(self.SYMBOL, type="STOP_MARKET")
            take_profit_order = self.future_client.get_open_orders(self.SYMBOL, type="TAKE_PROFIT_MARKET")
            
            self.assertIsInstance(stop_loss_order, list, "Stop loss order should be a list")
            self.assertIsInstance(take_profit_order, list, "Take profit order should be a list")
            logger.info("✅ Successfully retrieved stop loss and take profit orders")
            
            # 4. Close position
            logger.info("🌟 Closing position")
            self.future_client.close_position(self.SYMBOL, side)
            
            # 5. Check positions again to confirm closure
            positions_after = self.future_client.get_positions(self.SYMBOL)
            position_exists_after = any(p["symbol"] == self.SYMBOL for p in positions_after)
            self.assertFalse(position_exists_after, "Position should be closed")
            logger.info("✅ Successfully confirmed position closure")
            
            # 6. Check stop loss and take profit orders again to confirm cancellation
            stop_loss_order_after = self.future_client.get_open_orders(self.SYMBOL, type="STOP_MARKET")
            take_profit_order_after = self.future_client.get_open_orders(self.SYMBOL, type="TAKE_PROFIT_MARKET")
            
            self.assertFalse(stop_loss_order_after, "Stop loss order should be cancelled")
            self.assertFalse(take_profit_order_after, "Take profit order should be cancelled")
            logger.info("✅ Successfully confirmed stop loss and take profit order cancellation")
            
        except Exception as e:
            logger.error(f"❌ Test failed: {str(e)}")
            
            # If test fails, close the position
            self.future_client.close_position(self.SYMBOL, side)
            raise
            
    

if __name__ == "__main__":
    # To run tests with a different symbol, change the class variable here
    TestFuturesAPI.SYMBOL = "ETHUSDT"  # Uncomment to test with ETH
    
    print(f"🧪 Running tests for {TestFuturesAPI.SYMBOL}")
    
    # Create test suite and specify test method order
    suite = unittest.TestSuite()
    suite.addTest(TestFuturesAPI("test_get_historical_data"))
    suite.addTest(TestFuturesAPI("test_fetch_usdt_balance"))
    suite.addTest(TestFuturesAPI("test_limit_order_workflow"))
    suite.addTest(TestFuturesAPI("test_market_order_workflow"))
    
    # Run tests using TextTestRunner
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
    print("🎉 All tests passed!")

