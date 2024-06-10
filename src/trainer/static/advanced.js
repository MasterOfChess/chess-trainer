var board = null;
var game = new Chess();
var $status = $("#status");


/* **************************************
* Bot control actions
************************************** */


var bot_lvl_form = document.getElementById("bot-lvl-form");
bot_lvl_form.oninput = function () {
  let bot_lvl = this.value;
  $('label[for="bot-lvl-form"]').text("Bot lvl: " + bot_lvl);
  $.post("set_bot_lvl", { bot_lvl: bot_lvl }, function (data) {
  });
}

var freedom_degree_form = document.getElementById("freedom-degree-form");
freedom_degree_form.oninput = function () {
  let freedom_degree = this.value;
  $('label[for="freedom-degree-form"]').text("Freedom degree: " + freedom_degree);
  $.post("set_freedom_degree", { freedom_degree: freedom_degree }, function (data) {
  });
}


/* **************************************
* Board actions
************************************** */

var config = {
  draggable: true,
  position: "start",
  onDragStart: onDragStart,
  onDrop: onDrop,
  onSnapEnd: onSnapEnd,
};

board = Chessboard("board", config);

$('#play-button').on('click', async function () {
  $(this).off('click');
  $(this).prop('disabled', true);
  await startGame();
});

// Promotion logic


function onDragStart(source, piece, position, orientation) {
  console.log("onDragStart", source, piece, position, orientation);
  promotionOnDragStart(source, piece, position, orientation);
  // do not pick up pieces if the game is over
  if (game.game_over()) return false;
  if (game.turn() !== player_on_move[0]) return false;
  // only pick up pieces for the side to move
  if (
    (game.turn() === "w" && piece.search(/^b/) !== -1) ||
    (game.turn() === "b" && piece.search(/^w/) !== -1)
  ) {
    return false;
  }
}


async function askEngineToPlayMove(move_uci) {
  console.log("Asking to play move: " + move_uci);
  await new Promise((resolve) => {
    $.post("make_move", { fen: game.fen(), move_uci: move_uci }, function (data) {
      setTimeout(() => {
        game.load(data.fen);
        board.position(game.fen());
        resolve();
      }, moveDelay);
    });
  });
}

function updateGameState(data) {
  console.log('updateGameState');
  game = gameFromMoves(data.moves);
  console.log('game.fen(): ' + game.fen());
  board.position(game.fen());
  updatePlayerCardBorder(game);
  $('#pgn').html(data.pgn);
}

async function makeMove(move_uci) {
  console.log('makeMove(' + move_uci + ')');
  console.log(JSON.stringify({ move_uci: move_uci }));
  let form_data = new FormData();
  form_data.append('move_uci', move_uci);
  form_data.append('phase', 'first');
  const data = await fetchPostForm('make_move', form_data);
  updateGameState(data);
  if (data.ask_again === true) {
    console.log('ask_again');
    let form_data = new FormData();
    form_data.append('move_uci', move_uci);
    form_data.append('phase', 'second');
    const data = await fetchPostForm('make_move', form_data);
    setTimeout(() => { updateGameState(data) }, moveDelay);
  }
}

function onDrop(source, target, piece) {
  console.log("onDrop", source, target);
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
    drawArrow(source, target);
    await makeMove(moveToUCI(move));
  }
  handleMove();
}

// update the board position after the piece snap
// for castling, en passant, pawn promotion
function onSnapEnd() {
  console.log("onSnapEnd");
  board.position(game.fen());
}

function drawArrow(source, target) {
  console.log("Drawing arrow from " + source + " to " + target);
  let center = $('#board .square-55d63').width() / 2;
  let from = document.querySelector('#board .square-' + source);
  let to = document.querySelector('#board .square-' + target);
  let line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('id', 'curr-line');
  line.setAttribute('x1', from.offsetLeft + center);
  line.setAttribute('y1', from.offsetTop + center);
  line.setAttribute('x2', to.offsetLeft + center);
  line.setAttribute('y2', to.offsetTop + center);
  line.setAttribute('stroke', 'red');
  line.setAttribute('stroke-width', '5');
  $('#board-svg').append(line);

}

async function startGame() {
  console.log('startGame');
  player_on_move = player_color;
  if (player_color === 'black') {
    $('#eval-bar-bot-rect').attr('fill', 'black');
    $('#eval-bar-top-rect').attr('fill', 'white');
  }
  else {
    $('#eval-bar-bot-rect').attr('fill', 'white');
    $('#eval-bar-top-rect').attr('fill', 'black');
  }
  if (player_color === "black") {
    board.orientation('black');
    updateStatus();
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await makeMove("None");
  }
  else {
    board.orientation('white');
  }
}

