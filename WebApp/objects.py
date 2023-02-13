
import logging
from datetime import datetime
import pytz
import configparser

from WebApp.drive_func.func import Drive


class Formatter(logging.Formatter):
    """override logging.Formatter to use an aware datetime object"""

    def converter(self, timestamp):
        # Create datetime in UTC
        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        # Change datetime's timezone
        return dt.astimezone(pytz.timezone('Asia/Taipei'))

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            try:
                s = dt.isoformat(timespec='milliseconds')
            except TypeError:
                s = dt.isoformat()
        return s


def logger():
    
    #1.setup log path
    logName = 'TradingProgram.log'


    #2.create logger, then setLevel
    global allLogger
    allLogger = logging.getLogger('allLogger')
    allLogger.setLevel(logging.DEBUG)

    #3.create file handler, then setLevel
    #create file handler
    fileHandler = logging.FileHandler(logName, mode='a', encoding='utf-8')
    fileHandler.setLevel(logging.INFO)

    #4.create stram handler, then setLevel
    #create stream handler
    streamHandler = logging.StreamHandler()
    streamHandler.setLevel(logging.INFO)

    #5.create formatter, then handler setFormatter
    AllFormatter = Formatter("%(asctime)s - [line:%(lineno)d] - %(levelname)s: %(message)s", '%Y-%m-%d %H:%M:%S')
    fileHandler.setFormatter(AllFormatter)
    streamHandler.setFormatter(AllFormatter)

    #6.logger addHandler
    allLogger.addHandler(fileHandler)
    allLogger.addHandler(streamHandler)


logger()
config = configparser.ConfigParser()
config.read('creds/config.ini')
drive_object = Drive()

# 設定輸入為張數 則為FALSE
IS_STOCK_UNIT_BY_SHARES = config.get('flask', 'IS_STOCK_UNIT_BY_SHARES')
# 若上傳到SERVER 則SET POLICY 為FALSE
FLASK_ENV = config.get('flask', 'FLASK_ENV')
LOGGING_FILE_ID = config.get('drive', 'LOGGING_FILE_ID')



def upload_log():
    drive_object.update_file('TradingProgram.log', LOGGING_FILE_ID)
    allLogger.info('Logging updated to the cloud.')


class Job_config(object):
    JOBS = [
        {
            'id': 'job1',
            'func': upload_log,
            'trigger': 'interval',
            'seconds': 600
        }
    ]

    SCHEDULER_API_ENABLED = True
