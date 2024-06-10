var board = null;
var game = new Chess();
var $status = $("#status");
const whiteSquarePink = '#FFB6C1';
const blackSquarePink = '#FF69B4';
const moveDelay = 300; // allows better experience
var promotion_running = false;

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

// Promotion logic

function promotionOnDragStart(source, piece, position, orientation) {
  $('#board .square-' + source).get(0).click();
  console.log("Clicked " + source);
}

function promotionSquaresUnder(square) {
  let file = square[0];
  let rank = parseInt(square[1]);
  let squares = [];
  let pieces = ['q', 'r', 'b', 'n'];
  if (rank == 8) {
    for (let i = 8; i >= 5; i--) {
      squares.push({ coord: file + i, piece: pieces[8 - i] });
    }
  }
  else {
    for (let i = 1; i <= 4; i++) {
      squares.push({ coord: file + i, piece: pieces[i - 1] });
    }
  }
  return squares;
}

async function promotionHighlightSquares() {
  $('.promotion-square').each(function (index) {
    if ($(this).hasClass('black-3c85d')) {
      $(this).css('background', blackSquarePink);
    }
    else {
      $(this).css('background', whiteSquarePink);
    }
  });
}

function promotionRemoveHighlight() {
  $('#board .square-55d63').css('background', '')
}

function promotionPrepareAnimation(color, target) {
  promotion_running = true;
  for (let square of promotionSquaresUnder(target)) {
    let $square = $('#board .square-' + square.coord);
    game.put({ type: square.piece, color: color }, square.coord);
    console.log("Putting " + square.piece + " at " + square.coord);
    $square.addClass('promotion-square');
    $square.attr('data-promotion', square.piece);
  }
  promotionHighlightSquares();
}

async function promotionOnDrop(move, source, target, piece) {
  if (move.promotion) {
    let fen = game.fen();
    let color = pieceColor(piece);
    game.remove(source);
    let new_piece = await new Promise((resolve) => {
      console.log("Promoting");
      promotionPrepareAnimation(color, target);

      $('.promotion-square').on('click', function () {
        console.log('click', $(this).attr('data-square'));
        promotion_running = false;
        let piece = $(this).attr('data-promotion');
        game.load(fen);
        // Clean up
        promotionRemoveHighlight();
        $('.promotion-square').off('click');
        $('.promotion-square').removeAttr('data-promotion');
        $('.promotion-square').removeClass('promotion-square');
        resolve(piece);
      });

    });
    move.promotion = new_piece;
    console.log("Promotion done");
  }
}

function onDragStart(source, piece, position, orientation) {
  console.log("onDragStart", source, piece, position, orientation);
  if (promotion_running) {
    promotionOnDragStart(source, piece, position, orientation);
  }
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


function pieceColor(piece) {
  return piece.search(/^w/) !== -1 ? 'w' : 'b';
}

function moveToUCI(move) {
  if (move.promotion) {
    return move.from + move.to + move.promotion;
  }
  return move.from + move.to;
}

function moveFromUCI(move_uci) {
  let from = move_uci.slice(0, 2);
  let to = move_uci.slice(2, 4);
  let promotion = move_uci.slice(4, 5);
  return { from: from, to: to, promotion: promotion };
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

function gameFromMoves(moves) {
  console.log('gameFromMoves', moves);
  new_game = new Chess();
  for (let move of moves) {
    new_game.move(moveFromUCI(move));
  }
  console.log('new_game.fen(): ' + new_game.fen());
  return new_game;
}

function updateGameState(data) {
  console.log('updateGameState');
  game = gameFromMoves(data.moves);
  console.log('game.fen(): ' + game.fen());
  board.position(game.fen());
  updatePlayerCardBorder();
  $('#pgn').html(data.pgn);
}

async function fetchPostForm(url, form_data) {
  const response = await fetch(url, {
    'method': 'POST',
    'body': form_data,
  });
  return response.json();
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
    await promotionOnDrop(move, source, target, piece);
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

function updatePlayerCardBorder() {
  console.log('updatePlayerCardBorder');
  if (player_on_move === 'noone') {
    $('#border-bot').removeClass('border-warning');
    $('#border-top').removeClass('border-warning');
    $('#border-bot').addClass('border-secondary');
    $('#border-top').addClass('border-secondary');
    return;
  }
  if (game.turn() === player_on_move[0]) {
    $('#border-bot').addClass('border-warning');
    $('#border-bot').removeClass('border-secondary');
    $('#border-top').addClass('border-secondary');
    $('#border-top').removeClass('border-warning');
  }
  else {
    $('#border-top').addClass('border-warning');
    $('#border-top').removeClass('border-secondary');
    $('#border-bot').addClass('border-secondary');
    $('#border-bot').removeClass('border-warning');
  }
}

async function updatePGNCard() {
  await new Promise((resolve) => {
    $.post('query_game_state', {}, function (data) {
      console.log(data.pgn);
      $('#pgn').html(data.pgn);
      $('#eval-bar-bot').attr('height', data.score + '%');
      $('#eval-bar-top').attr('height', (100 - data.score) + '%');
      resolve();
    });
  });
}

function updateStatus() {
  console.log("Updating status");
  updatePGNCard();
  updatePlayerCardBorder();
  return true;
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
  // updateStatus();
}

$('#play-button').on('click', async function () {
  $(this).off('click');
  $(this).prop('disabled', true);
  await startGame();
});

$('#eval-bar-on').on('click', async function () {
  $('#eval-bar-top').attr('display', 'block');
  $('#eval-bar-bot').attr('display', 'block');
});
$('#eval-bar-off').on('click', async function () {
  $('#eval-bar-top').attr('display', 'none');
  $('#eval-bar-bot').attr('display', 'none');
});