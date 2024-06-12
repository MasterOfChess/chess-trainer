from flask import render_template, url_for, redirect
from flask import request, session, Blueprint
import os
import dataclasses
import logging
import json
from .paths import BOOKS_DIR

mod = Blueprint('index', __name__)

logging.basicConfig(
    format='%(asctime)s:%(threadName)s: %(filename)s:%(lineno)d %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


# Openings config
@dataclasses.dataclass
class Opening:
    book: str
    name: str
    games: int = 0
    moves: int = 0
    img: str | None = None
    description: str = ''


def init_openings() -> list[Opening]:
    with open(os.path.join(BOOKS_DIR, 'config.json'), encoding='utf-8') as f:
        config = json.load(f)
        return list(map(lambda opening: Opening(**opening), config))


OPENINGS = init_openings()

# Session fields
# bot_lvl: int [1, 20]
# freedom_degree: int [1, 6]
# color: white | black
# current_book: int
# current_book_path: str
# in_book: bool
# initialized: bool
# nickname: str
# color_mode: dark | light
# game: str
# fen: str


def change_book(new_book):
    logger.debug('Opening book: %s.bin', new_book)
    book_idx = [o.book for o in OPENINGS].index(new_book)
    session['current_book'] = book_idx
    session['current_book_path'] = os.path.join(BOOKS_DIR, new_book + '.bin')


@mod.before_request
def init_config():
    if 'initialized' not in session:
        session.permanent = True
        session['initialized'] = True
        session['current_book'] = 0
        session['current_book_path'] = os.path.join(BOOKS_DIR,
                                                    OPENINGS[0].book + '.bin')
        session['color_mode'] = 'dark'
        session['nickname'] = 'Default Player'
        session['color'] = 'white'


@mod.route('/choose_color', methods=['POST'])
def choose_color():
    color = request.form.get('color')
    color = 'white' if color == 'white-color' else 'black'
    session['color'] = color
    return {
        'response': 'success',
        'redirect': url_for('index.choose_mode')
    }

# The goal is 4 modes:
# - explore: play against the bot with the selected opening
# - beginner: play against the bot with the selected opening, but with hints and move suggestions
# - medium: play against the bot with the selected opening, but with hints but no move suggestions
# - advanced: play against the bot with the selected opening with hints, but bot can play sidelines
# - expert: play against the bot with the selected opening without hints, bot can play sidelines

@mod.route('/choose_mode', methods=['GET', 'POST'])
def choose_mode():
    if request.method == 'GET':
        return render_template('choose_mode.html')
    mode = request.form.get('mode')
    session['mode'] = mode
    if mode == 'explore':
        return {
            'response': 'success',
            'redirect': url_for('index.play.explore.explore_new_game')
        }
    if mode == 'beginner':
        return {
            'response': 'success',
            'redirect': url_for('index.play.beginner.beginner_new_game')
        }
    if mode == 'medium':
        return {
            'response': 'success',
            'redirect': url_for('index.play.medium.medium_new_game')
        }
    if mode == 'advanced':
        return {
            'response': 'success',
            'redirect': url_for('index.play.advanced.advanced_new_game')
        }
    return {'response': 'error', 'redirect': url_for('index.index')}


@mod.context_processor
def inject_session():
    return {
        'color_mode': session['color_mode'],
        'current_nickname': session['nickname'],
        'current_opponent': OPENINGS[session['current_book']].name
    }


@mod.route('/toggle_color_mode', methods=['POST'])
def toggle_color_mode():
    session[
        'color_mode'] = 'light' if session['color_mode'] == 'dark' else 'dark'
    return {'color_mode': session['color_mode']}


@mod.route('/change_nickname', methods=['POST'])
def change_nickname():
    nickname = request.form.get('nickname')
    session['nickname'] = nickname
    return {}


# Main routes


@mod.route('/')
def root():
    return render_template('index.html')


@mod.route('/choose_opening', methods=['GET'])
def choose_opening():
    return render_template('choose_opening.html', openings_list=OPENINGS)


@mod.route('/openings/<name>')
def openings(name):
    change_book(name)
    return redirect(url_for('index.new_game'))


@mod.route('/new_game', methods=['GET'])
def new_game():
    return render_template('new_game.html')
