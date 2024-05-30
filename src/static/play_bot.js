// NOTE: based on example that uses the chess.js library:
// https://github.com/jhlywa/chess.js
var board = null;
var game = new Chess();
var $status = $("#status");
var $fen = $("#fen");
var $pgn = $("#pgn");
var whiteSquareGrey = '#a9a9a9';
var blackSquareGrey = '#696969';
const whiteSquarePink = '#FFB6C1';
const blackSquarePink = '#FF69B4';
let promotion_running = false;
function onDragStart(source, piece, position, orientation) {
  console.log("onDragStart", source, piece, position, orientation);
  if (promotion_running) {
    $('#myBoard .square-' + source).get(0).click();
    console.log("Clicked " + source);
  }
  // do not pick up pieces if the game is over
  if (game.game_over()) return false;

  // only pick up pieces for the side to move
  if (
    (game.turn() === "w" && piece.search(/^b/) !== -1) ||
    (game.turn() === "b" && piece.search(/^w/) !== -1)
  ) {
    return false;
  }
}

function clickSquare(square) {
  var $square = $('#myBoard .square-' + square);
  $square.on('click', function () {
    console.log('click');
  });
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

function pieceColor(piece) {
  return piece.search(/^w/) !== -1 ? 'w' : 'b';
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
  $('#myBoard .square-55d63').css('background', '')
}

async function promotionOnDrop(move, source, target, piece) {
  if (move.promotion) {
    let fen = game.fen();
    let color = pieceColor(piece);
    game.remove(source);
    let new_piece = await new Promise((resolve) => {
      console.log("Promoting");
      promotion_running = true;
      for (let square of promotionSquaresUnder(target)) {
        let $square = $('#myBoard .square-' + square.coord);
        game.put({ type: square.piece, color: color }, square.coord);
        console.log("Putting " + square.piece + " at " + square.coord);
        $square.addClass('promotion-square');
        $square.attr('data-promotion', square.piece);
      }
      promotionHighlightSquares();

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

async function onDrop(source, target, piece) {
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
  // Handle promotions
  await promotionOnDrop(move, source, target, piece);
  game.move(move);
  board.position(game.fen());

  $.post("/make_move", { fen: game.fen() }, async function (data) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    game.load(data.fen);
    board.position(game.fen());
  });

  updateStatus();
}

// update the board position after the piece snap
// for castling, en passant, pawn promotion
function onSnapEnd() {
  console.log("onSnapEnd");
  board.position(game.fen());
}

function updateStatus() {
  console.log("Updating status");
  var status = "";

  var moveColor = "White";
  if (game.turn() === "b") {
    moveColor = "Black";
  }

  // checkmate?
  if (game.in_checkmate()) {
    status = "Game over, " + moveColor + " is in checkmate.";
  }

  // draw?
  else if (game.in_draw()) {
    status = "Game over, drawn position";
  }

  // game still on
  else {
    status = moveColor + " to move";

    // check?
    if (game.in_check()) {
      status += ", " + moveColor + " is in check";
    }
  }

  $status.html(status);
  $fen.html(game.fen());
  $pgn.html(game.pgn());
}

var config = {
  draggable: true,
  position: "start",
  onDragStart: onDragStart,
  onDrop: onDrop,
  onSnapEnd: onSnapEnd,
};
board = Chessboard("myBoard", config);

updateStatus();