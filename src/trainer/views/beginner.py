from flask import render_template, redirect, url_for
from flask import request, session, Blueprint
import chess
import chess.engine
import chess.pgn
import io
import logging
import datetime
from .index import OPENINGS
from .play_utilities import PositionAssessment, MoveAssessment, LineType, MoveType
from .play_utilities import assess_move, assess_position, find_best_move, get_absolute_score
from typing import Any
import dataclasses
import json

mod = Blueprint('beginner', __name__)

logging.basicConfig(
    format='%(asctime)s:%(threadName)s: %(filename)s:%(lineno)d %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# What do I store in session?
# game : str

# What variables do I need to pass to template?
# fen : str
# pgn : str
# player_color : str
# mainline : GameLine | None
# sidelines : list[GameLine]
# score : int
# active_bar : on | off
# refutation : str


@dataclasses.dataclass
class GameLine:
    move: str
    popularity: int


class GameState:

    def __init__(self, game: chess.pgn.Game):
        self.game = game
        self.board = chess.Board()
        self.node = self.game
        for move in self.game.mainline_moves():
            self.board.push(move)
            self.node = self.node.next()

    @classmethod
    def initialize(cls, color: str, nickname: str,
                   opening_id: int) -> 'GameState':
        game = chess.pgn.Game()
        game.headers['Event'] = 'Chess Opening Trainer training'
        game.headers.pop('Site')
        game.headers.pop('Round')
        if color == 'black':
            game.headers['Black'] = nickname
            game.headers['White'] = OPENINGS[opening_id].name
        else:
            game.headers['White'] = nickname
            game.headers['Black'] = OPENINGS[opening_id].name
        game.headers['Date'] = datetime.datetime.now().strftime('%Y-%m-%d')
        return cls(game)

    @classmethod
    def from_str(cls, data) -> 'GameState':
        game = chess.pgn.read_game(io.StringIO(data))
        return cls(game)

    def make_move(self, move: chess.Move):
        self.board.push(move)
        if self.node.next() is not None:
            self.node.remove_variation(self.node.next())
        self.node = self.node.add_main_variation(move)

    def prev(self) -> bool:
        print('prev')
        if self.node.parent is None:
            return False
        self.node = self.node.parent
        self.board.pop()
        self.node.remove_variation(self.node.next())
        return True

    def __str__(self) -> str:
        return self.game.accept(chess.pgn.StringExporter())
    
def get_render_data_second_phase(
        game_state: GameState, pos_info: PositionAssessment) -> dict[str, Any]:
    mainline = dataclasses.asdict(
        GameLine(pos_info.mainline[0].uci(),
                 pos_info.mainline[1])) if pos_info.mainline else None
    moves = [move.uci() for move in game_state.board.move_stack]
    sidelines = [
        dataclasses.asdict(GameLine(move.uci(), popularity))
        for move, popularity in pos_info.sidelines
    ]
    score = get_absolute_score(game_state.board, pos_info, session['color'])
    move = None
    if game_state.board.is_game_over():
        game_state.game.headers['Result'] = game_state.board.result()
    else:
        move = find_best_move(game_state.board, 1, session['current_book_path'])
    print('Rendering')
    print(session['color'])
    print(game_state.board.fen())
    print(str(game_state))
    print(str(game_state.game.mainline_moves()))
    return {
        'player_color': session['color'],
        'fen': game_state.board.fen(),
        'pgn': str(game_state.game.mainline_moves()),
        'moves': moves,
        'mainline': mainline,
        'sidelines': sidelines,
        'score': score,
        'active_bar': session['active_bar'],
        'refutation': '',
        'move_message': '',
        'lock_board': session.get('lock_board', False),
        'icon': None,
        'result': game_state.game.headers['Result'],
    }


def get_render_data_first_phase(game_state: GameState,
                                pos_info: PositionAssessment) -> dict[str, Any]:
    moves = [move.uci() for move in game_state.board.move_stack]
    score = get_absolute_score(game_state.board, pos_info, session['color'])
    return {
        'player_color': session['color'],
        'fen': game_state.board.fen(),
        'pgn': str(game_state.game.mainline_moves()),
        'moves': moves,
        'mainline': None,
        'sidelines': [],
        'score': score,
        'active_bar': session['active_bar'],
        'refutation': '',
        'move_message': '',
        'lock_board': False,
        'icon': None,
        'result': game_state.game.headers['Result'],
    }


def restore_game_state():
    game_state = GameState.from_str(session['game'])
    return game_state


def save_game_state(game_state: GameState):
    session['game'] = str(game_state)


def get_render_data_blunder(game_state: GameState, pos_info: PositionAssessment,
                            move_info: MoveAssessment) -> dict[str, Any]:
    return {
        'player_color': session['color'],
        'fen': game_state.board.fen(),
        'pgn': str(game_state.game.mainline_moves()),
        'moves': [move.uci() for move in game_state.board.move_stack],
        'mainline': None,
        'sidelines': [],
        'score': get_absolute_score(game_state.board, pos_info, session['color']),
        'active_bar': session['active_bar'],
        'refutation': json.dumps([m.uci() for m in move_info.pv]),
        'move_message': 'This is a blunder',
        'icon': 'blunder',
        'square': game_state.board.peek().uci()[2:4],
        'lock_board': True,
        'result': game_state.game.headers['Result'],
    }


def get_render_data_inaccuracy(game_state: GameState,
                               pos_info: PositionAssessment,
                               move_info: MoveAssessment) -> dict[str, Any]:
    return {
        'player_color': session['color'],
        'fen': game_state.board.fen(),
        'pgn': str(game_state.game.mainline_moves()),
        'moves': [move.uci() for move in game_state.board.move_stack],
        'mainline': None,
        'sidelines': [],
        'score': get_absolute_score(game_state.board, pos_info, session['color']),
        'active_bar': session['active_bar'],
        'refutation': json.dumps([m.uci() for m in move_info.pv]),
        'move_message': 'This is an inaccuracy',
        'icon': 'inaccuracy',
        'square': game_state.board.peek().uci()[2:4],
        'lock_board': True,
        'result': game_state.game.headers['Result'],
    }


def get_render_data_unknown(game_state: GameState, pos_info: PositionAssessment,
                            move_info: MoveAssessment) -> dict[str, Any]:
    return {
        'player_color': session['color'],
        'fen': game_state.board.fen(),
        'pgn': str(game_state.game.mainline_moves()),
        'moves': [move.uci() for move in game_state.board.move_stack],
        'mainline': None,
        'sidelines': [],
        'score': get_absolute_score(game_state.board, pos_info, session['color']),
        'active_bar': session['active_bar'],
        'refutation': '',
        'move_message': 'This is not a part of this opening',
        'icon': 'book-unknown',
        'square': game_state.board.peek().uci()[2:4],
        'lock_board': True,
        'result': game_state.game.headers['Result'],
    }


def first_phase(move_uci: str):
    move = chess.Move.from_uci(move_uci)
    game_state = restore_game_state()
    old_pos_info = assess_position(game_state.board,
                                   session['current_book_path'])
    move_info = assess_move(game_state.board, move, old_pos_info)
    game_state.make_move(move)
    save_game_state(game_state)
    if game_state.board.is_game_over():
        game_state.game.headers['Result'] = game_state.board.result()
    pos_info = assess_position(game_state.board, session['current_book_path'])

    if move_info.line_type != LineType.MAIN and move_info.move_type == MoveType.BLUNDER:
        return get_render_data_blunder(game_state, pos_info, move_info)

    # Player made a move that is not in the opening book
    if old_pos_info.mainline and move_info.line_type == LineType.UNKNOWN:
        return get_render_data_unknown(game_state, pos_info, move_info)

    # Player made an inaccuracy out of the opening
    if move_info.line_type == LineType.UNKNOWN and move_info.move_type == MoveType.INACCURACY:
        return get_render_data_inaccuracy(game_state, pos_info, move_info)
    return get_render_data_first_phase(game_state, pos_info)


def second_phase():
    game_state = restore_game_state()
    move = None
    if game_state.board.is_game_over():
        game_state.game.headers['Result'] = game_state.board.result()
    elif not session.get('lock_board', False):
        move = find_best_move(game_state.board, 1, session['current_book_path'])
    if move:
        game_state.make_move(move)
    print('Move: ', move)
    save_game_state(game_state)
    pos_info = assess_position(game_state.board, session['current_book_path'])
    data = get_render_data_second_phase(game_state, pos_info)
    data['bot_move'] = move.uci() if move else None
    return data


@mod.route('/make_move', methods=['POST'])
def make_move():
    move_uci = request.form.get('move_uci')
    phase = request.form.get('phase')
    move = chess.Move.from_uci(move_uci)
    print('/make_move', phase, move)
    if phase == 'first':
        data = first_phase(move_uci)
    else:
        data = second_phase()
    session['lock_board'] = data.get('lock_board', False)
    return {'data': data}


def get_render_data(game_state: GameState,
                    pos_info: PositionAssessment) -> dict[str, Any]:
    if (game_state.board.turn == chess.WHITE and session['color']
            == 'white') or (game_state.board.turn == chess.BLACK and
                            session['color'] == 'black'):
        return get_render_data_second_phase(game_state, pos_info)
    return second_phase()


@mod.route('/prev_move', methods=['POST'])
def prev_move():
    game_state = restore_game_state()
    session['lock_board'] = False
    if game_state.prev():
        save_game_state(game_state)
        pos_info = assess_position(game_state.board,
                                   session['current_book_path'])
        return {'data': get_render_data(game_state, pos_info)}
    save_game_state(game_state)
    return {'data': None}


@mod.route('/new_game')
def beginner_new_game():
    print('Endpoint explore')
    game_state = GameState.initialize(session['color'], session['nickname'],
                                      session['current_book'])
    session['active_bar'] = True
    session['lock_board'] = False
    print('Initialized')
    save_game_state(game_state)
    return redirect(url_for('index.play.beginner.beginner'))


@mod.route('/')
def beginner():
    game_state = restore_game_state()
    pos_info = assess_position(game_state.board, session['current_book_path'])
    print('Rendering')
    print(session['color'])
    print(game_state.board.fen())
    print(pos_info.mainline)
    print(pos_info.sidelines)
    print(pos_info.score.relative.wdl().expectation())
    return render_template('beginner.html',
                           **get_render_data(game_state, pos_info))
