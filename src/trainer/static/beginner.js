var board = null;
var board_locked = false;
var config = {
  draggable: true,
  position: game.fen(),
  onDragStart: onDragStart,
  onDrop: onDrop,
  onSnapEnd: onSnapEnd
};
console.log('game.fen()' + game.fen())
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
  console.log('onDragStart', source, piece, position, orientation)
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
  console.log('makeMove', move_uci, phase)
  if (phase === 'first') {
    await $.post('make_move', { move_uci: move_uci, phase: 'first' }, function (data) {
      updateSite(data['data']);
    });
  }
  else {
    await $.post('make_move', { move_uci: move_uci, phase: 'second' }, function (data) {
      if (data['data'].bot_move) {
        game.move(moveFromUCI(data['data'].bot_move));
        board.position(game.fen());
      }
      updateSite(data['data']);
    });
  }

}

function onDrop(source, target, piece) {
  console.log('onDrop', source, target, piece)
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
  console.log("onSnapEnd");
  board.position(game.fen());
}

function updateSite(data) {
  console.log("updateSite");
  console.log(data);
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
  }
  else {
    board_locked = false;
  }
  clearSVGBoard();
  if (data.move_message) {
    $('#move-message').html(data.move_message);
  }
  if (data.icon) {
    drawMoveIcon(data.square, data.icon + '-pattern');
    if (data.refutation !== '') {
      $('#refute-fen').attr('value', data.fen);
      console.log(data.refutation);
      $('#refute-refutation').attr('value', data.refutation);
      $('#refute-container').css('display', 'block');
    }
  }
  else {
    $('#refute-container').attr('display', 'none');
    if (data.mainline) {
      let move_obj = moveFromUCI(data.mainline.move);
      drawArrow(move_obj.from, move_obj.to, data.mainline.popularity + '%', 'green');
    }
    for (let line of data.sidelines) {
      let move_obj = moveFromUCI(line.move);
      drawArrow(move_obj.from, move_obj.to, line.popularity + '%', 'yellow');
    }
  }

}