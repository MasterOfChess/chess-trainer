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
import logging
import math
import json

logging.basicConfig(
    format='%(asctime)s:%(threadName)s: %(filename)s:%(lineno)d %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# create web app instance
app = Flask(__name__)

app.secret_key = 'KEY_EASY_TO_HACK'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=10)

# Paths
BOOK_READER_PATH = os.path.join('static', 'book_reader')
STOCKFISH_PATH = glob.glob(os.path.join('static', 'stockfish', 'stockfish*'))[0]
BOOKS_DIR = os.path.join('static', 'books')

# Engine settings
ENGINE_THINKING_TIME = 0.5

# Background jobs
book_reader = BookReader.popen(BOOK_READER_PATH)


# Openings config
@dataclasses.dataclass
class Opening:
    book: str
    name: str
    games: int = 0
    moves: int = 0
    img: str | None = None
    description: str = ''


def initialize_openings() -> list[Opening]:
    with open('static/books/config.json', encoding='utf-8') as f:
        config = json.load(f)
        return list(map(lambda opening: Opening(**opening), config))


OPENINGS = initialize_openings()

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


def get_current_game_state(
) -> tuple[chess.Board, chess.pgn.Game, chess.pgn.ChildNode]:
    board = chess.Board()
    game = chess.pgn.Game()
    if 'game' in session:
        game = chess.pgn.read_game(io.StringIO(session['game']))
        node = game
        for move in game.mainline_moves():
            board.push(move)
            node = node.next()
    return board, game, node


def update_game_state(board: chess.Board, game: chess.pgn.Game):
    session['game'] = game.accept(chess.pgn.StringExporter())
    session['fen'] = board.fen()


def change_book(new_book):
    logger.debug('Opening book: %s.bin', new_book)
    book_idx = [o.book for o in OPENINGS].index(new_book)
    session['current_book'] = book_idx
    session['current_book_path'] = os.path.join(BOOKS_DIR, new_book + '.bin')


def initialize_config():
    if 'initialized' not in session:
        session.permanent = True
        session['initialized'] = True
        session['current_book'] = 0
        session['current_book_path'] = os.path.join(BOOKS_DIR,
                                                    OPENINGS[0].book + '.bin')
        session['color_mode'] = 'dark'
        session['nickname'] = 'Default Player'
        session['color'] = 'white'


def init_new_game():
    session['in_book'] = True
    session['freedom_degree'] = 3
    session['bot_lvl'] = 10
    current_board = chess.Board()
    current_game = chess.pgn.Game()
    current_game.headers['Event'] = 'Chess Opening Trainer training'
    current_game.headers.pop('Site')
    current_game.headers.pop('Round')
    if session['color'] == 'black':
        current_game.headers['Black'] = session['nickname']
        current_game.headers['White'] = OPENINGS[session['current_book']].name
    else:
        current_game.headers['White'] = session['nickname']
        current_game.headers['Black'] = OPENINGS[session['current_book']].name
    current_game.headers['Date'] = datetime.datetime.now().strftime('%Y-%m-%d')
    update_game_state(current_board, current_game)


@app.route('/set_bot_lvl', methods=['POST'])
def set_bot_lvl():
    lvl = int(request.form.get('bot_lvl'))
    session['bot_lvl'] = lvl
    logger.debug('Setting bot_lvl to %s', lvl)
    return {'bot_lvl': lvl}


@app.route('/set_freedom_degree', methods=['POST'])
def set_freedom_degree():
    deg = int(request.form.get('freedom_degree'))
    session['freedom_degree'] = deg
    logger.debug('Setting freedom_degree to %d', deg)
    return {'freedom_degree': deg}


@app.route('/choose_color', methods=['POST'])
def choose_color():
    initialize_config()
    color = request.form.get('color')
    color = 'white' if color == 'white-color' else 'black'
    session['color'] = color
    return {'response': 'success', 'redirect': url_for('play')}


def choose_engine_move(board: chess.Board):
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({'Skill Level': session['bot_lvl']})
    result = engine.play(board, chess.engine.Limit(time=ENGINE_THINKING_TIME))
    engine.quit()
    board.push(result.move)
    return board.fen()


def choose_move(board: chess.Board):
    if not session['in_book']:
        return choose_engine_move(board)
    edge_result = book_reader.from_fen(session['current_book_path'],
                                       board.fen())
    if not edge_result.edges:
        return choose_engine_move(board)
    logger.info('\n'.join(map(str, edge_result.edges)))
    available_edges = edge_result.edges[:session['freedom_degree']]
    edge = random.choice(available_edges)
    board.push(edge.move)
    return board.fen()


def render_template_with_session(file: str, *args, **kwargs):
    return render_template(
        file,
        color_mode=session['color_mode'],
        current_nickname=session['nickname'],
        current_opponent=OPENINGS[session['current_book']].name,
        *args,
        **kwargs)


@app.route('/make_move', methods=['POST'])
def make_move():
    fen = request.form.get('fen')
    move_uci = request.form.get('move_uci')
    current_board, current_game, current_node = get_current_game_state()
    if move_uci != 'None':
        current_board.push(chess.Move.from_uci(move_uci))
        current_node = current_node.add_variation(current_board.peek())
    # board = chess.Board(fen)
    if current_board.is_game_over():
        current_game.headers['Result'] = current_board.result()
        update_game_state(current_board, current_game)
        return {'fen': current_board.fen()}
    fen = choose_move(current_board)
    current_node = current_node.add_variation(current_board.peek())
    update_game_state(current_board, current_game)
    return {'fen': fen}


@app.route('/toggle_color_mode', methods=['POST'])
def toggle_color_mode():
    session[
        'color_mode'] = 'light' if session['color_mode'] == 'dark' else 'dark'
    return {'color_mode': session['color_mode']}


@app.route('/change_nickname', methods=['POST'])
def change_nickname():
    current_board, current_game, _ = get_current_game_state()
    nickname = request.form.get('nickname')
    session['nickname'] = nickname
    if session['color'] == 'white':
        current_game.headers['White'] = nickname
    else:
        current_game.headers['Black'] = nickname
    update_game_state(current_board, current_game)
    return {}


@app.route('/query_game_state', methods=['POST'])
def query_game_state():
    current_board, current_game, _ = get_current_game_state()
    logger.debug('Current state: %s', str(current_game.mainline_moves()))
    if not current_board.is_game_over():
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        engine.configure({'Skill Level': 20})
        info = engine.analyse(current_board, chess.engine.Limit(time=0.4))
        engine.quit()
        wins = info['score'].relative.wdl(ply=info['depth']).wins
        draws = info['score'].relative.wdl(ply=info['depth']).draws
        losses = info['score'].relative.wdl(ply=info['depth']).losses
        logger.debug('depth: %d, score: %s, wins: %d, draws %d, losses: %d',
                     info['depth'], info['score'], wins, draws, losses)
        if (session['color'] == 'white' and
                not info['score'].turn) or (session['color'] == 'black' and
                                            info['score'].turn):
            wins, losses = losses, wins
        score = (wins + 0.5 * draws) / (wins + losses + draws)

        def sigmoid(x):
            return 1 / (1 + math.exp(-8 * (x - 0.5)))

        score = sigmoid(score)
    else:
        if current_board.result() == '1-0' and session['color'] == 'white':
            score = 1
        elif current_board.result() == '0-1' and session['color'] == 'black':
            score = 1
        elif current_board.result() == '1/2-1/2':
            score = 0.5
        else:
            score = 0
    return {
        'fen': current_board.fen(),
        'white': current_game.headers['White'],
        'black': current_game.headers['Black'],
        'date': current_game.headers['Date'],
        'pgn': str(current_game.mainline_moves()),
        'result': current_board.result(),
        'score': str(int(100 * score))
    }


@app.route('/download_pgn')
def download_pgn():
    pgn = session['game']
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
    logger.debug(parse_args)
    # start HTTP server
    app.run(host=parse_args.host,
            port=parse_args.port,
            debug=parse_args.debug,
            threaded=True)
