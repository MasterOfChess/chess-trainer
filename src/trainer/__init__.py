from flask import Flask
from flask_session import Session
from .views import index
from .views import play
from .views import explore
from .views import beginner
from .views import medium

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')
Session(app)

play.mod.register_blueprint(explore.mod, url_prefix='/explore')
play.mod.register_blueprint(beginner.mod, url_prefix='/beginner')
play.mod.register_blueprint(medium.mod, url_prefix='/medium')
index.mod.register_blueprint(play.mod, url_prefix='/play')
app.register_blueprint(index.mod, url_prefix='/')
