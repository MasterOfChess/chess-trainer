var board = null;
var config = {
  draggable: true,
  position: game.fen(),
  onDragStart: onDragStart,
  onDrop: onDrop,
  onSnapEnd: onSnapEnd
};
('game.fen()' + game.fen())
board = Chessboard('board', config);

$('#prev-button').on('click', function () {
  game.undo();
  board.position(game.fen());
  $.post('prev_move', function (data) {
    updateSite(data['data']);
  })
});

$('#next-button').on('click', function () {
  $.post('next_move', function (data) {
    if (data['data'].moves) {
      game.move(moveFromUCI(data['data'].moves.at(-1)));
      board.position(game.fen());
    }
    updateSite(data['data']);
  });
});




function onDragStart(source, piece, position, orientation) {
  ('onDragStart', source, piece, position, orientation)
  promotionOnDragStart(source, piece, position, orientation)
  if (board_locked) return false
  if (game.game_over()) return false
  if ((game.turn() === 'w' && piece.search(/^b/) !== -1) ||
    (game.turn() === 'b' && piece.search(/^w/) !== -1)) {
    return false
  }
  return true;
}

async function makeMove(move_uci, phase) {
  ('makeMove', move_uci, phase)
  if (phase === 'first') {
    await $.post('make_move', { move_uci: move_uci, phase: 'first' }, function (data) {
      updateSite(data['data']);
    });
  }
  else {
    await $.post('make_move', { move_uci: move_uci, phase: 'second' }, function (data) {
      setTimeout(() => {
        if (data['data'].bot_move) {
          game.move(moveFromUCI(data['data'].bot_move));
          board.position(game.fen());
        }
        updateSite(data['data']);
      }, moveDelay);
    });
  }

}

function onDrop(source, target, piece) {
  ('onDrop', source, target, piece)
  let is_legal = (source, target) => {
    let legal_moves = game
      .moves({ square: source, verbose: true })
      .filter((x) => {
        return x.to == target;
      });
    if (legal_moves.length == 0) return null;
    return legal_moves[0];
  };
  let move = is_legal(source, target);
  if (move === null) return "snapback";
  async function handleMove() {
    await promotionOnDrop(game, move, source, target, piece);
    game.move(move);
    await makeMove(moveToUCI(move), 'first');
    if (board_locked) return;
    await makeMove(moveToUCI(move), 'second');
  }
  handleMove();
}

function onSnapEnd() {
  ("onSnapEnd");
  board.position(game.fen());
}

function updateSite(data) {
  ("updateSite");
  (data);
  if (data === null) {
    return;
  }
  game = gameFromMoves(data.moves);
  board.position(game.fen(), false);
  updatePlayerCardBorder(game);
  $('#pgn').html(data.pgn);
  updateEvalBar(data.score);
  if (data.active_bar) {
    $('#eval-bar-top').attr('display', 'block');
    $('#eval-bar-bot').attr('display', 'block');
  }
  else {
    $('#eval-bar-top').attr('display', 'none');
    $('#eval-bar-bot').attr('display', 'none');
  }
  if (data.lock_board) {
    board_locked = true;
    $('#prev-button').prop('disabled', false);
  }
  else {
    board_locked = false;
    $('#prev-button').prop('disabled', true);
  }
  clearSVGBoard();
  if (data.icon) {
    drawMoveIcon(data.square, data.icon + '-pattern');
    if (data.refutation !== '') {
      $('#refute-fen').attr('value', data.fen);
      (data.refutation);
      $('#refute-refutation').attr('value', data.refutation);
      $('#refute-container').css('display', 'block');
    }
  }
  else {
    $('#refute-container').css('display', 'none');
  }

}