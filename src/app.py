from flask import Flask, render_template, request, session, redirect, url_for, send_file
import datetime
from book_reader_protocol import BookReader
import chess
import chess.engine
import chess.pgn
import random
import os
import dataclasses
import glob
import argparse
import io

# big_book - 1 934 385 games
# semi_slav - 141 640 games

# create web app instance
app = Flask(__name__)

app.secret_key = 'KEY_EASY_TO_HACK'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=10)
BOOK_READER_PATH = os.path.join('static', 'book_reader')
STOCKFISH_PATH = glob.glob(os.path.join('static', 'stockfish', 'stockfish*'))[0]
BOOKS_DIR = os.path.join('static', 'books')
BOOKS = ['tree', 'big_book', 'semi_slav']

ENGINE_THINKING_TIME = 0.5

engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
book_reader = BookReader.popen(BOOK_READER_PATH,
                               os.path.join(BOOKS_DIR, 'tree.bin'))
current_board = chess.Board()
current_game = chess.pgn.Game()
current_node = None


@dataclasses.dataclass
class Opening:
    book: str
    text: str


OPENINGS = [
    Opening('tree', 'Bot Small Book'),
    Opening('big_book', 'Bot Big Book'),
    Opening('semi_slav', 'Bot Semi Slav')
]

# Session fields
# bot_lvl: int [1, 20]
# freedom_degree: int [1, 6]
# color: white | black
# current_book: int
# in_book: bool
# initialized: bool
# nickname: str


def change_book(new_book):
    if OPENINGS[session['current_book']].book != new_book:
        global book_reader
        book_reader.quit()
        book_reader = BookReader.popen(
            BOOK_READER_PATH, os.path.join(BOOKS_DIR, new_book + '.bin'))
        book_idx = [o.book for o in OPENINGS].index(new_book)
        session['current_book'] = book_idx


def initialize_config():
    if 'initialized' not in session:
        session.permanent = True
        session['initialized'] = True
        session['current_book'] = 0
        session['color_mode'] = 'dark'
        session['nickname'] = 'Default Player'
        session['color'] = 'white'


def init_new_game():
    global current_board
    global current_game
    global current_node
    session['in_book'] = True
    session['freedom_degree'] = 3
    session['bot_lvl'] = 10
    current_board = chess.Board()
    current_game = chess.pgn.Game()
    current_node = None
    current_game.headers['Event'] = 'Chess Opening Trainer training'
    current_game.headers.pop('Site')
    current_game.headers.pop('Round')
    if session['color'] == 'black':
        current_game.headers['Black'] = session['nickname']
        current_game.headers['White'] = OPENINGS[session['current_book']].text
    else:
        current_game.headers['White'] = session['nickname']
        current_game.headers['Black'] = OPENINGS[session['current_book']].text
    current_game.headers['Date'] = datetime.datetime.now().strftime('%Y-%m-%d')
    engine.configure({'Skill Level': session['bot_lvl']})


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


@app.route('/choose_color', methods=['POST'])
def choose_color():
    initialize_config()
    color = request.form.get('color')
    color = 'white' if color == 'white-color' else 'black'
    session['color'] = color
    return {'response': 'success', 'redirect': url_for('play')}


def choose_engine_move(board: chess.Board):
    result = engine.play(board, chess.engine.Limit(time=ENGINE_THINKING_TIME))
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


def render_template_with_session(file: str, *args, **kwargs):
    return render_template(
        file,
        color_mode=session['color_mode'],
        current_nickname=session['nickname'],
        current_opponent=OPENINGS[session['current_book']].text,
        *args,
        **kwargs)


def update_current_node():
    global current_node
    if current_node is None:
        current_node = current_game.add_variation(current_board.peek())
    else:
        current_node = current_node.add_variation(current_board.peek())


@app.route('/make_move', methods=['POST'])
def make_move():
    fen = request.form.get('fen')
    move_san = request.form.get('move_san')
    if move_san != 'None':
        current_board.push_san(move_san)
        update_current_node()
    # board = chess.Board(fen)
    if current_board.is_game_over():
        current_game.headers['Result'] = current_board.result()
        return {'fen': current_board.fen()}
    fen = choose_move(current_board)
    update_current_node()

    return {'fen': fen}


@app.route('/toggle_color_mode', methods=['POST'])
def toggle_color_mode():
    session[
        'color_mode'] = 'light' if session['color_mode'] == 'dark' else 'dark'
    return {'color_mode': session['color_mode']}


@app.route('/change_nickname', methods=['POST'])
def change_nickname():
    nickname = request.form.get('nickname')
    session['nickname'] = nickname
    if session['color'] == 'white':
        current_game.headers['White'] = nickname
    else:
        current_game.headers['Black'] = nickname
    return {}


@app.route('/query_game_state', methods=['POST'])
def query_game_state():
    print('Current state:', str(current_game.mainline_moves()))
    return {
        'fen': current_board.fen(),
        'white': current_game.headers['White'],
        'black': current_game.headers['Black'],
        'date': current_game.headers['Date'],
        'pgn': str(current_game.mainline_moves()),
        'result': current_board.result()
    }


@app.route('/download_pgn')
def download_pgn():
    pgn = current_game.accept(chess.pgn.StringExporter())
    return send_file(io.BytesIO(pgn.encode()), download_name='game.pgn')


# Main routes


@app.route('/')
def root():
    initialize_config()
    init_new_game()
    return render_template_with_session('index.html')


@app.route('/choose_opening', methods=['GET'])
def choose_opening():
    initialize_config()
    return render_template_with_session('choose_opening.html',
                                        openings_list=OPENINGS)


@app.route('/openings/<name>')
def openings(name):
    initialize_config()
    change_book(name)
    return redirect(url_for('new_game'))


@app.route('/new_game', methods=['GET'])
def new_game():
    initialize_config()
    return render_template_with_session('new_game.html')


@app.route('/play')
def play():
    initialize_config()
    init_new_game()
    return render_template_with_session('play.html',
                                        player_color=session['color'])


parser = argparse.ArgumentParser()

# main driver
if __name__ == '__main__':
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', type=bool, default=False)
    parse_args = parser.parse_args()
    print(parse_args)
    # start HTTP server
    app.run(host=parse_args.host,
            port=parse_args.port,
            debug=parse_args.debug,
            threaded=True)
