from flask import Blueprint, session, render_template, request, flash, send_file, redirect, url_for
from flask_login import login_required
import pickle
import time
import os
import pandas as pd
from datetime import datetime

import asyncio

from WebApp.objects import allLogger, drive_object, FLASK_ENV
from WebApp.portfolio.func import portfolio_to_file, dashboard_stats, portfolio_frames, realized_stats, portfolio_col
from WebApp.portfolio.aio import settle_prices, get_or_create_eventloop
from WebApp.new_entry.func import trade_sheet_col


port = Blueprint('port', __name__)

@port.route('/portfolio', methods = ['GET', 'POST'])
@login_required
def portfolio():

    with open(session['uid'] + '.pkl', 'rb') as f:
        users_file = pickle.load(f)
    list_of_sheets = users_file['sheets']
    sheet = list_of_sheets[-1]

    if not sheet.empty:

        start = time.time()
        # 庫存未實現        
        combined_and_seperate_portfolios = portfolio_frames(sheet)
        allLogger.info(''.join(['Done portfolio dataframes for user ', session['username'], '. Time spent: ', str(round(time.time() - start)), ' s']))

        # 計算已實現以及未實現數據
        stats = dashboard_stats(combined_and_seperate_portfolios[1], sheet)
        # 輸出庫存股數據
        with pd.ExcelWriter('portfolio.xlsx') as writer:
            portfolio_to_file(combined_and_seperate_portfolios[0]).to_excel(writer, sheet_name='all', index = False)
            for acc, df in combined_and_seperate_portfolios[1].items():            
                portfolio_to_file(df).to_excel(writer, sheet_name=acc, index = False)

    else:
        # 庫存未實現
        combined_and_seperate_portfolios = [pd.DataFrame(columns=portfolio_col), {}]
        # 已實現以及未實現數據
        stats = [{}, {'unrealized_gain':0, 'unrealized_ror':'-', 
                      'realized_gain':0, 'all_gain':0, 'all_gain_ror':0}]
        # 輸出庫存股數據
        empty_portfolio = pd.DataFrame(columns=['代碼', '公司名稱', '現價', '持有張數', '買入均價', '賣出均價', '支出(含交易成本)', 
                                                '收入', '市值', '未實現損益', '未實現損益率', '佔比'])
        empty_portfolio.to_excel('portfolio.xlsx', index=False)   
    


    if request.method != 'POST':
        # using sheet as operation base
        # default time select: this month
        sheet['date'] = pd.to_datetime(sheet['date'], format='%Y-%m-%d')
        year, month = datetime.now().year, datetime.now().month
        filtered_sells = sheet[(sheet['date'].dt.month == month) & (sheet['date'].dt.year == year) & ((sheet.type == 'sell') | (sheet.type == 'dividend'))]

        # change text in is_day_trade; reverse order to make latest at top
        filtered_sells.is_day_trade = filtered_sells.is_day_trade.astype(str)
        filtered_sells.is_day_trade[filtered_sells.is_day_trade == '1'] = '是'
        filtered_sells.is_day_trade[filtered_sells.is_day_trade == '0'] = '否'
        filtered_sells = filtered_sells.iloc[::-1]
        filtered_sells = realized_stats(filtered_sells)
    else:
        if request.form.get('this_month') == 'this_month':

            sheet['date'] = pd.to_datetime(sheet['date'], format='%Y-%m-%d')
            year, month = datetime.now().year, datetime.now().month
            filtered_sells = sheet[(sheet['date'].dt.month == month) & (sheet['date'].dt.year == year) & ((sheet.type == 'sell') | (sheet.type == 'dividend'))]
            filtered_sells.is_day_trade = filtered_sells.is_day_trade.astype(str)
            filtered_sells.is_day_trade[filtered_sells.is_day_trade == '1'] = '是'
            filtered_sells.is_day_trade[filtered_sells.is_day_trade == '0'] = '否'
            filtered_sells = filtered_sells.iloc[::-1]
            filtered_sells = realized_stats(filtered_sells)

        elif request.form.get('last_month') == 'last_month':

            sheet['date'] = pd.to_datetime(sheet['date'], format='%Y-%m-%d')
            year, month = datetime.now().year, datetime.now().month - 1
            if month == 0:
                year, month = year - 1, 12
            filtered_sells = sheet[(sheet['date'].dt.month == month) & (sheet['date'].dt.year == year) & ((sheet.type == 'sell') | (sheet.type == 'dividend'))]
            filtered_sells.is_day_trade = filtered_sells.is_day_trade.astype(str)
            filtered_sells.is_day_trade[filtered_sells.is_day_trade == '1'] = '是'
            filtered_sells.is_day_trade[filtered_sells.is_day_trade == '0'] = '否'
            filtered_sells = filtered_sells.iloc[::-1]
            filtered_sells = realized_stats(filtered_sells)
        
        elif request.form.get('custom') == 'custom':

            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')

            if start_date != '' and end_date != '':

                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = datetime.strptime(end_date, '%Y-%m-%d')

                if start_date <= end_date:

                    sheet['date'] = pd.to_datetime(sheet['date'], format='%Y-%m-%d')
                    
                    filtered_sells = sheet[(sheet['date'] >= start_date) & (sheet['date'] <= end_date) & ((sheet.type == 'sell') | (sheet.type == 'dividend'))]
                    filtered_sells.is_day_trade = filtered_sells.is_day_trade.astype(str)
                    filtered_sells.is_day_trade[filtered_sells.is_day_trade == '1'] = '是'
                    filtered_sells.is_day_trade[filtered_sells.is_day_trade == '0'] = '否'
                    filtered_sells = filtered_sells.iloc[::-1]
                    filtered_sells = realized_stats(filtered_sells)

                else:
                    flash('開始日期不可小於截止日期', category='error')
                    tmp_df = pd.DataFrame(columns=trade_sheet_col)
                    filtered_sells = [{}, tmp_df, 0, '-']
                    allLogger.warn(''.join(['User ', session['username'], ' has entered dates in incorrect order.']))

            else:
                flash('開始或截止日期輸入有誤，請重新輸入', category='error')
                tmp_df = pd.DataFrame(columns=trade_sheet_col)
                filtered_sells = [{}, tmp_df, 0, '-']
                allLogger.warn(''.join(['User ', session['username'], ' has entered dates incorrectly.']))

            

    return render_template('portfolio.html', 
                            portfolio = combined_and_seperate_portfolios, 
                            stats = stats,
                            username = session['username'],
                            time_select = filtered_sells)


@port.route('/download-portfolio', methods=['GET'])
@login_required
def download_portfolio():

    path = os.getcwd() + '/portfolio.xlsx'
    allLogger.info(''.join(['User ', session['username'], ' downloaded portfolio sheets.']))
    return send_file(path, as_attachment=True)

@port.route('/download-realized', methods=['GET'])
@login_required
def download_realized():

    new_cols = ['日期', '子帳戶', '代碼', '公司名稱', '賣(股)', '價格',
                '是否當沖', '成交價金', '折扣後手續費', '交易稅', '交易成本', '收入', 
                '已實現損益', '持有成本', '獲益率']

    with open(session['uid'] + '.pkl', 'rb') as f:
        user_files = pickle.load(f)
    list_of_sheets = user_files['sheets']
    sheet = list_of_sheets[-1]
    sheet = sheet[(sheet.type == 'sell') | (sheet.type == 'dividend')]
    sheet = sheet[['date', 'sub_account', 'code', 'name', 'sell', 'price',
                   'is_day_trade', 'deal', 'discounted_fee', 'tax', 'transaction_cost', 'income', 
                   'realized_gain', 'holding_cost', 'rate_of_return']]
    # reverse order
    sheet = sheet.iloc[::-1]
    # change text in is_day_trade
    sheet.is_day_trade = sheet.is_day_trade.astype(str)
    sheet.is_day_trade[sheet.is_day_trade == '1'] = '是'
    sheet.is_day_trade[sheet.is_day_trade == '0'] = '否'
    sheet.rate_of_return = sheet.rate_of_return.astype(str) + '%'

    accs = sheet.sub_account.unique().tolist()
    with pd.ExcelWriter('realized_trade.xlsx') as writer:
        sheet_full = sheet.copy()
        sheet_full.columns = new_cols
        sheet_full.to_excel(writer, sheet_name='all', index = False)
        new_cols.remove('子帳戶')
        for acc in accs:
            sheet_sep = sheet[sheet.sub_account == acc].copy()        
            sheet_sep.drop('sub_account', axis=1, inplace=True)
            sheet_sep.columns = new_cols
            sheet_sep.to_excel(writer, sheet_name=acc, index = False)
    path = os.getcwd() + '/realized_trade.xlsx'
    allLogger.info(''.join(['User ', session['username'], ' downloaded realized records.']))

    return send_file(path, as_attachment=True)



# 要改成抓完價格以後去改pkl裡面的所有紀錄
@port.route('/quarterly-settlement', methods=['GET'])
@login_required
def settle():
    # settle 過後 
    # 1. 交易歷程中有售出之已實現標記 is_settled，在已實現統計中將不採計
    # 2. 調整剩餘的庫存股至上一季季末收盤價
    # 只會結算到目前有持有的那些
    start_time = time.time()
    with open(session['uid'] + '.pkl', 'rb') as f:
        user_files = pickle.load(f)
    list_of_sheets = user_files['sheets']
    sheet = list_of_sheets[-1]

    # 篩出庫存中還有的股票
    codes = []
    for code in sheet.code.unique().tolist():
        stock_remain_shares = sheet[sheet.code == code].remain_shares.sum()
        if stock_remain_shares != 0:
            codes.append(code) 

    # create price index of last quarter
    loop = get_or_create_eventloop()
    if FLASK_ENV == 'DEV':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    price_dict = asyncio.run(settle_prices(codes))
    loop.close()

    ## the settlement
    # 將 sell 跟 dividend 的紀錄標上 is_settled，讓已實現不會被抓
    sheet.loc[sheet.realized_gain != 0, ['is_settled']] = 1
    # change in stock into last quarter closing
    for code, close in price_dict.items():
        sheet.adjusted_buy_cost[sheet.code == code] = close

    user_files = {'sheets':[sheet], 'records':['settled']}
    with open(session['uid'] + '.pkl', 'wb') as f:
        pickle.dump(user_files, f)
    if FLASK_ENV != 'DEV':
        drive_object.update_file(session['uid']+'.pkl', session['file_id'])
    allLogger.info(''.join(['Settled trading records of user ', session['username'], ' . Time spent:', str(round(time.time() - start_time, 2)), 's']))

    return redirect(url_for('port.portfolio'))


@port.route('/undo-settle', methods = ['GET'])
@login_required
def undo_settle():

    with open(session['uid']+'.pkl', 'rb') as f:
        file = pickle.load(f)

    list_of_sheets = file['sheets']
    for sheet in list_of_sheets:

        sheet['is_day_trade'] = 0
        sheet['is_settled'] = 0
        sheet['adjusted_buy_cost'] = 0
        sheet.adjusted_buy_cost[sheet.type == 'buy'] = sheet.price

    user_files = {}
    user_files['records'] = file['records']
    user_files['sheets'] = [sheet]

    with open(session['uid']+'.pkl', 'wb') as f:
        pickle.dump(user_files, f)
    if FLASK_ENV != 'DEV':
        drive_object.update_file(session['uid']+'.pkl', session['file_id'])
    allLogger.info('Undo settlement annd uploaded for user {}'.format(session['username']))

    return redirect(url_for('auth.portfolio'))
