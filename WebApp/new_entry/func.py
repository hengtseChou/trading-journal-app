import pandas as pd
import requests
from flask import session
from WebApp.objects import IS_STOCK_UNIT_BY_SHARES

trade_sheet_col = ['date', 'sub_account', 'code', 'name', 'type', 'buy', 'sell', 'price', 
                   'deal', 'fee', 'discounted_fee', 'tax', 
                   'transaction_cost', 'expense', 'income', 
                   'remain_shares', 'realized_gain', 'holding_cost', 'rate_of_return', 
                   'is_day_trade', 'is_settled', 'adjusted_buy_cost']
# dependent area: creating user, initializing sheets


if IS_STOCK_UNIT_BY_SHARES == 'true':
    stock_unit = 1
else:
    stock_unit = 1000           
    

# define objects

# date: str
# code: str
# name: str
# type: str
class Entry(object): # 分為買/賣/股利
    def __init__(self, date, sub_account, code, name) :
        self.date = date
        self.code = code
        self.sub_account = sub_account
        self.name = name

class Buy_entry(Entry): # 製作買入紀錄
    def __init__(self, date, sub_account, code, name, buy_shares, price, is_day_trade=False): 
        super().__init__(date, sub_account, code, name)
        self.type = 'buy'
        self.buy_shares = buy_shares
        self.price = price
        self.is_day_trade = is_day_trade

    def entry_to_row(self):
        
        new_row = [self.date, self.sub_account, self.code, self.name, self.type, self.buy_shares, 0, self.price]
        fee_discount_rate = session['sub_account'][self.sub_account][0]

        deal = self.buy_shares * self.price * stock_unit
        new_row.append(deal)
        new_row.append(deal * 0.001425)
        
        new_row.append(deal * 0.001425 * fee_discount_rate)
        # no tax for buying stock
        new_row.append(0)

        # transaction cost = fee + tax
        new_row.append(deal * 0.001425 * fee_discount_rate + 0) 
        # expense = deal + discounted_fee
        new_row.append(deal * (1 + 0.001425 * fee_discount_rate)) 
        # income = 0
        new_row.append(0)

        # now remain = shares bought
        new_row.append(self.buy_shares)
        # realized gain, holding cost, RoR = 0
        new_row.extend([0, 0, 0]) 

        # day trade
        if self.is_day_trade:
            new_row.append(1)
        else:
            new_row.append(0)

        # is settled = false (0)
        new_row.append(0) 
        # adjusted buy cost init as buy price
        new_row.append(self.price)

        new_row = pd.DataFrame(new_row).T
        new_row.columns = trade_sheet_col

        self.new_row = new_row

    def concat_to_sheet(self, full_sheet):

        return pd.concat([full_sheet, self.new_row], ignore_index=True)


class Sell_entry(Entry):
    def __init__(self, date, sub_account, code, name, sell_shares, price, is_day_trade=False): 
        super().__init__(date, sub_account, code, name)
        self.type = 'sell'
        self.sell_shares = sell_shares
        self.price = price
        self.is_day_trade = is_day_trade

    def entry_to_row(self):
        
        new_row = [self.date, self.sub_account, self.code, self.name, self.type, 0, self.sell_shares, self.price]
        self.fee_discount_rate = session['sub_account'][self.sub_account][0]

        deal = self.sell_shares * self.price * stock_unit
        new_row.append(deal)
        new_row.append(deal * 0.001425)
        discounted_fee = deal * 0.001425 * self.fee_discount_rate
        new_row.append(discounted_fee)
        if self.is_day_trade == True:
            tax = deal * 0.0015
        else:
            tax = deal * 0.003
        new_row.append(tax)

        # transaction cost = fee + tax
        self.cost = discounted_fee + tax 
        new_row.append(self.cost)
        # expense = 0
        new_row.append(0) 
        # income = deal - transaction cost
        new_row.append(deal - (self.cost)) 
        
        # remain shares, realized gain, holding cost, Ror = 0
        new_row.extend([0, 0, 0, 0])
        # is day trade
        if self.is_day_trade:
            new_row.append(1)
        else:
            new_row.append(0)

        # is settled = false (won't need), adjusted buy cost = 0
        new_row.extend([0, 0])

        new_row = pd.DataFrame(new_row).T
        new_row.columns = trade_sheet_col

        self.new_row = new_row

    def concat_to_sheet_and_sell(self, full_sheet):

        full_sheet_copy = full_sheet.copy()
        code = self.code
        sub_account = self.sub_account
        selling_shares = self.sell_shares
        holding_cost = 0

        bool_idx = ((full_sheet_copy.code == code) & 
                    (full_sheet_copy.sub_account == sub_account) & 
                    (full_sheet_copy.buy > 0) & 
                    (full_sheet_copy.is_day_trade == 0)).tolist() 
        idx = [i for i, x in enumerate(bool_idx) if x]

        i = 0
        while selling_shares > 0:
            # 以調整成本價計算損益
            # 並且有含買入時的交易成本
            adjusted_buy_price = full_sheet_copy.adjusted_buy_cost[idx[i]]            
            if full_sheet_copy.remain_shares[idx[i]] == 0:
                i += 1
            else:
                if full_sheet_copy.remain_shares[idx[i]] >= selling_shares: # 當前買單剩餘數量大於賣單
                    full_sheet_copy.remain_shares[idx[i]] -= selling_shares
                    holding_cost += adjusted_buy_price * selling_shares * stock_unit * (1 + 0.001425 * self.fee_discount_rate)
                    selling_shares = 0
                else: 
                    selling_shares -= full_sheet_copy.remain_shares[idx[i]] # 當前買單會用盡，前往下一買單
                    holding_cost += adjusted_buy_price * full_sheet_copy.remain_shares[idx[i]] * stock_unit * (1 + 0.001425 * self.fee_discount_rate)
                    full_sheet_copy.remain_shares[idx[i]] = 0
                    i += 1

        
        new_row_copy = self.new_row
        realized_gain = new_row_copy.income[0] - holding_cost
        new_row_copy.realized_gain[0] = realized_gain
        new_row_copy.holding_cost[0] = holding_cost
        new_row_copy.rate_of_return[0] = round(realized_gain / holding_cost * 100, 2)
        self.new_row = new_row_copy
        
        return pd.concat([full_sheet_copy, self.new_row], ignore_index=True)
    
    def day_trade_sell_concat(self, full_sheet):

        full_sheet_copy = full_sheet.copy()
        code = self.code
        sub_account = self.sub_account
        selling_shares = self.sell_shares
        holding_cost = 0

        # 當沖必須篩出當天的當沖買入，做賣出
        bool_idx = ((full_sheet_copy.code == code) & 
                    (full_sheet_copy.sub_account == sub_account) & 
                    (full_sheet_copy.buy > 0) & 
                    (full_sheet_copy.is_day_trade == 1) &
                    (full_sheet_copy.date == self.date)).tolist() 
        idx = [i for i, x in enumerate(bool_idx) if x]

        i = 0
        while selling_shares > 0:
            # 以調整成本價計算損益
            # 並且有含買入時的交易成本
            adjusted_buy_price = full_sheet_copy.adjusted_buy_cost[idx[i]]            
            if full_sheet_copy.remain_shares[idx[i]] == 0:
                i += 1
            else:
                if full_sheet_copy.remain_shares[idx[i]] >= selling_shares: # 當前買單剩餘數量大於賣單
                    full_sheet_copy.remain_shares[idx[i]] -= selling_shares
                    holding_cost += adjusted_buy_price * selling_shares * stock_unit * (1 + 0.001425 * self.fee_discount_rate)
                    selling_shares = 0
                else: 
                    selling_shares -= full_sheet_copy.remain_shares[idx[i]] # 當前買單會用盡，前往下一買單
                    holding_cost += adjusted_buy_price * full_sheet_copy.remain_shares[idx[i]] * stock_unit * (1 + 0.001425 * self.fee_discount_rate)
                    full_sheet_copy.remain_shares[idx[i]] = 0
                    i += 1

        
        new_row_copy = self.new_row
        realized_gain = new_row_copy.income[0] - holding_cost
        new_row_copy.realized_gain[0] = realized_gain
        new_row_copy.holding_cost[0] = holding_cost
        new_row_copy.rate_of_return[0] = round(realized_gain / holding_cost * 100, 2)
        self.new_row = new_row_copy
        
        return pd.concat([full_sheet_copy, self.new_row], ignore_index=True)



class Dividend_entry(Entry):    
    def __init__(self, date, sub_account, code, name, dividend_received): 
        super().__init__(date, sub_account, code, name)
        self.type = 'dividend'
        self.div = dividend_received
        
    def entry_to_row(self):
        
        new_row = [self.date, self.sub_account, self.code, self.name, self.type]
        new_row.extend([0] * 17)
        new_row[14] = self.div # income
        new_row[16] = self.div # realized gain

        new_row = pd.DataFrame(new_row).T
        new_row.columns = trade_sheet_col

        self.new_row = new_row

    def concat_to_sheet(self, full_sheet):
        
        return pd.concat([full_sheet, self.new_row], ignore_index=True)


def sheet_output(sheet):
    # change order to output
    # drop columns will operate in front end
    sheet = sheet.iloc[::-1]
    ror = sheet['rate_of_return'].copy()
    is_day_trade = sheet['is_day_trade'].copy()
    adjusted_buy_cost = sheet['adjusted_buy_cost'].copy()
    sheet = pd.concat([sheet.iloc[:, 0:8], sheet.iloc[:, 8:18].round().astype(int)], axis=1)
    sheet = pd.concat([sheet, ror], axis=1)
    sheet = pd.concat([sheet, is_day_trade], axis=1)
    sheet = pd.concat([sheet, adjusted_buy_cost], axis=1)

    # change text in is_day_trade
    sheet.is_day_trade = sheet.is_day_trade.astype(str)
    sheet.is_day_trade[sheet.is_day_trade == '1'] = '是'
    sheet.is_day_trade[sheet.is_day_trade == '0'] = '否'

    sub_acc = sheet.sub_account.unique()
    separate_view = {}
    for acc in sub_acc:
        separate_view[acc] = sheet[sheet.sub_account == acc]

    output = [separate_view, sheet]
    
    return output


def update_index():

    new_table = pd.DataFrame(columns = ['code', 'company'])

    mkt_url = 'https://isin.twse.com.tw/isin/C_public.jsp?strMode=2'
    otc_url = 'https://isin.twse.com.tw/isin/C_public.jsp?strMode=4'

    ### stock exchange market

    res = requests.get(mkt_url)
    df = pd.read_html(res.text)[0]

    idx = df.index[(df.iloc[:,0] == '上市認購(售)權證') == True].tolist()[0]
    df = df.iloc[2:idx, 0]
    df = df.str.split(expand = True)
    df.columns = ['code', 'company']
    new_table = pd.concat([new_table, df], ignore_index=True)

    ### OTC

    res = requests.get(otc_url)
    df = pd.read_html(res.text)[0]

    idx2 = df.index[(df.iloc[:,0] == '股票') == True].tolist()[0]
    idx3 = df.index[(df.iloc[:,0] == '特別股') == True].tolist()[0]
    df = df.iloc[(idx2+1):idx3, 0]
    df = df.str.split(expand = True)
    df.columns = ['code', 'company']
    new_table = pd.concat([new_table, df], ignore_index=True)

    ### save locally

    new_table.to_csv('company_code_index.csv', index=False)



def settle_price(code, date_str):

    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPrice",
        "data_id": code,
        "start_date": date_str,
        "end_date": date_str,
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyMy0wMi0wMSAxMDo0MToxNyIsInVzZXJfaWQiOiJsZWVzaGloIiwiaXAiOiIxNDAuMTEzLjEzNi4yMjEifQ.V-sctM-BRrCbcocxdUqHbdxw-7-HmBQGMVbN0x1fdNA", # 參考登入，獲取金鑰
    }
    resp = requests.get(url, params=parameter)
    data = resp.json()

    if len(data['data']) == 0:
        return 'retry'

    close = data['data'][0]['close']
    return close

def create_log_text(info: dict):
    # date, type, sub_account, code, name, day_trade
    # buy/sell: amount; div: income
    for key, value in info.items():
        info[key] = str(value)

    day_trade_text = ''
    if info['day_trade'] == 'True':
        day_trade_text = '當沖'

    if info['type'] == 'div':
        type_text = '獲得 '
    elif info['type'] == 'buy':
        type_text = '買 '
    elif info['type'] == 'sell':
        type_text = '賣 ' 

    text = ''.join([info['date'], ' 以子帳戶 ', info['sub_account'], ' ', day_trade_text, type_text, info['code'], ' ', info['name']])
    
    if info['type'] == 'div':
        text = text + '股利共 ' + info['income'] + ' 元'
    else:
        text = text + ' 共 ' + info['amount'] + ' 張'
    return text