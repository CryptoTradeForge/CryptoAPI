import os
import json
import requests
from dotenv import load_dotenv

class CoinMarketCapAPI:
    """CoinMarketCap API handler for fetching cryptocurrency data."""

    def __init__(self, cmc_api_key=None, env_path=".env"):
        
        if cmc_api_key:
            self.CMC_API_KEY = cmc_api_key
        else:
            if not os.path.exists(env_path):
                raise FileNotFoundError(f"Environment file {env_path} not found.")
            if not os.path.isfile(env_path):
                raise ValueError(f"{env_path} is not a file.")
            if not os.access(env_path, os.R_OK):
                raise PermissionError(f"Cannot read environment file {env_path}.")

            self.env = load_dotenv(env_path)
            self.CMC_API_KEY = os.getenv("COINMARKETCAP_API_KEY")
            
            if not self.CMC_API_KEY:
                raise ValueError("CoinMarketCap API key not found in environment variables.")
            

    def get_top_cryptos(self, limit=None):
        """Fetch top cryptocurrencies from CoinMarketCap."""
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {"X-CMC_PRO_API_KEY": self.CMC_API_KEY}
        response = requests.get(url, headers=headers)
        data = response.json()["data"]
        
        top_cryptos = sorted(data, key=lambda x: x["cmc_rank"])
        
        top_cryptos_list = [f"{i['symbol']}USDT" for i in top_cryptos]
        
        if limit:
            top_cryptos_list = top_cryptos_list[:limit]
        
        if not top_cryptos_list:
            raise ValueError("No valid cryptocurrencies found in the top list.")
        
        return top_cryptos_list
    

# Example usage:
if __name__ == "__main__":
    cmc_api = CoinMarketCapAPI()
    try:
        top_cryptos = cmc_api.get_top_cryptos(limit=10)
        print("Top Cryptos:", top_cryptos)
    except ValueError as e:
        print("Error:", e)