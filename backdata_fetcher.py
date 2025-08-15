# -*- coding: utf-8 -*-
import pytz
import json
from datetime import datetime
from pathlib import Path

# Timeframe constants in milliseconds
TIMEFRAME_TO_MS = {
    '5m': 1000 * 60 * 5,      # 5 minutes
    '15m': 1000 * 60 * 15,    # 15 minutes  
    '1h': 1000 * 60 * 60,     # 1 hour
    '4h': 1000 * 60 * 60 * 4, # 4 hours
    '1d': 1000 * 60 * 60 * 24 # 1 day
}

# Extra buffer for backtesting safety margin
EXTRA_BUFFER = 10

class BackDataFetcher:
    """
    Advanced historical data fetcher for cryptocurrency backtesting and analysis.
    
    While simple single-symbol data can be retrieved directly using the futures API's 
    get_historical_data() method, this class provides sophisticated functionality for:
    
    - Multi-timeframe data synchronization (5m, 15m, 1h, 4h, 1d)
    - Batch processing of multiple symbols with error handling
    - Top cryptocurrency ranking integration via CoinMarketCap API  
    - Intelligent buffer management for backtesting vs live trading modes
    - Problematic coin exclusion and filtering capabilities
    - Automated data validation and consistency checking
    - Persistent storage with timestamped file management
    
    Designed for comprehensive backtesting workflows and large-scale data operations
    where simple single-symbol fetching is insufficient.
    """

    def __init__(self, future_api=None, cmc_api=None, exclusion_coins_record=None, use_extra_buffer=True, save_folder='data/back_data', verbose=True):
        """
        Initializes the BackDataFetcher with the necessary APIs and save folder.
        :param future_api: An instance of the futures API to fetch historical data. If None, uses default BinanceFutures.
        :param cmc_api: An instance of the CoinMarketCap API to fetch top cryptocurrencies. If None, uses default CoinMarketCapAPI.
        :param exclusion_coins_record: An instance of ExclusionCoinsRecord for filtering coins. If None, no exclusion functionality.
                                     Can be imported from GeneralUtils.exclusion_coins_record.ExclusionCoinsRecord.
        :param use_extra_buffer: Whether to use extra buffer (10) for backtesting safety margin. True for backtest mode, False for live mode.
        :param save_folder: The folder where the fetched data will be saved.
        :param verbose: Whether to print information during execution.
        """
        
        self.verbose = verbose
        self.use_extra_buffer = use_extra_buffer
        self.timezone = pytz.timezone("Asia/Taipei")
        
        self.future_api = future_api
        self.cmc_api = cmc_api
        self.exclusion_coins = exclusion_coins_record
        self.save_folder = save_folder
        
        # Set up default APIs if not provided
        if self.future_api is None:
            from .futures.binance_api import BinanceFutures
            self.future_api = BinanceFutures()
            if self.verbose:
                print("[Warning]: No future_api provided. Using default BinanceFutures API.")

        if self.cmc_api is None:
            from .cmc_api import CoinMarketCapAPI
            self.cmc_api = CoinMarketCapAPI()
            if self.verbose:
                print("[Warning]: No cmc_api provided. Using default CoinMarketCapAPI.")

        if not self.exclusion_coins and self.verbose:
            print("[Warning]: No exclusion_coins_record provided. No exclusion functionality will be applied.")


    def get_historical_data_and_check(self, symbol: str, interval: str, limit: int):
        
        if self.verbose:
            print(f"---------- Fetching {symbol} [{interval}] with limit {limit} ----------")
        
        data = self.future_api.get_historical_data(symbol=symbol, interval=interval, limit=limit, show=self.verbose)
        
        # if not data:
        #     raise ValueError(f"No data found for {symbol} at interval {interval} with limit {limit}.")
        
        if len(set([d[0] for d in data])) < limit:
            raise ValueError(f"Insufficient data points for {symbol} at interval {interval}. Expected {limit}, got {len(data)}.")
        
        return data
    
    
    def fetch_data(self, symbol: str, limit: int = 10000, buffer: int = 1000) -> dict:
        """
        Fetches historical data for a given symbol across multiple timeframes.
        :param symbol: The trading symbol for which to fetch data.
        :param limit: The maximum number of data points to fetch for the shortest timeframe.
        :param buffer: Additional data points to fetch for longer timeframes to ensure sufficient data.
        :return: A dictionary containing historical data for the symbol across different timeframes.
        """
        
        if self.verbose:
            print(f"============================== Fetching {symbol} ==============================")
        
        extra = EXTRA_BUFFER if self.use_extra_buffer else 0
        
        data = {
            '5m': self.get_historical_data_and_check(symbol=symbol, interval='5m', limit=limit + buffer + extra),
            '15m': self.get_historical_data_and_check(symbol=symbol, interval='15m', limit=limit // 3 + buffer + extra),
            '1h': self.get_historical_data_and_check(symbol=symbol, interval='1h', limit=limit // 12 + buffer + extra),
            '4h': self.get_historical_data_and_check(symbol=symbol, interval='4h', limit=limit // 48 + buffer + extra),
            '1d': self.get_historical_data_and_check(symbol=symbol, interval='1d', limit=limit // 288 + buffer + extra)
        }
        
        return data


    def fetch_data_symbols(self, symbols: list, limit: int = 10000, buffer: int = 1000) -> dict:
        """
        Fetches historical data for multiple symbols across different timeframes.
        :param symbols: A list of trading symbols for which to fetch data.
        :param limit: The maximum number of data points to fetch for the shortest timeframe.
        :param buffer: Additional data points to fetch for longer timeframes to ensure sufficient data.
        :return: A dictionary containing historical data for each symbol across different timeframes.
        """
        all_data = {}
        for symbol in symbols:
            try:
                all_data[symbol] = self.fetch_data(symbol, limit, buffer)
            except Exception as e:
                if self.verbose:
                    print(f"Error fetching data for {symbol}: {e}")
                if self.exclusion_coins:
                    self.exclusion_coins.add_problematic_coin(symbol)
        return all_data

    def fetch_data_since(self, symbol: str, since: int, buffer: int = 1000, show: bool = False) -> dict:
        """
        Fetches historical data for a given symbol starting from a specific timestamp.
        :param symbol: The trading symbol for which to fetch data.
        :param since: The timestamp (in seconds) from which to start fetching data.
        :param buffer: The base buffer size for ensuring sufficient data.
        :param show: Whether to show fetch information.
        :return: A dictionary containing historical data for the symbol across different timeframes.
        """
        if show and self.verbose:
            print(f"Fetching {symbol} since: {since}")
        
        extra = EXTRA_BUFFER if self.use_extra_buffer else 0
        
        data = {
            '5m': self.future_api.get_historical_data(symbol=symbol, interval='5m', since=since-TIMEFRAME_TO_MS['5m']*(buffer+extra)),
            '15m': self.future_api.get_historical_data(symbol=symbol, interval='15m', since=since-TIMEFRAME_TO_MS['15m']*(buffer+extra)),
            '1h': self.future_api.get_historical_data(symbol=symbol, interval='1h', since=since-TIMEFRAME_TO_MS['1h']*(buffer+extra)),
            '4h': self.future_api.get_historical_data(symbol=symbol, interval='4h', since=since-TIMEFRAME_TO_MS['4h']*(buffer+extra)),
            '1d': self.future_api.get_historical_data(symbol=symbol, interval='1d', since=since-TIMEFRAME_TO_MS['1d']*(buffer+extra))
        }
        
        for interval, interval_data in data.items():
            if not interval_data:
                raise ValueError(f"No data found for {symbol} at interval {interval} since {since}.")
            if len(set([d[0] for d in interval_data])) != len(interval_data):
                raise ValueError(f"Insufficient data for {symbol} at interval {interval} since {since}.")
        
        return data

    def fetch_topk_data(self, topk: int = 10, limit: int = 10000, buffer: int = 1000) -> dict:
        """
        Fetches historical data for the top k cryptocurrencies.
        :param topk: The number of top cryptocurrencies to fetch data for.
        :param limit: The maximum number of data points to fetch for the shortest timeframe.
        :param buffer: Additional data points to fetch for longer timeframes to ensure sufficient data.
        :return: A dictionary containing historical data for the top k cryptocurrencies across different timeframes.
        """
        symbols = self.cmc_api.get_top_cryptos(limit=topk)
        if self.exclusion_coins:
            symbols = self.exclusion_coins.filter_coins(symbols)
        if not symbols:
            raise ValueError("No valid cryptocurrencies found in the top list after filtering.")
        return self.fetch_data_symbols(symbols, limit, buffer)

    def fetch_topk_and_save(self, topk: int = 10, limit: int = 10000, buffer: int = 1000, save_path: str = None) -> dict:
        """
        Fetches historical data for the top k cryptocurrencies and saves it to a specified path.
        :param topk: The number of top cryptocurrencies to fetch data for.
        :param limit: The maximum number of data points to fetch for the shortest timeframe.
        :param buffer: Additional data points to fetch for longer timeframes to ensure sufficient data.
        :param save_path: The path where the fetched data will be saved. If None, uses the default save folder.
        :return: A dictionary containing historical data for the top k cryptocurrencies across different timeframes.
        """
        if save_path is None:
            save_path = self.save_folder
        all_data = self.fetch_topk_data(topk, limit, buffer)
        
        now = datetime.now(self.timezone).strftime("%Y%m%d_%H%M")
        filename = f"{save_path}/top_{topk}_{limit}_{now}.json"
        
        Path(save_path).mkdir(parents=True, exist_ok=True)
        with open(filename, 'w') as file:
            json.dump(all_data, file)
        
        if self.verbose:
            print(f"Data saved to {filename}")
        return all_data

if __name__ == "__main__":
    # Example usage
    fetcher = BackDataFetcher()

    data = fetcher.fetch_topk_and_save(topk=100, limit=100, buffer=10)
    print(data.keys())