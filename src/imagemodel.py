from google.appengine.api import users
from google.appengine.ext import db
import cloudstorage as gcs

# image slot
#----------------------------------------------------
class Image(db.Model):    
# workspace for images
    header = db.TextProperty(indexed=False)
    cs_file = db.TextProperty(indexed=False)
    user = db.UserProperty(auto_current_user_add=True,indexed=False) 
#----------------------------------------------------       

def get_image(user_id=None):
    if not user_id:
        user = users.get_current_user()
        if not user:
            return None
        user_id = user.user_id()   
    imstr = 'Image'
    key = db.Key.from_path(imstr, user_id)
    img = db.get(key)
    if not img:
        img = eval(imstr+'(key_name=user_id)')
        img.header='no data'     
    return img   

def get_header(user_id=None):  
    img = get_image(user_id)   
    return img.header       

def get_blob(user_id=None):
    img = get_image(user_id)  
    cs_file = img.cs_file        
    with gcs.open(cs_file,'r') as f:
        result = f.read()
        f.close()
    return result 



