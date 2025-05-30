import requests
import os
from dotenv import load_dotenv

class CoinMarketCapAPI:
    """CoinMarketCap API handler for fetching cryptocurrency data."""

    def __init__(self, env_path: str = ".env"):
        
        self.env_path = env_path
        self.env = load_dotenv(self.env_path)
        self.CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
        if not self.CMC_API_KEY:
            raise ValueError("CoinMarketCap API key not found in environment variables.")

        self.stable_coins = [
            "USDT", "USDC", "USDe", "PYUSDT", "BUSD",
        ]
        self.problematic_coins = [
            "HYPE",
        ]

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
    
    