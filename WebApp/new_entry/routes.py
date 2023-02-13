from flask import Blueprint, session, request, render_template, flash, send_file, redirect, url_for
from flask_login import login_required
import pickle
import pandas as pd
import os

from WebApp.objects import allLogger, drive_object, config
from WebApp.new_entry.func import sheet_output, update_index, create_log_text
from WebApp.new_entry.func import Buy_entry, Sell_entry, Dividend_entry

entry = Blueprint('entry', __name__)

COMPANY_CODE_FILE_ID = config.get('drive', 'COMPANY_CODE_FILE_ID')


## sheet is stored by the order of entry
## new entry will at the bottom
## but displayed reversely
## list of sheet is the older, the further ahead

@entry.route('/new-entry', methods = ['GET', 'POST'])
@login_required
def new_entry():    

    # load file from local
    # it is legal because we downloaded the file when logging in 
    with open(session['uid'] + '.pkl', 'rb') as f:
        user_files = pickle.load(f)
    list_of_sheets = user_files['sheets']
    list_of_records = user_files['records']
    sheet = list_of_sheets[-1]
    

    if request.method == 'POST': 

        if request.form.get('send_trade') == 'send_trade':

            try:
                # formating input
                date = request.form.get('date') # yyyy-mm-dd
                if date == '':
                    flash('未輸入日期，請重新輸入', category='error')
                    allLogger.warn(''.join(['User ', session['username'], ' has entered date incorrectly.']))
                    return render_template('new_entry.html', 
                                            data = sheet_output(sheet), 
                                            username = session['username'],
                                            sub_account = session['sub_account'])

                sub_account = request.form.get('sub_account')                
                code = request.form.get('stockcode')
                shares = request.form.get('shares')
                price = request.form.get('price')

                if code == '' or shares == '' or price == '':
                    flash('有欄位未輸入', category='error')
                    allLogger.warn(''.join(['User ', session['username'], ' has entered numbers incorrectly.']))
                    return render_template('new_entry.html', 
                                            data = sheet_output(sheet), 
                                            username = session['username'],
                                            sub_account = session['sub_account'])

                shares = int(request.form.get('shares'))
                price = float(request.form.get('price'))

                # match stock code with name
                # self-updating with one try
                for i in range(2):
                    try:
                        company_code_index = pd.read_csv('company_code_index.csv')
                        company_code_index.code = company_code_index.code.astype(str)
                        idx = company_code_index.code == code
                        name = company_code_index.company[idx].item()
                    except ValueError:
                        update_index()
                        drive_object.update_file('company_code_index.csv', COMPANY_CODE_FILE_ID)
                        allLogger.info('Company code index updated')
                        continue
                    except Exception as e:
                        flash('找不到對應的股票', category='error')
                        allLogger.warning(''.join(['User ', session['username'], ' entered invalid stock code. Code: ', str(code)]))

                    

                type = request.form.get('type')
                if type == '':
                    flash('未輸入買或賣，請重新輸入', category='error')
                    allLogger.warn(''.join(['User ', session['username'], ' has entered type incorrectly.']))
                    return render_template('new_entry.html', 
                                            data = sheet_output(sheet), 
                                            username = session['username'],
                                            sub_account = session['sub_account'])
                
                day_trade = request.form.get('day_trade')                
                if day_trade == 'day_trade_true':
                    day_trade = True
                else:
                    day_trade = False
                
                if type == 'buy':

                    buy = Buy_entry(date, sub_account, code, name, shares, price, day_trade)
                    buy.entry_to_row()

                    # merge with existing df
                    # update list of sheets, with max length = 100
                    sheet = buy.concat_to_sheet(sheet)
                    list_of_sheets.append(sheet)
                    info = {'date':date, 'type': type, 'sub_account': sub_account, 
                            'code': code, 'name': name, 'day_trade': day_trade, 'amount':shares}
                    log_text = create_log_text(info)
                    list_of_records.append(log_text)
                    if len(list_of_sheets) > 100:
                        list_of_sheets.pop(0)
                    if len(list_of_records) > 100:
                        # keep the status of init or settled around
                        list_of_records.pop(1)
                    user_files = {'sheets':list_of_sheets, 'records': list_of_records}
                    with open(session['uid'] + '.pkl', 'wb') as f:
                        pickle.dump(user_files, f)

                    flash('新增成功', category='success')
                    allLogger.info('User {} added a new buy entry. Info: {}, {}, ${} * {}'.format(session['username'], sub_account, code, price, shares))


                elif type == 'sell':

                    sell = Sell_entry(date, sub_account, code, name, shares, price, day_trade)
                    sell.entry_to_row()

                    try:                        
                        # merge with existing df
                        # update list of sheets, with max length = 100
                        if day_trade:
                            sheet = sell.day_trade_sell_concat(sheet)
                            list_of_sheets.append(sheet)
                        else:
                            sheet = sell.concat_to_sheet_and_sell(sheet)
                            list_of_sheets.append(sheet)
                        info = {'date':date, 'type': type, 'sub_account': sub_account, 
                            'code': code, 'name': name, 'day_trade': day_trade, 'amount':shares}
                        log_text = create_log_text(info)
                        list_of_records.append(log_text)
                        if len(list_of_sheets) > 100:
                            list_of_sheets.pop(0)
                        if len(list_of_records) > 100:
                            # keep the status of init or settled around
                            list_of_records.pop(1)
                        user_files = {'sheets':list_of_sheets, 'records': list_of_records}
                        with open(session['uid'] + '.pkl', 'wb') as f:
                            pickle.dump(user_files, f)

                        flash('新增成功', category='success')
                        allLogger.info('User {} added a new sell entry. Info: {}, {}, ${} * {}'.format(session['username'], sub_account, code, price, shares))
                    except IndexError:
                        flash('剩餘股票數量不符，請重新輸入', category='error')

            except ValueError as e:
                
                flash('找不到對應的股票', category='error')
                allLogger.warning(''.join(['User ', session['username'], ' entered invalid stock code. Code: ', str(code)]))

            except Exception as e:
                flash('輸入有誤，請重新輸入', category='error')
                allLogger.warning([''.join(['User ', session['username'], ' has exception occurred with buy/sell entry. Msg: ', str(e)])])
                
        elif request.form.get('send_div') == 'send_div':

            try:
                
                date_div = request.form.get('date_div')
                if date_div == '':
                    flash('日期輸入有誤，請重新輸入', category='error')
                    allLogger.warn(''.join(['User ', session['username'], ' has entered date incorrectly.']))
                    return render_template('new_entry.html', 
                                            data = sheet_output(sheet), 
                                            username = session['username'],
                                            sub_account = session['sub_account'])

                sub_account_div = request.form.get('sub_account_div')
                code_div = request.form.get('stockcode_div')
                amount = request.form.get('amount')

                if code_div == '' or amount == '':
                    flash('有欄位未輸入', category='error')
                    allLogger.warn(''.join(['User ', session['username'], ' has entered numbers incorrectly.']))
                    return render_template('new_entry.html', 
                                            data = sheet_output(sheet), 
                                            username = session['username'],
                                            sub_account = session['sub_account'])

                amount = int(request.form.get('amount'))

                for i in range(2):
                    try:
                        company_code_index = pd.read_csv('company_code_index.csv')
                        company_code_index.code = company_code_index.code.astype(str)
                        idx = company_code_index.code == code_div
                        name_div = company_code_index.company[idx].item() 
                    except ValueError:
                        update_index()
                        company_code_index
                        drive_object.update_file('company_code_index.csv', COMPANY_CODE_FILE_ID)
                        allLogger.info('Company code index updated')
                        continue
                    except Exception as e:
                        flash('找不到對應的股票', category='error')
                        allLogger.warning(''.join(['User ', session['username'], ' entered invalid stock code. Code: ', str(code_div)]))
               

                div = Dividend_entry(date_div, sub_account_div, code_div, name_div, amount)
                div.entry_to_row()

                # merge with existing df
                # update list of sheets, with max length = 100
                sheet = div.concat_to_sheet(sheet)
                list_of_sheets.append(sheet)
                info = {'date':date_div, 'type': 'div', 'sub_account': sub_account_div, 
                        'code': code_div, 'name': name_div, 'day_trade': False, 'income':amount}
                log_text = create_log_text(info)
                list_of_records.append(log_text)
                if len(list_of_sheets) > 100:
                    list_of_sheets.pop(0)
                if len(list_of_records) > 100:
                    # keep the status of init or settled around
                    list_of_records.pop(1)
                user_files = {'sheets':list_of_sheets, 'records': list_of_records}
                with open(session['uid'] + '.pkl', 'wb') as f:
                    pickle.dump(user_files, f)

                flash('新增成功', category='success')
                allLogger.info('User {} added a new buy entry. Info: {}, {}, ${}'.format(session['username'], sub_account, code_div, amount))

            except Exception as e:
                flash('輸入有誤，請重新輸入', category='error')
                allLogger.warning(''.join(['User ', session['username'], ' has exception occurred with dividend entry. Msg: ', str(e)]))

        elif request.form.get('delete_button_modal') == 'delete_button_modal' or request.form.get('delete_button') == 'delete_button':
                    
            num = request.form.get('delete_number')
            if num == "":
                flash('輸入有誤，請重新輸入', category='error')
            elif not num.isdigit(): # isdigit returns true for integer including zero
                flash('輸入有誤，請重新輸入', category='error')
            elif int(num) == 0:
                flash('輸入有誤，請重新輸入', category='error')
            # 第0筆是init dataframe/ settled dataframe
            elif int(num) >= len(list_of_sheets):
                flash('輸入數量大於現有資料筆數，請重新輸入', category='error')
            else:
                num = int(num)
                # remove last n items
                list_of_sheets = list_of_sheets[:len(list_of_sheets) - num]
                list_of_records = list_of_records[:len(list_of_records) - num]

                user_files = {'sheets': list_of_sheets, 'records': list_of_records}
                with open(session['uid'] + '.pkl', 'wb') as f:
                    pickle.dump(user_files, f)
                sheet = list_of_sheets[-1]
                drive_object.update_file(session['uid']+'.pkl', session['file_id'])
                allLogger.info(''.join(['User ', session['username'], ' removed ', str(num), ' entr(ies) and uploaded.']))
                flash('刪除成功', category='success')

    list_of_records.reverse()    
    return render_template('new_entry.html',
                            data = sheet_output(sheet), 
                            username = session['username'],
                            sub_account = session['sub_account'], 
                            # passing a inverted record, so first element will be the newest
                            records = list_of_records)



@entry.route('/download-sheet', methods=['GET'])
@login_required
def download_sheet():

    new_cols = ['日期', '子帳戶', '代碼', '公司名稱', '類型', '買(股)', '賣(股)', '是否當沖', '價格', 
                '成交價金', '折扣後手續費', '交易稅', '交易成本', 
                '支出', '收入', '已實現損益', '持有成本', '獲益率']

    with open(session['uid'] + '.pkl', 'rb') as f:
        user_files = pickle.load(f)
    list_of_sheets = user_files['sheets']
    sheet = list_of_sheets[-1]
    sheet = sheet[['date', 'sub_account', 'code', 'name', 'type', 'buy', 'sell', 'is_day_trade', 'price', 
                   'deal','discounted_fee', 'tax', 'transaction_cost', 
                   'expense', 'income', 'realized_gain', 'holding_cost', 'rate_of_return']]
    # reverse order
    sheet = sheet.iloc[::-1]
    # change text in is_day_trade
    sheet.is_day_trade = sheet.is_day_trade.astype(str)
    sheet.is_day_trade[sheet.is_day_trade == '1'] = '是'
    sheet.is_day_trade[sheet.is_day_trade == '0'] = '否'
    sheet.rate_of_return = sheet.rate_of_return.astype(str) + '%'

    accs = sheet.sub_account.unique().tolist()
    with pd.ExcelWriter('trade_sheet.xlsx') as writer:
        sheet_full = sheet.copy()
        sheet_full.columns = new_cols
        sheet_full.to_excel(writer, sheet_name='all', index = False)
        new_cols.remove('子帳戶')
        for acc in accs:
            sheet_sep = sheet[sheet.sub_account == acc].copy()        
            sheet_sep.drop('sub_account', axis=1, inplace=True)
            sheet_sep.columns = new_cols
            sheet_sep.to_excel(writer, sheet_name=acc, index = False)
    path = os.getcwd() + '/trade_sheet.xlsx'
    allLogger.info(''.join(['User ', session['username'], ' downloaded trading sheet.']))

    return send_file(path, as_attachment=True)





@entry.route('/upload-current-records', methods = ['GET'])
def upload_current_records():
    try:
        drive_object.update_file(session['uid']+'.pkl', session['file_id'])
        allLogger.info(''.join(['Trading records of user ', session['username'], ' has uploaded. ']))
        flash('存檔成功', category='success')                 
    except KeyError:
        allLogger.warn(''.join(['Drive tried to upload without logging in.']))
        flash('身分認證錯誤', category='error')
    except Exception as e:
        allLogger.warn(''.join(['Unable to save file to drive.']))
        flash('伺服器連線異常', category='error')
    return redirect(url_for('entry.new_entry'))