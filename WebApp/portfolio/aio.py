from datetime import datetime, timezone, timedelta
import json
import aiohttp
import asyncio
import os
import requests
import time

from WebApp.objects import allLogger, FLASK_ENV

tz = timezone(timedelta(hours=+8))



def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError as e:
        if "There is no current event loop in thread" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop()


async def get_twse_latest(code, session, price_dict, latest_date):
    today = datetime.now(tz)
    today_str = today.strftime('%Y%m%d')
    try:
        url = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=%s&stockNo=%s' % (today_str, code)
        async with session.get(url=url) as response:
            text = await response.text()
        content = json.loads(text)
        last_day = content['data'][-1]
        close = last_day[-3]    
        price_dict[code] = float(close)
        allLogger.info('Request TWSE to get latest price of {} succeeded. '.format(code))

    except:
            
        try:
            year, month, day = latest_date[:3], latest_date[4:6], latest_date[7:9]
            year = str(int(year) + 1911)
            url = "https://api.finmindtrade.com/api/v4/data"
                
            date_str = ''.join([year, '-', month, '-', day])
            parameter = {
                "dataset": "TaiwanStockPrice",
                "data_id": code,
                "start_date": date_str,
                "end_date": date_str,
                "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyMy0wMi0wMSAxMDo0MToxNyIsInVzZXJfaWQiOiJsZWVzaGloIiwiaXAiOiIxNDAuMTEzLjEzNi4yMjEifQ.V-sctM-BRrCbcocxdUqHbdxw-7-HmBQGMVbN0x1fdNA", # 參考登入，獲取金鑰
            }

            async with session.get(url=url, params = parameter) as response:
                data = await response.json()            

            close = data['data'][0]['close']

            price_dict[code] = float(close)
            allLogger.info('Failed to request TWSE. Request Finmind to get latest price of {} succeeded. '.format(code))

        except Exception as e:
            allLogger.error("Unable to get latest price of {} from Finmind due to {}.".format(code, str(e)))


async def portfolio_prices(codes, price_dict, latest_date):
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[get_twse_latest(code, session, price_dict, latest_date) for code in codes])
    return price_dict


def portfolio_prices_with_update(codes):

    # price_dict_file:
    # keys: date, value

    # query date format: %Y%m%d
    # saving date format: 112/02/01

    today = datetime.now(tz)
    today_str = today.strftime('%Y%m%d')

    # use 0050 to find the latest date
    resp = requests.get('https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=%s&stockNo=%s' % (today_str, '0050'))
    content = json.loads(resp.text)
    latest_date = content['data'][-1][0]

    if os.path.exists('price_dict_file.json'):

        with open('price_dict_file.json', 'r') as f:
            price_dict_file = json.load(f)       
       

        if latest_date == price_dict_file['date']:

            start = time.time()

            price_dict = price_dict_file['value']
            not_queried_codes = list(set(codes) - set(price_dict.keys()))

            loop = get_or_create_eventloop()
            if FLASK_ENV == 'DEV': 
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            price_dict = asyncio.run(portfolio_prices(not_queried_codes, price_dict, latest_date))
            loop.close()
            price_dict_file['value'] = price_dict
            if len(not_queried_codes) > 0:
                allLogger.info(''.join(['Price dict file updated with current date. Time spent: ', str(round(time.time() - start)), ' s']))


            with open('price_dict_file.json', 'w') as f:
                json.dump(price_dict_file, f)

            return price_dict

        else:

            start = time.time()

            price_dict_file['date'] = latest_date
            loop = get_or_create_eventloop()
            if FLASK_ENV == 'DEV': 
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            price_dict = asyncio.run(portfolio_prices(codes, {}, latest_date))
            loop.close()
            price_dict_file['value'] = price_dict
            allLogger.info(''.join(['Price dict file updated with new date. Time spent: ', str(round(time.time() - start)), ' s']))

            with open('price_dict_file.json', 'w') as f:
                json.dump(price_dict_file, f)
            return price_dict
    else:

        start = time.time()

        price_dict_file = {}
        price_dict_file['date'] = latest_date
        loop = get_or_create_eventloop()
        if FLASK_ENV == 'DEV': 
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        price_dict = asyncio.run(portfolio_prices(codes, {}, latest_date))
        loop.close()
        price_dict_file['value'] = price_dict

        allLogger.info(''.join(['Price dict file created with new date. Time spent: ', str(round(time.time() - start)), ' s']))

        with open('price_dict_file.json', 'w') as f:
            json.dump(price_dict_file, f)
        return price_dict


## history prices
async def get_twse_history(code, session, price_dict, final_open_date):
    
    try:
        year, month = final_open_date[:3], final_open_date[4:6]
        year = str(int(year) + 1911)
        date_str = ''.join([year, month, '01'])
        url = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=%s&stockNo=%s' % (date_str, code)
        async with session.get(url=url) as response:
            text = await response.text()
            content = json.loads(text)
            last_day = content['data'][-1]
            close = last_day[-3]    
            price_dict[code] = float(close)
            allLogger.info('Request TWSE to get history price of {} succeeded. '.format(code))

    except:
            
        try:

            year, month, day = final_open_date[:3], final_open_date[4:6], final_open_date[7:9]
            year = str(int(year) + 1911)
            url = "https://api.finmindtrade.com/api/v4/data"
                
            date_str = ''.join([year, '-', month, '-', day])
            parameter = {
                "dataset": "TaiwanStockPrice",
                "data_id": code,
                "start_date": date_str,
                "end_date": date_str,
                "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyMy0wMi0wMSAxMDo0MToxNyIsInVzZXJfaWQiOiJsZWVzaGloIiwiaXAiOiIxNDAuMTEzLjEzNi4yMjEifQ.V-sctM-BRrCbcocxdUqHbdxw-7-HmBQGMVbN0x1fdNA", # 參考登入，獲取金鑰
            }
            async with session.get(url=url, params = parameter) as response:
                data = await response.json()
            
            close = data['data'][0]['close']

            price_dict[code] = float(close)
            allLogger.info('Failed to request TWSE. Request Finmind to get history price of {} succeeded. '.format(code))

        except Exception as e:
            allLogger.error("Unable to get history price of {} from Finmind due to {}.".format(code, str(e)))


async def settle_prices(codes):

    # get final day of last season
    now = datetime.now(tz)
    year, month = now.year, now.month
    while month % 4 != 0:
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    
    # get last open date
    resp = requests.get('https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=%s&stockNo=%s' % (str(year) + str(month) + '01', '0050'))
    content = json.loads(resp.text)
    final_open_date = content['data'][-1][0]

    price_dict = {}

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[get_twse_history(code, session, price_dict, final_open_date) for code in codes])

    return price_dict