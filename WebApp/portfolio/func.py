import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
import numpy as np
from flask import session

from WebApp.objects import IS_STOCK_UNIT_BY_SHARES
from WebApp.portfolio.aio import portfolio_prices_with_update


portfolio_col = ['code', 'name', 'now_price', 'avg_buy_price_in_stock', 'avg_buy_price_adjusted',
                 'holding_shares', 'in_stock_cost_adjusted', 'market_value', 'expected_income',
                 'unrealized_gain', 'unrealized_gain_per']

if IS_STOCK_UNIT_BY_SHARES == 'true':
    stock_unit = 1
else:
    stock_unit = 1000 


def portfolio_frames(sheet): # 子帳戶持股情況

    portfolio_dict = {}
    codes = []
    sub_accounts = sheet.sub_account.unique().tolist()

    # 篩出庫存中還有的股票
    for code in sheet.code.unique().tolist():
        stock_remain_shares = sheet[sheet.code == code].remain_shares.sum()
        if stock_remain_shares != 0:
            codes.append(code)  

    # creating price indexes
    price_dict = portfolio_prices_with_update(codes)


    # 子帳戶
    for acc in sub_accounts:

        df_portfolio = pd.DataFrame(columns=portfolio_col)
        fee_discount_rate = session['sub_account'][acc][0]

        for code in codes:

            sheet_filtered = sheet[(sheet.code == code) & (sheet.sub_account == acc) & (sheet.is_day_trade == 0)]
            
            if not sheet_filtered.empty:

                new_row = []
                now_price = price_dict[code]
                
                new_row.append(code)
                new_row.append(sheet_filtered['name'].iloc[0])
                new_row.append(now_price)

                holding_shares = sheet_filtered.remain_shares.sum() 
                market_value = holding_shares * now_price * stock_unit
                market_value = round(market_value, 2)
                

                # unrealized gain
                discounted_fee_rate = 0.001425 * fee_discount_rate
                expected_income = market_value * (1 - discounted_fee_rate - 0.003) # fee+tax

                in_stock_cost_adjusted_no_fee = sheet_filtered.remain_shares.dot(sheet_filtered.adjusted_buy_cost) * stock_unit
                in_stock_cost_adjusted = round(in_stock_cost_adjusted_no_fee * (1 + discounted_fee_rate))
                unrealized_gain = expected_income - in_stock_cost_adjusted_no_fee * (1 + discounted_fee_rate) # minus the ititial cost
                unrealized_gain = round(unrealized_gain)



                if sheet_filtered.remain_shares.sum() != 0:
                    
                    avg_buy_price_in_stock = sheet_filtered.remain_shares.dot(sheet_filtered.price) / sheet_filtered.remain_shares.sum()
                    avg_buy_price_in_stock = round(avg_buy_price_in_stock, 2)

                    unrealized_gain_per = expected_income / in_stock_cost_adjusted
                    unrealized_gain_per = round(unrealized_gain_per * 100 - 100, 2)

                    avg_buy_price_adjusted = sheet_filtered.remain_shares.dot(sheet_filtered.adjusted_buy_cost) / sheet_filtered.remain_shares.sum()
                    avg_buy_price_adjusted = round(avg_buy_price_adjusted, 2)

                else:
                    unrealized_gain_per = '-'
                    avg_buy_price_in_stock = '-'
                    avg_buy_price_adjusted = '-'


                new_row.extend([avg_buy_price_in_stock, avg_buy_price_adjusted, 
                                holding_shares, in_stock_cost_adjusted, market_value, expected_income, 
                                unrealized_gain, unrealized_gain_per])


                new_row = pd.DataFrame(new_row).T
                new_row.columns = portfolio_col
                df_portfolio = pd.concat([df_portfolio, new_row], ignore_index=True)
    
            total_value = df_portfolio.market_value.sum()
            if total_value != 0:
                df_portfolio['proportion'] = df_portfolio.market_value / total_value * 100
            else:
                df_portfolio['proportion'] = 0
            df_portfolio['proportion'] = df_portfolio['proportion'].astype(np.double).round(2)
            df_portfolio = df_portfolio.sort_values(by=['proportion'], ascending=False)
            # remove sold out stocks
            df_portfolio.drop(df_portfolio[df_portfolio.proportion == 0].index, inplace=True)

        if not df_portfolio.empty:
            portfolio_dict[acc] = df_portfolio

    # 合併檢視

    df_portfolio = pd.DataFrame(columns=portfolio_col)
    avg_rate = 0
    for acc in sub_accounts:
        avg_rate += session['sub_account'][acc][0]
    avg_rate /= len(sub_accounts)

    for code in codes:

        sheet_filtered = sheet[(sheet.code == code) & (sheet.is_day_trade == 0)]
        
        if not sheet_filtered.empty:

            new_row = []
            now_price = price_dict[code]
            
            new_row.append(code)
            new_row.append(sheet_filtered['name'].iloc[0])
            new_row.append(now_price)

            holding_shares = sheet_filtered.remain_shares.sum() 
            market_value = holding_shares * now_price * stock_unit
            market_value = round(market_value, 2)
            

            # unrealized gain
            discounted_fee_rate = 0.001425 * avg_rate
            expected_income = market_value * (1 - discounted_fee_rate - 0.003) # fee+tax

            in_stock_cost_adjusted_no_fee = sheet_filtered.remain_shares.dot(sheet_filtered.adjusted_buy_cost) * stock_unit
            in_stock_cost_adjusted = round(in_stock_cost_adjusted_no_fee * (1 + discounted_fee_rate))
            unrealized_gain = expected_income - in_stock_cost_adjusted_no_fee * (1 + discounted_fee_rate) # minus the ititial cost
            unrealized_gain = round(unrealized_gain)

            if sheet_filtered.remain_shares.sum() != 0:
                
                avg_buy_price_in_stock = sheet_filtered.remain_shares.dot(sheet_filtered.price) / sheet_filtered.remain_shares.sum()
                avg_buy_price_in_stock = round(avg_buy_price_in_stock, 2)

                unrealized_gain_per = expected_income / in_stock_cost_adjusted
                unrealized_gain_per = round(unrealized_gain_per * 100 - 100, 2)

                avg_buy_price_adjusted = sheet_filtered.remain_shares.dot(sheet_filtered.adjusted_buy_cost) / sheet_filtered.remain_shares.sum()
                avg_buy_price_adjusted = round(avg_buy_price_adjusted, 2)

            else:
                unrealized_gain_per = '-'
                avg_buy_price_in_stock = '-'
                avg_buy_price_adjusted = '-'


            new_row.extend([avg_buy_price_in_stock, avg_buy_price_adjusted, 
                            holding_shares, in_stock_cost_adjusted, market_value, expected_income, 
                            unrealized_gain, unrealized_gain_per])


            new_row = pd.DataFrame(new_row).T
            new_row.columns = portfolio_col
            df_portfolio = pd.concat([df_portfolio, new_row], ignore_index=True)
            

        total_value = df_portfolio.market_value.sum()
        if total_value != 0:
            df_portfolio['proportion'] = df_portfolio.market_value / total_value * 100
        else:
            df_portfolio['proportion'] = 0
        df_portfolio['proportion'] = df_portfolio['proportion'].astype(np.double).round(2)
        df_portfolio = df_portfolio.sort_values(by=['proportion'], ascending=False)
        # remove sold out stocks
        df_portfolio.drop(df_portfolio[df_portfolio.proportion == 0].index, inplace=True)

    combined_and_seperate_portfolios = [df_portfolio, portfolio_dict]

    return combined_and_seperate_portfolios

def dashboard_stats(portfolio_dict, sheet):# for all, and each sub-acc

    # portfolio dict: {子帳戶: 庫存股 dataframe}
    dashboard_combined = {'unrealized_gain':0, 'unrealized_ror':0, 
                      'realized_gain':0, 'all_gain':0, 'all_gain_ror':0} 
    dashboard_seperated = {}
    all_principal = 0
    all_in_stock_cost = 0

    sub_accounts = sheet.sub_account.unique().tolist()
    
    for acc in sub_accounts: # loop 各個子帳戶庫存股

        sub_acc_dict = {}
        if acc in portfolio_dict.keys():
        
            df = portfolio_dict[acc] 

            unrealized_gain = round(df.unrealized_gain.sum())
            in_stock_cost = round(df.in_stock_cost_adjusted.sum())
            sub_acc_dict['unrealized_gain'] = unrealized_gain
            if in_stock_cost != 0:
                sub_acc_dict['unrealized_ror'] = round(unrealized_gain / in_stock_cost * 100 , 2)
            else:
                sub_acc_dict['unrealized_ror'] = '-'
        
        else:
            sub_acc_dict['unrealized_gain'] = 0
            sub_acc_dict['unrealized_ror'] = '-'

        realized_gain = round(sheet[(sheet.sub_account == acc) & (sheet.is_settled == 0)].realized_gain.sum())
        all_gain = unrealized_gain + realized_gain
        principal = session['sub_account'][acc][1]

        sub_acc_dict['realized_gain'] = realized_gain
        sub_acc_dict['all_gain'] = all_gain
        sub_acc_dict['all_gain_ror'] = round(all_gain / principal * 100, 2)

        dashboard_seperated[acc] = sub_acc_dict

        dashboard_combined['unrealized_gain'] += unrealized_gain
        dashboard_combined['realized_gain'] += realized_gain
        all_in_stock_cost += in_stock_cost
        all_principal += principal
    
    dashboard_combined['all_gain'] = dashboard_combined['realized_gain'] + dashboard_combined['unrealized_gain']
    if all_in_stock_cost != 0:
        dashboard_combined['unrealized_ror'] = round(dashboard_combined['unrealized_gain'] / all_in_stock_cost * 100, 2)
    else:
        dashboard_combined['unrealized_ror'] = '-'
    if dashboard_combined['unrealized_gain'] == 0:
        dashboard_combined['unrealized_ror'] = '-'
    dashboard_combined['all_gain_ror'] = round(dashboard_combined['all_gain'] / all_principal * 100, 2) 

    return [dashboard_seperated, dashboard_combined]


# structure: 
# 0. dict -> acc: [df of records, gain, ror]
# 1. df of records (combined)
# 2. gain (combined)
# 3. ror (combind)
def realized_stats(filtered):

    realized_stats = [{}, filtered]
    realized_stats[1]['date'] = realized_stats[1]['date'].dt.strftime('%Y-%m-%d')
    total_gain = round(realized_stats[1]['realized_gain'].sum())
    total_cost = round(realized_stats[1]['holding_cost'].sum())
    if total_cost != 0:
        total_ror = round(total_gain / total_cost * 100, 2)
    else:
        total_ror = '-'
    realized_stats.extend([total_gain, total_ror])

    for acc in filtered['sub_account'].unique().tolist():

        tmp_df = realized_stats[1][realized_stats[1]['sub_account'] == acc]        
        realized_stats[0][acc] = [tmp_df]
        # 2 var below won't be 0
        gain = round(tmp_df.realized_gain.sum())
        cost = round(tmp_df.holding_cost.sum())
        if cost != 0:
            ror = round(gain / cost * 100, 2)
        else:
            ror = '-'
        realized_stats[0][acc].extend([gain, ror])

    return realized_stats

def portfolio_to_file(portfolio):

    col_out = ['代碼', '公司名稱', '現價', '買入均價', '調整成本價', '持有數量(張)',  '持有成本',
               '市值', '預估收入', '未實現損益', '未實現損益率', '佔比']

    if not portfolio.empty:

        p2 = portfolio.copy()

        p2.unrealized_gain_per = p2.unrealized_gain_per.astype(str) + '%'    
        p2.unrealized_gain_per[p2.unrealized_gain_per == '-%'] = '-'
        p2.proportion = p2.proportion.astype(str) + '%'

        p2.columns = col_out
    else:
        p2 = pd.DataFrame(columns=col_out)

    return p2


