from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import time 
import random
import configparser


config = configparser.ConfigParser()
config.read('creds/config.ini')

PARENT_FOLDER_ID = config.get('drive', 'PARENT_FOLDER_ID')
RETRIES = config.get('drive', 'RETRIES')

# client_secrets.json do not change
# creds will auto refresh(only need to upload one version)
def authorize_drive():

    gauth = GoogleAuth()
    gauth.DEFAULT_SETTINGS['client_config_file'] = "creds/client_secrets.json"

    gauth.LoadCredentialsFile("creds/mycreds.txt")
    if gauth.credentials is None:
        # Authenticate if they're not there
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
    # Refresh them if expired
        gauth.Refresh()
    else:
        # Initialize the saved creds
        gauth.Authorize()
    # Save the current credentials to a file
    gauth.SaveCredentialsFile("creds/mycreds.txt")
    
    return GoogleDrive(gauth)

class Drive(object):

    def __init__(self):
        self.drive = authorize_drive()        

    # will need create(new), download(exist), upload(exist)
    # create also need to return id

    def create_new_file(self, local_path, new_name, return_id=False):
        count = 0
        file = self.drive.CreateFile({'title':new_name, 'parents':[{'id':PARENT_FOLDER_ID}]})
        file.SetContentFile(local_path)
        while True:
            try:
                file.Upload()
                if return_id == True:
                    return file['id']
            except:                
                if count == RETRIES:                    
                    raise
                sleep = 2 ** count + random.uniform(0, 1)
                time.sleep(sleep)
                count += 1

    def download_file(self, file_name, file_id):
        # retry with backoff
        count = 0
        file = self.drive.CreateFile({'id':file_id})
        while True:
            try:
                file.GetContentFile(file_name)
                return
            except:
                if count == RETRIES:                    
                    raise
                sleep = 2 ** count + random.uniform(0, 1)
                time.sleep(sleep)
                count += 1                
        
    
    def update_file(self, file_name, file_id):
        # retry with backoff
        count = 0
        file = self.drive.CreateFile({'id': file_id})
        file.SetContentFile(file_name)
        while True:
            try:                
                file.Upload()
                return
            except:
                if count == RETRIES:
                    raise
                sleep = 2 ** count + random.uniform(0, 1)
                time.sleep(sleep)
                count += 1    