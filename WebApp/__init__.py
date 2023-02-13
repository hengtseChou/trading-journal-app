### packages
from flask import Flask
from flask_login import LoginManager
import os
from flask_apscheduler import APScheduler

from WebApp.objects import LOGGING_FILE_ID, Job_config, drive_object, config, allLogger

COMPANY_CODE_FILE_ID = config.get('drive', 'COMPANY_CODE_FILE_ID')
USER_INFO_FILE_ID = config.get('drive', 'USER_INFO_FILE_ID')





def create_app():
    
    app = Flask(__name__)
    
    app.config.from_object(Job_config())
    app.config['SECRET_KEY'] = os.urandom(16).hex()

    # # disable https messages
    # flask_log = logging.getLogger('werkzeug')
    # flask_log.setLevel(logging.ERROR) 

    # load user info 
    drive_object.download_file('user_info.json', USER_INFO_FILE_ID)
    allLogger.info('App init. Users downloaded.')
    drive_object.download_file('company_code_index.csv', COMPANY_CODE_FILE_ID)
    allLogger.info('Company code index downloaded.')
    drive_object.download_file('TradingProgram.log', LOGGING_FILE_ID)
    allLogger.info('Logging file loaded')
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '請登入以進行更多操作'
    login_manager.init_app(app)
    

    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
        
    from WebApp.auth.func import User
    @login_manager.user_loader  
    def user_loader(uid):

        user = User()  
        user.id = uid  
        return user

    from WebApp.auth.routes import auth
    from WebApp.new_entry.routes import entry
    from WebApp.portfolio.routes import port

    app.register_blueprint(auth, url_prefix = '/')
    app.register_blueprint(entry, url_prefix = '/')
    app.register_blueprint(port, url_prefix = '/')

    return app