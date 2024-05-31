from flask import Flask, render_template, request, session, redirect, url_for
import datetime
from book_reader_protocol import BookReader
import chess
import chess.engine
import random
import os
import dataclasses

# big_book - 1 934 385 games
# semi_slav - 141 640 games

# create web app instance
app = Flask(__name__)

app.secret_key = 'KEY_EASY_TO_HACK'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=10)
BOOK_READER_PATH = os.path.join('static', 'book_reader')
STOCKFISH_PATH = os.path.join('static', 'stockfish',
                              'stockfish-ubuntu-x86-64-avx2')
BOOKS_DIR = os.path.join('static', 'books')
BOOKS = ['tree', 'big_book', 'semi_slav']

engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
book_reader = BookReader.popen(BOOK_READER_PATH,
                               os.path.join(BOOKS_DIR, 'tree.bin'))


@dataclasses.dataclass
class Opening:
    book: str
    text: str


OPENINGS = [
    Opening('tree', 'Small Book'),
    Opening('big_book', 'Big Book'),
    Opening('semi_slav', 'Semi-Slav')
]


def change_book(new_book):
    if session['current_book'] != new_book:
        global book_reader
        book_reader.quit()
        book_reader = BookReader.popen(
            BOOK_READER_PATH, os.path.join(BOOKS_DIR, new_book + '.bin'))
        session['current_book'] = new_book


def initialize_config():
    session.permanent = True
    if 'bot_lvl' not in session:
        session['bot_lvl'] = 10
    if 'freedom_degree' not in session:
        session['freedom_degree'] = 3
    if 'color' not in session:
        session['color'] = 'white'
    if 'current_book' not in session:
        session['current_book'] = 'tree'


def init_new_game():
    session['in_book'] = True
    session['freedom_degree'] = 3
    session['bot_lvl'] = 10
    engine.configure({'Skill Level': session['bot_lvl']})


@app.route('/openings/<name>')
def openings(name):
    initialize_config()
    change_book(name)
    return redirect(url_for('new_game'))


@app.route('/choose_opening', methods=['GET'])
def choose_opening():
    initialize_config()
    return render_template('choose_opening.html', openings_list=OPENINGS)


@app.route('/set_bot_lvl', methods=['POST'])
def set_bot_lvl():
    lvl = int(request.form.get('bot_lvl'))
    session['bot_lvl'] = lvl
    print(f'Setting bot_lvl to {lvl}')
    engine.configure({'Skill Level': lvl})
    return {'bot_lvl': lvl}


@app.route('/set_freedom_degree', methods=['POST'])
def set_freedom_degree():
    deg = int(request.form.get('freedom_degree'))
    session['freedom_degree'] = deg
    print(f'Setting freedom_degree to {deg}')
    return {'freedom_degree': deg}


@app.route('/new_game', methods=['GET'])
def new_game():
    initialize_config()
    return render_template('new_game.html')


@app.route('/choose_color', methods=['POST'])
def choose_color():
    initialize_config()
    color = request.form.get('color')
    color = 'white' if color == 'white-color' else 'black'
    session['color'] = color
    return {'response': 'success'}


@app.route('/play')
def play():
    initialize_config()
    init_new_game()
    return render_template('play.html', player_color=session['color'])


# define root(index) route
@app.route('/')
def root():
    initialize_config()
    init_new_game()
    return render_template('index.html')


def choose_engine_move(board: chess.Board):
    result = engine.play(board, chess.engine.Limit(time=0.5))
    board.push(result.move)
    return board.fen()


def choose_move(board: chess.Board):
    if not session['in_book']:
        return choose_engine_move(board)
    edge_result = book_reader.from_fen(board.fen())
    if not edge_result.edges:
        return choose_engine_move(board)
    print('\n'.join(map(str, edge_result.edges)))
    available_edges = edge_result.edges[:session['freedom_degree']]
    edge = random.choice(available_edges)
    board.push(edge.move)
    return board.fen()


@app.route('/make_move', methods=['POST'])
def make_move():
    fen = request.form.get('fen')
    board = chess.Board(fen)
    if (board.is_game_over()):
        return {'fen': board.fen()}
    fen = choose_move(board)

    return {'fen': fen}


# main driver
if __name__ == '__main__':
    # start HTTP server
    app.run(debug=True, threaded=True)
