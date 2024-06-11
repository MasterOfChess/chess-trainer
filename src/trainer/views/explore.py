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
from .play_utilities import assess_move, assess_position, get_absolute_score
from typing import Any
import dataclasses
import json

mod = Blueprint('explore', __name__)

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

    def next(self) -> bool:
        print('next')
        if self.node.next() is None:
            return False
        self.node = self.node.next()
        print(self.node.move)
        self.board.push(self.node.move)
        print(self.board)
        return True

    def prev(self) -> bool:
        print('prev')
        if self.node.parent is None:
            return False
        self.node = self.node.parent
        self.board.pop()
        print(self.board)
        return True

    def get_mainline(self) -> str:
        moves = self.node.mainline_moves()
        if self.node.next() is not None:
            self.node.remove_variation(self.node.next())
        res = str(self.game.mainline_moves())
        new_node = self.node
        for move in moves:
            new_node = new_node.add_main_variation(move)
        return res

    def restore_node(self, moves: int):
        self.node = self.game
        self.board = chess.Board()
        for _ in range(moves):
            self.node = self.node.next()
            self.board.push(self.node.move)

    def __str__(self) -> str:
        return self.game.accept(chess.pgn.StringExporter())


def get_render_data(game_state: GameState,
                    pos_info: PositionAssessment) -> dict[str, Any]:
    mainline = dataclasses.asdict(
        GameLine(pos_info.mainline[0].uci(),
                 pos_info.mainline[1])) if pos_info.mainline else None
    moves = [move.uci() for move in game_state.board.move_stack]
    sidelines = [
        dataclasses.asdict(GameLine(move.uci(), popularity))
        for move, popularity in pos_info.sidelines
    ]
    score = get_absolute_score(game_state.board, pos_info, session['color'])
    print('Rendering')
    print(session['color'])
    print(game_state.board.fen())
    print(str(game_state))
    print(game_state.get_mainline())
    return {
        'player_color': session['color'],
        'fen': game_state.board.fen(),
        'pgn': game_state.get_mainline(),
        'moves': moves,
        'mainline': mainline,
        'sidelines': sidelines,
        'score': score,
        'active_bar': session['active_bar'],
        'refutation': '',
        'move_message': '',
        'icon': None
    }


def restore_game_state():
    game_state = GameState.from_str(session['game'])
    if 'restore_node' in session:
        game_state.restore_node(session['restore_node'])
        session.pop('restore_node')
    return game_state


def save_game_state(game_state: GameState):
    session['game'] = str(game_state)
    session['restore_node'] = len(game_state.board.move_stack)


@mod.route('/make_move', methods=['POST'])
def make_move():
    move_uci = request.form.get('move_uci')
    move = chess.Move.from_uci(move_uci)
    print('/make_move', move)
    game_state = restore_game_state()
    old_pos_info = assess_position(game_state.board,
                                   session['current_book_path'])
    move_info = assess_move(game_state.board, move, old_pos_info)
    game_state.make_move(move)
    save_game_state(game_state)
    pos_info = assess_position(game_state.board, session['current_book_path'])
    data = {'data': get_render_data(game_state, pos_info)}
    if move_info.move_type == MoveType.OK:
        if move_info.line_type == LineType.MAIN:
            data['data']['move_message'] = 'It is good to follow the main line'
        elif move_info.line_type == LineType.SIDELINE:
            data['data'][
                'move_message'] = 'Sometimes it is good to explore sidelines'
        else:
            data['data']['move_message'] = 'This is not a part of the opening'
            data['data']['icon'] = 'book-unknown'
            data['data']['square'] = move.uci()[2:4]
    elif move_info.move_type == MoveType.INACCURACY:
        if move_info.line_type == LineType.MAIN:
            data['data']['move_message'] = 'It is good to follow the main line'
        elif move_info.line_type == LineType.SIDELINE:
            data['data'][
                'move_message'] = 'Some sidelines are not as good as others'
            data['data']['icon'] = 'inaccuracy'
            data['data']['square'] = move.uci()[2:4]
            data['data']['refutation'] = json.dumps(
                [m.uci() for m in move_info.pv])

        else:
            data['data']['move_message'] = 'This is not a part of the opening'
            data['data']['icon'] = 'inaccuracy'
            data['data']['square'] = move.uci()[2:4]
            data['data']['refutation'] = json.dumps(
                [m.uci() for m in move_info.pv])

    elif move_info.move_type == MoveType.BLUNDER:
        if move_info.line_type == LineType.MAIN:
            data['data']['move_message'] = 'It is good to follow the main line'
        elif move_info.line_type == LineType.SIDELINE:
            data['data']['move_message'] = 'This sideline is a blunder'
            data['data']['icon'] = 'blunder'
            data['data']['square'] = move.uci()[2:4]
            data['data']['refutation'] = json.dumps(
                [m.uci() for m in move_info.pv])

        else:
            data['data']['move_message'] = 'This is not a part of the opening'
            data['data']['icon'] = 'blunder'
            data['data']['square'] = move.uci()[2:4]
            data['data']['refutation'] = json.dumps(
                [m.uci() for m in move_info.pv])

    return data


@mod.route('/next_move', methods=['POST'])
def next_move():
    game_state = restore_game_state()
    if game_state.next():
        save_game_state(game_state)

        pos_info = assess_position(game_state.board,
                                   session['current_book_path'])
        return {'data': get_render_data(game_state, pos_info)}
    save_game_state(game_state)
    return {'data': None}


@mod.route('/prev_move', methods=['POST'])
def prev_move():
    game_state = restore_game_state()
    if game_state.prev():
        save_game_state(game_state)
        pos_info = assess_position(game_state.board,
                                   session['current_book_path'])
        return {'data': get_render_data(game_state, pos_info)}
    save_game_state(game_state)
    return {'data': None}


@mod.route('/new_game')
def explore_new_game():
    print("Endpoint explore")
    game_state = GameState.initialize(session['color'], session['nickname'],
                                      session['current_book'])
    session['active_bar'] = True
    print('Initialized')
    save_game_state(game_state)
    return redirect(url_for('index.play.explore.explore'))


@mod.route('/')
def explore():
    game_state = restore_game_state()
    pos_info = assess_position(game_state.board, session['current_book_path'])
    print('Rendering')
    print(session['color'])
    print(game_state.board.fen())
    print(pos_info.mainline)
    print(pos_info.sidelines)
    print(pos_info.score.relative.wdl().expectation())
    return render_template('explore.html',
                           **get_render_data(game_state, pos_info))
