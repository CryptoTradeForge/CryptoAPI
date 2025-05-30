import os
import json
import requests
from dotenv import load_dotenv

class CoinMarketCapAPI:
    """CoinMarketCap API handler for fetching cryptocurrency data."""

    def __init__(self, env_path: str = ".env", exclusion_coins_path: str = "CryptoAPI\data\cmc_exclusion_coins.json"):
        self.env_path = env_path
        self.env = load_dotenv(self.env_path)
        self.CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
        if not self.CMC_API_KEY:
            raise ValueError("CoinMarketCap API key not found in environment variables.")

        self.exclusion_coins_path = exclusion_coins_path
        if not os.path.exists(self.exclusion_coins_path):
            self.stable_coins = []
            self.problematic_coins = []
        else:
            with open(self.exclusion_coins_path, 'r') as file:
                exclusion_data = json.load(file)
            self.stable_coins = exclusion_data.get("stable_coins", [])
            self.problematic_coins = exclusion_data.get("problematic_coins", [])

    def get_top_cryptos(self, limit=None, exclude_stablecoins=True, filling=True):
        """Fetch top cryptocurrencies from CoinMarketCap."""
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {"X-CMC_PRO_API_KEY": self.CMC_API_KEY}
        response = requests.get(url, headers=headers)
        data = response.json()["data"]
        
        # filter out problematic coins
        data = [coin for coin in data if coin["symbol"] not in self.problematic_coins]
        
        if not filling:
            data = data[:limit] if limit and limit < len(data) else data
        top_cryptos = sorted(data, key=lambda x: x["cmc_rank"])
        
        if exclude_stablecoins:
            top_cryptos_list = [f"{i['symbol']}USDT" for i in top_cryptos if i['symbol'] not in self.stable_coins]
        else:
            top_cryptos_list = [f"{i['symbol']}USDT" for i in top_cryptos]
        
        if filling and limit is not None:
            top_cryptos_list = top_cryptos_list[:limit]
        
        if not top_cryptos_list:
            raise ValueError("No valid cryptocurrencies found in the top list.")
        
        return top_cryptos_list
    
    def add_stable_coin(self, coin_symbol: str):
        """Add a stable coin to the exclusion list."""
        
        if coin_symbol != "USDT" and coin_symbol.endswith("USDT"):
            coin_symbol = coin_symbol[:-4]
        
        if coin_symbol and coin_symbol not in self.stable_coins:
            self.stable_coins.append(coin_symbol)
            self._save_exclusion_coins()
    
    def add_problematic_coin(self, coin_symbol: str):
        """Add a problematic coin to the exclusion list."""
        
        if coin_symbol != "USDT" and coin_symbol.endswith("USDT"):
            coin_symbol = coin_symbol[:-4]
        
        if coin_symbol and coin_symbol not in self.problematic_coins:
            self.problematic_coins.append(coin_symbol)
            self._save_exclusion_coins()
    
    # -------------------- assisted functions --------------------
    def _save_exclusion_coins(self):
        """Save the updated exclusion coins to the JSON file."""
        exclusion_data = {
            "stable_coins": self.stable_coins,
            "problematic_coins": self.problematic_coins
        }
        with open(self.exclusion_coins_path, 'w') as file:
            json.dump(exclusion_data, file, indent=4)
            

# Example usage:
if __name__ == "__main__":
    cmc_api = CoinMarketCapAPI()
    try:
        top_cryptos = cmc_api.get_top_cryptos(limit=10)
        print("Top Cryptos:", top_cryptos)
    except ValueError as e:
        print("Error:", e)
    
    # Example of adding a stable coin
    cmc_api.add_stable_coin("USDC")
    
    # Example of adding a problematic coin
    cmc_api.add_problematic_coin("XYZ")