import json
import bcrypt
from flask import Blueprint, render_template, request, flash, session, redirect, url_for
from flask_login import login_required, login_user, logout_user
import pandas as pd
import pickle


from WebApp.objects import allLogger, config, drive_object, LOGGING_FILE_ID
from WebApp.auth.func import User, id_generator, is_legal_password, is_legal_rate
from WebApp.new_entry.func import trade_sheet_col


## objects

auth = Blueprint('auth', __name__)

## variables

USER_INFO_FILE_ID = config.get('drive', 'USER_INFO_FILE_ID')


## pages

@auth.route('/login', methods = ['POST', 'GET']) 
def login(): 

    # retrive form input
    if request.method == 'POST':
        username = request.form.get('Username')
        password = request.form.get('password')
        with open('user_info.json', 'r') as f:
            user_info = json.load(f)

        user_found = 0
        pw_checked = 0
        # check password
        for key, value in user_info.items():
            if value['username'] == username:
                user_found = 1                
                if bcrypt.checkpw(password.encode('utf8'), value['pw'].encode('utf8')):
                    pw_checked = 1
                    uid = key
        

        if user_found == 0:
            flash('用戶名不存在，請再試一次', category='error')
        else:
            if pw_checked == 0:
                flash('無效的密碼，請再試一次', category='error')
            else:

                # change stutus to login
                user = User()  
                user.id = uid
                login_user(user)
                allLogger.info(''.join(['User ', username, ' login successfully.']))
                
                # save user related info in session
                session['uid'] = uid                
                session['username'] = user_info[uid]['username']
                session['file_id'] = user_info[uid]['file_id']
                session['sub_account'] = user_info[uid]['sub_account']

                # download file to local                                
                drive_object.download_file(uid + '.pkl', session['file_id'])
                allLogger.info(''.join(['User ', username, '\'s trading records loaded.']))
                flash('登入成功', category='success')

                return redirect(url_for('entry.new_entry'))

    return render_template('login.html')


@auth.route('/logout', methods = ['GET'])
@login_required
def logout():
    logout_user()
    allLogger.info(''.join(['User ', session['username'], ' has logged out. ']))
    return redirect(url_for('entry.new_entry'))
        


    
    

# 4 keys in a user info:
# username - string
# password(crypted) - string
# sub account, with name and its discount rate - dict
# file id - string

@auth.route('/register', methods = ['POST', 'GET']) 
def register(): 
    if request.method == 'POST':

        # init input
        username = request.form.get('Username')
        password = request.form.get('password')
        discount_rate = request.form.get('discount_rate')
        principal = request.form.get('principal')

        # check if input legal
        if username == '' or password == '' or discount_rate == '' or principal == '':
            flash('輸入有誤，請再試一次', category='error')
            return render_template('register.html')
        if not is_legal_password(password):
            flash('無效的密碼，請再試一次', category='error')
            return render_template('register.html')
        if not is_legal_rate(discount_rate):
            flash('無效的手續費折數，請再試一次', category='error')
            return render_template('register.html')
        if not principal.isdigit():
            flash('本金輸入有誤，請再試一次', category='error')
            return render_template('register.html')


        # check if user exist
        with open('user_info.json', 'r') as f:
            user_info = json.load(f)
        user_already_exist = False

        for value in user_info.values():
            if value['username'] == username:
                user_already_exist = True
                flash('此用戶名已被註冊，請再試一次', category='error')
        
        # if user not exist, then register 
        if user_already_exist == False:
                        
            password = password.encode('utf-8')
            hashed_pw = bcrypt.hashpw(password, bcrypt.gensalt(10))
            hashed_pw = hashed_pw.decode('utf-8')
            principal = int(principal)
            sub_account = {username:[float(discount_rate), principal]}

            new_user_dict = {'username':username, 'pw':hashed_pw, 'sub_account':sub_account}
                
            # make sure uid is unique
            uid = id_generator(4)
            while (uid in user_info.keys()):
                uid = id_generator(4)

            # initial sheet 
            # save this as list to pickle
            # upload local file(.pkl) to cloud
            init_df = pd.DataFrame(columns=trade_sheet_col)
            list_of_sheets = [init_df]
            list_of_records = ['init']
            user_files = {'sheets': list_of_sheets, 'records': list_of_records}
            with open(uid + '.pkl', 'wb') as f:
                pickle.dump(user_files, f)
            file_id = drive_object.create_new_file(uid + '.pkl', uid, True)
            new_user_dict['file_id'] = file_id
            # done user settings
            
            # now update new register info to cloud
            user_info[uid] = new_user_dict
            with open('user_info.json', 'w') as f:
                json.dump(user_info, f)
            try:
                drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                allLogger.info(''.join(['Created new user ', username, '.']))
                flash('帳戶創建成功', category='success')
            except Exception as e:
                allLogger.warn(''.join(['Unable to upload. Message: ', str(e)]))
                flash('無法創建，伺服器連線異常', category='error')
                

            return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth.route('/settings', methods = ['GET', 'POST'])
@login_required
def settings():

    if request.method == 'POST':

        if request.form.get('new_sub_acc') == 'new_sub_acc':
            sub_acc_name = request.form.get('sub_acc_name')
            sub_acc_rate = request.form.get('sub_acc_rate')
            principal = request.form.get('sub_acc_principal')
            if sub_acc_name == "" or sub_acc_rate == '' or principal == '':
                flash('有欄位未填寫，請再試一次', category='error')
            elif sub_acc_name in session['sub_account']:
                flash('子帳戶名稱已存在，請再試一次', category='error')
            elif not is_legal_rate(sub_acc_rate) :
                flash('手續費折數輸入有誤，請再試一次', category='error')
            elif not principal.isdigit():
                flash('本金輸入有誤，請再試一次', category='error')
            else:

                with open('user_info.json', 'r') as f:
                    user_info = json.load(f)
                user_info[session['uid']]['sub_account'][sub_acc_name] = [float(sub_acc_rate), int(principal)]
                # also need to update in the session data
                session['sub_account'] = user_info[session['uid']]['sub_account']
                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)
                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    allLogger.info(''.join(['User ', session['username'], ' has added a new sub-acount ', sub_acc_name, '.']))
                    flash('子帳戶新增成功', category='success')
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法修改：伺服器連線異常，請稍後再試', category='error')


        elif request.form.get('send_new_rate') == 'send_new_rate':

            acc = request.form.get('new_rate_acc')
            new_rate = request.form.get('new_rate')

            if not is_legal_rate(new_rate):
                flash('子帳戶新折數輸入有誤，請再試一次', category='error')
            else:
                with open('user_info.json', 'r') as f:
                    user_info = json.load(f)
                user_info[session['uid']]['sub_account'][acc][0] = float(new_rate)
                # also need to update in the session data
                session['sub_account'] = user_info[session['uid']]['sub_account']
                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)
                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    flash('子帳戶手續費折數修改成功', category='success')
                    allLogger.info(''.join(['User ', session['username'], ' has changed the discount rate of sub-acount ', acc, '.']))
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法修改：伺服器連線異常，請稍後再試', category='error')

        elif request.form.get('send_new_principal') == 'send_new_principal':

            acc = request.form.get('new_principal_acc')
            new_principal = request.form.get('new_principal')

            if new_principal == '':
                flash('子帳戶新本金輸入有誤，請再試一次', category='error')
            elif not new_principal.isdigit():
                flash('子帳戶新本金輸入有誤，請再試一次', category='error')
            else:
                with open('user_info.json', 'r') as f:
                    user_info = json.load(f)
                user_info[session['uid']]['sub_account'][acc][1] = int(new_principal)
                # also need to update in the session data
                session['sub_account'] = user_info[session['uid']]['sub_account']
                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)
                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    flash('子帳戶起始本金修改成功', category='success')
                    allLogger.info(''.join(['User ', session['username'], ' has changed the principal of sub-acount ', acc, '.']))
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法修改：伺服器連線異常，請稍後再試', category='error')

        elif request.form.get('send_new_name') == 'send_new_name':
            acc = request.form.get('new_name_acc')
            new_name = request.form.get('new_name')

            sub_acc_dict_copy = session['sub_account']
            del sub_acc_dict_copy[acc]
            exist_names = sub_acc_dict_copy.keys()

            if new_name == '':
                flash('新名稱輸入有誤，請再試一次', category='error')
            elif new_name in exist_names:
                flash('新名稱已使用過，請再試一次', category='error')
            else:
                # changes name
                with open('user_info.json', 'r') as f:
                    user_info = json.load(f)
                user_info[session['uid']]['sub_account'][new_name] = user_info[session['uid']]['sub_account'].pop(acc)
                session['sub_account'] = user_info[session['uid']]['sub_account']
                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)

                # changes all records in trading
                with open(session['uid'] + '.pkl', 'rb') as f:
                    user_files = pickle.load(f)
                list_of_sheets = user_files['sheets']
                for i in range(len(list_of_sheets)):
                    list_of_sheets[i]['sub_account'] = list_of_sheets[i]['sub_account'].replace(acc, new_name)
                user_files['sheets'] = list_of_sheets
                with open(session['uid'] + '.pkl', 'wb') as f:
                    pickle.dump(user_files, f)
                    
                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    drive_object.update_file(session['uid']+'.pkl', session['file_id'])
                    flash('子帳戶名稱修改成功', category='success')
                    allLogger.info(''.join(['User ', session['username'], ' has changed the name of sub-acount ', acc, ' to ', new_name, '.']))
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法修改：伺服器連線異常，請稍後再試', category='error')


        elif request.form.get('send_deletion') == 'send_deletion':

            acc = request.form.get('delete_acc')
            with open('user_info.json', 'r') as f:
                user_info = json.load(f)

            if len(user_info[session['uid']]['sub_account']) == 1:
                flash('帳戶中必須至少存在一子帳戶', category='error')
            else:   
                # delete sub account in users.json
                user_info[session['uid']]['sub_account'].pop(acc, None)
                session['sub_account'] = user_info[session['uid']]['sub_account']
                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)
                # changes all records in trading
                with open(session['uid'] + '.pkl', 'rb') as f:
                    user_files = pickle.load(f)
                list_of_sheets = user_files['sheets']
                for i in range(len(list_of_sheets)):
                    list_of_sheets[i] = list_of_sheets[i][list_of_sheets[i]['sub_account'] != acc]
                user_files['sheets'] = list_of_sheets
                with open(session['uid'] + '.pkl', 'wb') as f:
                    pickle.dump(user_files, f)                

                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    drive_object.update_file(session['uid']+'.pkl', session['file_id'])
                    flash('子帳戶刪除成功', category='success')
                    allLogger.info(''.join(['User ', session['username'], ' has deleted sub-acount ', acc, '.']))
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法刪除：伺服器連線異常，請稍後再試', category='error')

        elif request.form.get('pw_change') == 'pw_change':

            old_pw = request.form.get('old_password')
            new_pw = request.form.get('new_password')
            new_pw_confirm = request.form.get('new_password_confirm')
            uid = session['uid']

            with open('user_info.json', 'r') as f:
                user_info = json.load(f)
            user_pw = user_info[uid]['pw']

            if old_pw == '' or new_pw == '' or new_pw_confirm == '':
                flash('有欄位未填寫，請再試一次', category='error')
            elif not bcrypt.checkpw(old_pw.encode('utf8'), user_pw.encode('utf8')):
                #confirmed user identity
                flash('舊密碼輸入有誤，請重新輸入', category='error')
            elif new_pw != new_pw_confirm or is_legal_password(new_pw) or is_legal_password(new_pw_confirm):
                flash('新密碼輸入有誤，請重新輸入', category='error')
            else:
                # make pw hange
                new_pw = new_pw.encode('utf-8')
                new_hashed_pw = bcrypt.hashpw(new_pw, bcrypt.gensalt(10))
                new_hashed_pw = new_hashed_pw.decode('utf-8')
                user_info[uid]['pw'] = new_hashed_pw

                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)
                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    flash('成功變更密碼', category='success')
                    allLogger.info(''.join(['User ', session['username'], 'has changed the password. ']))
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法修改：伺服器連線異常，請稍後再試', category='error')

        elif request.form.get('username_change') == 'username_change':
            
            new_username = request.form.get('new_username')

            with open('user_info.json', 'r') as f:
                user_info = json.load(f)
            uid = session['uid']
            all_usernames = []
            for user in user_info.values():
                all_usernames.append(user['username'])

            if new_username == '':
                flash('有欄位未填寫，請再試一次', category='error')
            elif new_username in all_usernames:
                flash('新用戶名已有人使用過，請再試一次', category='error')
            else:
                old_username = user_info[uid]['username']
                user_info[uid]['username'] = new_username
                session['username'] = new_username

                with open('user_info.json', 'w') as f:
                    json.dump(user_info, f)
                try:
                    drive_object.update_file('user_info.json', USER_INFO_FILE_ID)
                    flash('成功變更用戶名', category='success')
                    allLogger.info(''.join(['User ', old_username, 'has changed username to ', session['username'], '.']))
                except Exception as e:
                    allLogger.warn(''.join(['Unable to upload file. Message: ', str(e)]))
                    flash('無法修改：伺服器連線異常，請稍後再試', category='error')               




    return render_template('settings.html', 
                            sub_account = session['sub_account'], 
                            username = session['username'])


### simple and unimportant routes

@auth.route('/manual', methods = ['GET'])
def manual():
    return render_template('manual.html')


@auth.route('/wake', methods=['GET'])
def wake():
    return 'OK'

# also used in health check
@auth.route('/', methods = ['GET'])
@login_required
def entrance():    
    return redirect(url_for('auth.login'))



@auth.route('/log', methods = ['GET'])
def check_log():
    log_lines = []
    with open('TradingProgram.log', encoding='utf-8', errors='ignore') as f:
        log_file = f.readlines()    
    for line in log_file:
        log_lines.append(line)
    log_lines.reverse()

    return render_template('log.html', log = log_lines)


@auth.route('/reload', methods = ['GET'])
def reload_files():

    COMPANY_CODE_FILE_ID = config.get('drive', 'COMPANY_CODE_FILE_ID')
    USER_INFO_FILE_ID = config.get('drive', 'USER_INFO_FILE_ID')


    drive_object.download_file('user_info.json', USER_INFO_FILE_ID)
    allLogger.info('Users info re-downloaded.')
    drive_object.download_file('company_code_index.csv', COMPANY_CODE_FILE_ID)
    allLogger.info('Company code index re-downloaded.')
    

    return redirect(url_for('entry.new_entry'))