from flask import Flask, render_template, request, session
import datetime
from book_reader_protocol import BookReader
import chess
import chess.engine
import random

# create web app instance
app = Flask(__name__)

app.secret_key = 'KEY_EASY_TO_HACK'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=10)

engine = chess.engine.SimpleEngine.popen_uci(
    '../stockfish/stockfish-ubuntu-x86-64-avx2')
book_reader = BookReader.popen('../tree-generation/book_reader',
                               '../tree-generation/tree.bin')


def initialize_config():
    session.permanent = True
    if 'bot_lvl' not in session:
        session['bot_lvl'] = 10
    if 'branching_factor' not in session:
        session['branching_factor'] = 1


def new_game():
    session['in_book'] = True
    engine.configure({'Skill Level': session['bot_lvl']})


@app.route('/set_bot_lvl', methods=['POST'])
def set_bot_lvl():
    lvl = int(request.form.get('bot_lvl'))
    session['bot_lvl'] = lvl
    print(f'Setting bot_lvl to {lvl}')
    engine.configure({'Skill Level': lvl})
    return {'bot_lvl': lvl}


# define root(index) route
@app.route('/')
def root():
    initialize_config()
    new_game()
    return render_template('index.html')


def choose_engine_move(board: chess.Board):
    result = engine.play(board, chess.engine.Limit(time=1.0))
    board.push(result.move)
    return board.fen()


def choose_move(board: chess.Board):
    if not session['in_book']:
        return choose_engine_move(board)
    edge_result = book_reader.from_fen(board.fen())
    if not edge_result.edges:
        return choose_engine_move(board)
    print('\n'.join(map(str, edge_result.edges)))
    available_edges = edge_result.edges[:session['branching_factor']]
    edge = random.choice(available_edges)
    board.push(edge.move)
    return board.fen()


@app.route('/make_move', methods=['POST'])
def make_move():
    fen = request.form.get('fen')
    board = chess.Board(fen)
    # move = random.choice(list(board.legal_moves))
    # board.push(move)
    fen = choose_move(board)

    return {'fen': fen}


# main driver
if __name__ == '__main__':
    # start HTTP server
    app.run(debug=True, threaded=True)
