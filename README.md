# CryptoAPI

A comprehensive Python framework for cryptocurrency futures trading, designed with extensibility and standardization in mind.

## Overview

This project provides a unified API abstraction for interacting with various cryptocurrency exchange futures markets. Currently implemented with support for Binance Futures, the architecture allows for easy extension to other exchanges.

## Features

- **Standardized Interface**: Consistent API across different exchanges
- **Futures Trading Operations**:
  - Market and limit orders
  - Position management
  - Stop-loss and take-profit functionality
  - Order cancellation
- **Data Access**:
  - Historical price data retrieval
  - Account balance information
  - Open orders and position details

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd CryptoAPI

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the root directory with your API credentials:

```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

## Usage Examples

### Initializing the API

```python
from binance_api import BinanceFutures

# Initialize with default .env file
client = BinanceFutures()

# Or specify a custom path to your environment file
client = BinanceFutures(env_path="/path/to/.env")
```

### Getting Market Data

```python
# Get current price for a symbol
price = client.get_price("ETHUSDT")
print(f"Current ETH price: {price}")

# Get historical candlestick data
klines = client.get_historical_data("ETHUSDT", interval="15m", limit=100)
```

### Trading Operations

```python
# Place a market order
client.place_market_order(
    symbol="ETHUSDT",
    position_type="LONG",
    amount=50,  # USDT amount
    leverage=5,
    stop_loss_price=1800.0,
    take_profit_price=2100.0
)

# Place a limit order
client.place_limit_order(
    symbol="ETHUSDT",
    position_type="SHORT",
    amount=50,
    price=2000.0,
    leverage=5
)

# Close a position
client.close_position("ETHUSDT", "LONG")
```

### Account Information

```python
# Get account balance
balance = client.fetch_usdt_balance()
print(f"USDT Balance: {balance['total']} (Free: {balance['free']}, Used: {balance['used']})")

# Get open positions
positions = client.get_positions()
for position in positions:
    print(f"Position: {position['symbol']} - Side: {position['side']} - Amount: {position['positionAmt']}")

# Get open orders
orders = client.get_open_orders()
for order in orders:
    print(f"Order: {order['symbol']} - Type: {order['type']} - Price: {order['price']}")
```

## Architecture

The project follows object-oriented design principles:

- `AbstractFuturesAPI`: Base abstract class defining the standard interface
- `BinanceFutures`: Concrete implementation for Binance Futures

This enables easy extension to other exchanges by implementing new classes that inherit from `AbstractFuturesAPI`.

## Testing

Run the test suite to verify functionality:

```bash
python test_futures_api.py
```

The tests include:
- Historical data retrieval
- Balance fetching
- Limit order workflow
- Market order workflow with stop-loss and take-profit

## Dependencies

- python-binance==1.0.28
- python-dotenv (for environment variable management)

## Contributing

Contributions are welcome! To add support for a new exchange:

1. Create a new class that inherits from `AbstractFuturesAPI`
2. Implement all required methods
3. Add appropriate tests

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Copyright 2025 CryptoAPI Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
