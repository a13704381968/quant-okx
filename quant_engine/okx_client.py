import hmac
import base64
import datetime
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

class OKXClient:
    def __init__(self, api_key, secret_key, passphrase, base_url="https://www.okx.com", proxy_url=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = base_url
        self.proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

        # Create session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _get_timestamp(self):
        return datetime.datetime.utcnow().isoformat("T", "milliseconds") + "Z"

    def _sign(self, timestamp, method, request_path, body):
        if str(body) == '{}' or str(body) == 'None':
            body = ''
        message = str(timestamp) + str(method) + str(request_path) + str(body)
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf8'),
            digestmod='sha256'
        )
        d = mac.digest()
        return base64.b64encode(d)

    def _get_headers(self, method, request_path, body):
        timestamp = self._get_timestamp()
        sign = self._sign(timestamp, method, request_path, body)
        header = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': sign,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
        return header

    def get_account_balance(self):
        path = '/api/v5/account/balance'
        headers = self._get_headers('GET', path, '')
        try:
            response = self.session.get(self.base_url + path, headers=headers, proxies=self.proxies, timeout=30)
            return response.json()
        except Exception as e:
            return {"code": "500", "msg": str(e)}

    def get_positions(self):
        path = '/api/v5/account/positions'
        headers = self._get_headers('GET', path, '')
        try:
            response = self.session.get(self.base_url + path, headers=headers, proxies=self.proxies, timeout=30)
            return response.json()
        except Exception as e:
            return {"code": "500", "msg": str(e)}

    def get_ticker(self, instId):
        path = f'/api/v5/market/ticker?instId={instId}'
        try:
            response = self.session.get(self.base_url + path, proxies=self.proxies, timeout=30)
            return response.json()
        except Exception as e:
            return {"code": "500", "msg": str(e)}

    def place_order(self, instId, tdMode, side, ordType, sz, px=None):
        """
        Place an order on OKX

        Args:
            instId: Instrument ID (e.g., BTC-USDT)
            tdMode: Trade mode - 'cash' for spot, 'cross' or 'isolated' for margin
            side: 'buy' or 'sell'
            ordType: 'limit' or 'market'
            sz: Order size (quantity)
            px: Price (required for limit orders)
        """
        path = '/api/v5/trade/order'

        # Format size to proper precision (avoid scientific notation)
        sz_formatted = f"{float(sz):.8f}".rstrip('0').rstrip('.')

        body = {
            "instId": instId,
            "tdMode": tdMode,
            "side": side,
            "ordType": ordType,
            "sz": sz_formatted,
            "tag": "c314b0aecb5bBCDE"
        }

        if px and ordType == 'limit':
            # Format price properly
            px_formatted = f"{float(px):.2f}"
            body["px"] = px_formatted

        print(f"[OKX API] Placing order: {body}")

        headers = self._get_headers('POST', path, json.dumps(body))

        # Try up to 3 times with different strategies
        last_error = None
        for attempt in range(3):
            try:
                response = self.session.post(
                    self.base_url + path,
                    headers=headers,
                    data=json.dumps(body),
                    proxies=self.proxies,
                    timeout=30
                )
                result = response.json()
                print(f"[OKX API] Response: {result}")
                return result
            except Exception as e:
                last_error = e
                print(f"[OKX API] Attempt {attempt + 1} failed: {e}")
                time.sleep(1)

        print(f"[OKX API] All attempts failed: {last_error}")
        return {"code": "500", "msg": str(last_error)}

    def get_history_candles(self, instId, bar='1H', after=None, before=None, limit=100):
        """
        获取历史K线数据 (公开接口，不需要认证)

        Args:
            instId: 交易对，如 BTC-USDT
            bar: K线周期，如 1m, 5m, 15m, 1H, 4H, 1D
            after: 请求此时间戳之前的数据（更早的数据）
            before: 请求此时间戳之后的数据（更新的数据）
            limit: 返回结果数量，最大100

        Returns:
            dict: API响应结果
        """
        path = f'/api/v5/market/history-candles?instId={instId}&bar={bar}&limit={limit}'
        if after:
            path += f'&after={after}'
        if before:
            path += f'&before={before}'

        try:
            response = requests.get(self.base_url + path, proxies=self.proxies)
            return response.json()
        except Exception as e:
            return {"code": "500", "msg": str(e)}

    def get_candles(self, instId, bar='1H', after=None, before=None, limit=100):
        """
        获取最近K线数据 (公开接口，不需要认证)
        用于获取最新的K线数据

        Args:
            instId: 交易对，如 BTC-USDT
            bar: K线周期，如 1m, 5m, 15m, 1H, 4H, 1D
            after: 请求此时间戳之前的数据
            before: 请求此时间戳之后的数据
            limit: 返回结果数量，最大100

        Returns:
            dict: API响应结果
        """
        path = f'/api/v5/market/candles?instId={instId}&bar={bar}&limit={limit}'
        if after:
            path += f'&after={after}'
        if before:
            path += f'&before={before}'

        try:
            response = requests.get(self.base_url + path, proxies=self.proxies)
            return response.json()
        except Exception as e:
            return {"code": "500", "msg": str(e)}
