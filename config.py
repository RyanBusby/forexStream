import os

u, p = os.getenv('uname'), os.getenv('upass')
SECRET_KEY = os.urandom(16).hex()
DEBUG = False

# https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/
SQLALCHEMY_DATABASE_URI = f'postgresql://{u}:{p}@localhost:5432/forexticks'
SQLALCHEMY_TRACK_MODIFICATIONS = False
