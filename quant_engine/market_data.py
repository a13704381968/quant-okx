"""
Market Data Manager - 市场数据管理模块
用于从OKX获取历史K线数据并存入数据库
"""

import time
import pandas as pd
from datetime import datetime
from quant_engine.db import get_db_connection


class MarketDataManager:
    def __init__(self, okx_client=None):
        self.client = okx_client
    
    def set_client(self, okx_client):
        self.client = okx_client
    
    def fetch_and_save_klines(self, symbol, bar='1H', start_date=None, end_date=None, progress_callback=None):
        """
        从OKX获取历史K线数据并存入数据库
        
        Args:
            symbol: 交易对，如 BTC-USDT
            bar: K线周期，如 1m, 5m, 15m, 1H, 4H, 1D
            start_date: 开始日期，格式 'YYYY-MM-DD' 或 datetime
            end_date: 结束日期，格式 'YYYY-MM-DD' 或 datetime
            progress_callback: 进度回调函数 callback(current, total, message)
        
        Returns:
            dict: {'status': 'success'/'error', 'msg': str, 'count': int}
        """
        import requests
        
        if not start_date:
            start_date = '2024-01-01'
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 转换日期为时间戳
        if isinstance(start_date, str):
            start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
        else:
            start_ts = int(start_date.timestamp() * 1000)
            
        if isinstance(end_date, str):
            end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)
        else:
            end_ts = int(end_date.timestamp() * 1000)
        
        all_data = []
        current_after = end_ts  # OKX API: after参数获取该时间之前的数据
        batch_count = 0
        max_batches = 500  # 防止无限循环
        
        base_url = "https://www.okx.com"
        if self.client:
            base_url = self.client.base_url
        
        try:
            while batch_count < max_batches:
                url = f"{base_url}/api/v5/market/history-candles?instId={symbol}&bar={bar}&limit=100&after={current_after}"
                
                response = requests.get(url, proxies=self.client.proxies if self.client else None)
                data = response.json()
                
                if data.get('code') != '0' or not data.get('data'):
                    break
                
                klines = data['data']
                if not klines:
                    break
                
                # 检查是否已经超出开始时间范围
                oldest_ts = int(klines[-1][0])
                if oldest_ts < start_ts:
                    # 过滤掉超出范围的数据
                    klines = [k for k in klines if int(k[0]) >= start_ts]
                    all_data.extend(klines)
                    break
                
                all_data.extend(klines)
                batch_count += 1
                
                # 更新进度
                if progress_callback:
                    progress_callback(batch_count, max_batches, f"已获取 {len(all_data)} 条数据...")
                
                # 使用最老数据的时间戳作为下一次请求的after参数
                current_after = oldest_ts
                
                # 避免请求过快
                time.sleep(0.2)
            
            if not all_data:
                return {'status': 'error', 'msg': '未获取到数据', 'count': 0}
            
            # 存入数据库
            count = self._save_klines_to_db(symbol, bar, all_data)
            
            return {
                'status': 'success',
                'msg': f'成功获取并保存 {count} 条K线数据',
                'count': count
            }
            
        except Exception as e:
            return {'status': 'error', 'msg': str(e), 'count': 0}
    
    def _save_klines_to_db(self, symbol, bar, klines):
        """将K线数据保存到数据库"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        count = 0
        for k in klines:
            try:
                cursor.execute('''
                INSERT OR REPLACE INTO market_klines 
                (symbol, bar, ts, open, high, low, close, vol, vol_ccy, vol_ccy_quote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, bar, int(k[0]),
                    float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                    float(k[5]) if k[5] else None,
                    float(k[6]) if k[6] else None,
                    float(k[7]) if k[7] else None
                ))
                count += 1
            except Exception as e:
                print(f"Error saving kline: {e}")
        
        conn.commit()
        conn.close()
        return count
    
    def get_klines_from_db(self, symbol, bar='1H', start_date=None, end_date=None):
        """从数据库获取K线数据"""
        conn = get_db_connection()
        
        query = 'SELECT * FROM market_klines WHERE symbol = ? AND bar = ?'
        params = [symbol, bar]
        
        if start_date:
            start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
            query += ' AND ts >= ?'
            params.append(start_ts)
        
        if end_date:
            end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)
            query += ' AND ts <= ?'
            params.append(end_ts)
        
        query += ' ORDER BY ts ASC'

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        return df

    def get_data_info(self, symbol=None, bar=None):
        """获取数据库中已有数据的统计信息"""
        conn = get_db_connection()
        cursor = conn.cursor()

        if symbol and bar:
            cursor.execute('''
            SELECT symbol, bar, COUNT(*) as count,
                   MIN(ts) as min_ts, MAX(ts) as max_ts
            FROM market_klines
            WHERE symbol = ? AND bar = ?
            GROUP BY symbol, bar
            ''', (symbol, bar))
        else:
            cursor.execute('''
            SELECT symbol, bar, COUNT(*) as count,
                   MIN(ts) as min_ts, MAX(ts) as max_ts
            FROM market_klines
            GROUP BY symbol, bar
            ''')

        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            min_date = datetime.fromtimestamp(row['min_ts'] / 1000).strftime('%Y-%m-%d %H:%M') if row['min_ts'] else None
            max_date = datetime.fromtimestamp(row['max_ts'] / 1000).strftime('%Y-%m-%d %H:%M') if row['max_ts'] else None
            result.append({
                'symbol': row['symbol'],
                'bar': row['bar'],
                'count': row['count'],
                'start_date': min_date,
                'end_date': max_date
            })

        return result

    def delete_klines(self, symbol, bar=None):
        """删除指定交易对的K线数据"""
        conn = get_db_connection()
        cursor = conn.cursor()

        if bar:
            cursor.execute('DELETE FROM market_klines WHERE symbol = ? AND bar = ?', (symbol, bar))
        else:
            cursor.execute('DELETE FROM market_klines WHERE symbol = ?', (symbol,))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        return count

