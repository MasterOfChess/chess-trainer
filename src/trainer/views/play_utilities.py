import chess
import chess.pgn
import chess.engine
from .paths import STOCKFISH_PATH
from .shared_jobs import book_reader
import enum
import dataclasses
from ..book_reader_protocol import EdgeResult

# Might be a good idea to make it opening dependent
START_HALFMOVES_LENGTH = 0
SIDELINE_ACCEPT_THRESHOLD = 10
ENGINE_DEPTH = 15

MoveType = enum.Enum('MoveScore', ['OK', 'INACCURACY', 'BLUNDER'])
LineType = enum.Enum('LineType', ['MAIN', 'SIDELINE', 'UNKNOWN'])


@dataclasses.dataclass
class PositionAssessment:
    score: chess.engine.PovScore
    mainline: tuple[chess.Move, int] | None = None
    sidelines: list[tuple[chess.Move,
                          int]] = dataclasses.field(default_factory=list)
    pv: list[chess.Move] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class MoveAssessment:
    move_type: MoveType
    line_type: LineType
    score: chess.engine.PovScore
    pv: list[chess.Move]


def get_sidelines(result: EdgeResult) -> list[tuple[chess.Move, int]]:
    sidelines = []
    total_count = sum(edge.count for edge in result.edges)

    for edge in result.edges[1:]:
        if edge.count * SIDELINE_ACCEPT_THRESHOLD < total_count:
            continue
        sidelines.append((edge.move, int(100 * edge.count / total_count)))
    return sidelines


def assess_position(board: chess.Board, opening: str) -> PositionAssessment:
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    info = engine.analyse(board, chess.engine.Limit(depth=ENGINE_DEPTH))
    engine.quit()
    print('Engine')
    print(opening, board.fen())
    result = book_reader.from_fen(opening, board.fen())
    print('Result')
    print('\n'.join(map(str, result.edges)))
    if not result.edges:
        return PositionAssessment(pv=info['pv'], score=info['score'])
    sidelines = get_sidelines(result)
    if len(board.move_stack) < START_HALFMOVES_LENGTH:
        sidelines = []
    assert result.edges[0].count != 0
    mainline = (result.edges[0].move,
                int(100 * result.edges[0].count /
                    sum(edge.count for edge in result.edges)))
    return PositionAssessment(score=info['score'],
                              mainline=mainline,
                              sidelines=sidelines,
                              pv=info['pv'])


def get_move_type(expectation: float, new_expectation: float) -> MoveType:
    print('Expectation', expectation, new_expectation)
    if new_expectation + 0.2 < expectation:
        return MoveType.BLUNDER
    if new_expectation < expectation - 0.05:
        return MoveType.INACCURACY
    return MoveType.OK


def assess_move(board: chess.Board, move: chess.Move,
                position_assessment: PositionAssessment) -> MoveAssessment:
    board.push(move)
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    info = engine.analyse(board, chess.engine.Limit(depth=ENGINE_DEPTH))
    engine.quit()
    board.pop()
    old_expectation = position_assessment.score.relative.wdl().expectation()
    new_expectation = (-info['score'].relative).wdl(
        ply=ENGINE_DEPTH).expectation()
    move_type = get_move_type(old_expectation, new_expectation)
    line_type = LineType.UNKNOWN
    if move in list(map(lambda x: x[0], position_assessment.sidelines)):
        line_type = LineType.SIDELINE
    if position_assessment.mainline and move == position_assessment.mainline[0]:
        line_type = LineType.MAIN
    return MoveAssessment(move_type, line_type, info['score'], info['pv'])


def find_best_move(board: chess.Board, lvl: int, opening: str) -> chess.Move:
    result = book_reader.from_fen(opening, board.fen())
    if result.edges:
        return result.edges[0].move
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({'Skill level': lvl})
    result = engine.play(board, chess.engine.Limit(time=0.2))
    return result.move

def get_absolute_score(board: chess.Board, pos_info: PositionAssessment, player_color: str) -> int:
    if (board.turn == chess.WHITE 
        and player_color== 'white') or (board.turn == chess.BLACK
                                             and player_color == 'black'):
        return int(pos_info.score.relative.wdl().expectation() * 100)
    return 100 - int(pos_info.score.relative.wdl().expectation() * 100)