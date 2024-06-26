from flask import render_template, send_file
from flask import request, session, Blueprint
import datetime
import chess
import chess.engine
import chess.pgn
import io
import logging
from .paths import STOCKFISH_PATH
from .shared_jobs import book_reader
from .index import OPENINGS

mod = Blueprint('play', __name__)

logging.basicConfig(
    format='%(asctime)s:%(threadName)s: %(filename)s:%(lineno)d %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# Engine settings
ENGINE_THINKING_TIME = 0.5

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
    if session['color'] == 'white':
        game.headers['White'] = session['nickname']
    else:
        game.headers['Black'] = session['nickname']
    logger.debug('Current game state:')
    print(session['game'])
    print(board)
    return board, game, node


def update_game_state(board: chess.Board, game: chess.pgn.Game):
    session['game'] = game.accept(chess.pgn.StringExporter())
    session['fen'] = board.fen()
    logger.debug('Updated game state:')
    print(session['game'])


# @mod.route('/set_bot_lvl', methods=['POST'])
# def set_bot_lvl():
#     lvl = int(request.form.get('bot_lvl'))
#     session['bot_lvl'] = lvl
#     logger.debug('Setting bot_lvl to %s', lvl)
#     return {'bot_lvl': lvl}


@mod.route('/set_freedom_degree', methods=['POST'])
def set_freedom_degree():
    deg = int(request.form.get('freedom_degree'))
    session['freedom_degree'] = deg
    logger.debug('Setting freedom_degree to %d', deg)
    return {'freedom_degree': deg}


def choose_engine_move(board: chess.Board):
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({'Skill Level': session['bot_lvl']})
    result = engine.play(board, chess.engine.Limit(time=ENGINE_THINKING_TIME))
    engine.quit()
    board.push(result.move)
    return board.fen()


def choose_move(board: chess.Board) -> chess.Move:
    edge_result = book_reader.from_fen(session['current_book_path'],
                                       board.fen())
    if not edge_result.edges:
        logger.info('No edges found')
        return None
    logger.info('\n'.join(map(str, edge_result.edges)))
    return edge_result.edges[0].move


def game_state_info(board: chess.Board, game: chess.pgn.Game):
    return {
        'white': game.headers['White'],
        'black': game.headers['Black'],
        'date': game.headers['Date'],
        'result': board.result(),
        'on_move': 'white' if board.turn == chess.WHITE else 'black',
        'fen': board.fen(),
        'pgn': str(game.mainline_moves()),
        'moves': list(map(str, board.move_stack))
    }


# use streams
@mod.route('/make_move', methods=['POST'])
def make_move():
    """
    Makes a move a and returns current game state.
    The only route that can modify the game state.

    Returns JSON response containing:
    - white: str
    - black: str
    - date: str
    - result: str
    - fen: str
    - pgn: str
    """
    move_uci = request.form.get('move_uci')
    phase = request.form.get('phase')
    logger.info('Make move %s', move_uci)

    current_board, current_game, current_node = get_current_game_state()
    if phase == 'first':
        if move_uci != 'None':
            current_board.push(chess.Move.from_uci(move_uci))
            current_node = current_node.add_variation(current_board.peek())
        if current_board.is_game_over():
            current_game.headers['Result'] = current_board.result()
        update_game_state(current_board, current_game)
        resp = game_state_info(current_board, current_game)
        resp['ask_again'] = not current_board.is_game_over()
        return resp
    move = choose_move(current_board)
    if move is not None:
        current_board.push(move)
        current_node = current_node.add_variation(current_board.peek())
        update_game_state(current_board, current_game)
    resp = game_state_info(current_board, current_game)
    resp['ask_again'] = False

    return resp


@mod.route('/eval_bar_on', methods=['GET'])
def eval_bar_on():
    logger.info('Eval bar on')
    session['active_bar'] = True
    return {}


@mod.route('/eval_bar_off', methods=['GET'])
def eval_bar_off():
    logger.info('Eval bar off')
    session['active_bar'] = False
    return {}


@mod.route('/download_pgn')
def download_pgn():
    pgn = session['game']
    return send_file(io.BytesIO(pgn.encode()), download_name='game.pgn')


# Main routes

# @mod.route('/beginner')
# def beginner():
#     init_new_game()
#     return render_template('beginner.html', player_color=session['color'])

# @mod.route('/beginner')
# def play_base():
#     init_new_game()
#     return render_template('play.html', player_color=session['color'])


@mod.route('/refute', methods=['POST'])
def refute():
    fen = request.form.get('fen')
    refutation = request.form.get('refutation')
    return_url = request.form.get('return_url')
    return render_template('refutation.html',
                           fen=fen,
                           refutation=refutation,
                           player_color=session['color'],
                           return_url=return_url)
