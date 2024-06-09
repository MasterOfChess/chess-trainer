from flask import Flask
from .views import index
from .views import play

app = Flask(__name__, instance_relative_config=True)

app.config.from_object('config')
app.config.from_pyfile('config.py')

index.mod.register_blueprint(play.mod, url_prefix='/play')
app.register_blueprint(index.mod, url_prefix='/')
