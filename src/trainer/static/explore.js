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
  if (game.game_over()) return false
  if ((game.turn() === 'w' && piece.search(/^b/) !== -1) ||
    (game.turn() === 'b' && piece.search(/^w/) !== -1)) {
    return false
  }
  return true;
}

async function makeMove(move_uci) {
  ('makeMove', move_uci)
  $.post('make_move', { move_uci: move_uci }, function (data) {
    if (data['redirect']) {
      window.location.href = data['url'];
    }
    else {
      updateSite(data['data']);
    }
  });

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
    await makeMove(moveToUCI(move));
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
  clearSVGBoard();
  if (data.move_message) {
    $('#move-message').html(data.move_message);
  }
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