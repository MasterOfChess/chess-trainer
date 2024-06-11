const whiteSquarePink = '#FFB6C1';
const blackSquarePink = '#FF69B4';
const moveDelay = 300; // allows better experience
var promotion_running = false;

$('#eval-bar-on').on('click', async function () {
  $.get('/play/eval_bar_on');
  $('#eval-bar-top').attr('display', 'block');
  $('#eval-bar-bot').attr('display', 'block');
});
$('#eval-bar-off').on('click', async function () {
  $.get('/play/eval_bar_off');
  $('#eval-bar-top').attr('display', 'none');
  $('#eval-bar-bot').attr('display', 'none');
});


/* **************************************
*  Move utilities
************************************** */

function moveToUCI(move) {
  if (move.promotion) {
    return move.from + move.to + move.promotion;
  }
  return move.from + move.to;
}

function moveFromUCI(move_uci) {
  console.log("moveFromUCI: " + move_uci);
  let from = move_uci.slice(0, 2);
  let to = move_uci.slice(2, 4);
  let promotion = move_uci.slice(4, 5);
  return { from: from, to: to, promotion: promotion };
}


/* **************************************
* Board utilities
************************************** */

function pieceColor(piece) {
  return piece.search(/^w/) !== -1 ? 'w' : 'b';
}

/* **************************************
* Promotion logic
************************************** */

function promotionOnDragStart(source, piece, position, orientation) {
  if (promotion_running) {
    $('#board .square-' + source).get(0).click();
  }
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

function promotionPrepareAnimation(game, color, target) {
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

async function promotionOnDrop(game, move, source, target, piece) {
  if (move.promotion) {
    let fen = game.fen();
    let color = pieceColor(piece);
    game.remove(source);
    let new_piece = await new Promise((resolve) => {
      promotionPrepareAnimation(game, color, target);

      $('.promotion-square').on('click', function () {
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
  }
}


/* **************************************
* Game utilities
************************************** */

function gameFromMoves(moves) {
  new_game = new Chess();
  for (let move of moves) {
    new_game.move(moveFromUCI(move));
  }
  console.log('gameFromMoves: ' + new_game.fen());
  return new_game;
}


/* **************************************
* Flask communication utilities
************************************** */

async function fetchPostForm(url, form_data) {
  const response = await fetch(url, {
    'method': 'POST',
    'body': form_data,
  });
  return response.json();
}


/* **************************************
* Eval bar utilities
************************************** */

async function updateEvalBar(score) {
  $('#eval-bar-bot').attr('height', score + '%');
  $('#eval-bar-top').attr('height', (100 - score) + '%');
}


/* **************************************
* Player cards utilities
************************************** */

function updatePlayerCardBorder(game) {
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

function drawArrow(source, target, text, color) {
  console.log("Drawing arrow from " + source + " to " + target + " with text " + text + " and color " + color);
  let center = $('#board .square-55d63').width() / 2;
  let from = document.querySelector('#board .square-' + source);
  let to = document.querySelector('#board .square-' + target);
  let line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  let marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
  marker.classList.add('board-animation');
  marker_id = 'arrow' + source + target;
  marker.setAttribute('id', marker_id);
  marker.setAttribute('markerWidth', '4');
  marker.setAttribute('markerHeight', '4');
  marker.setAttribute('viewBox', '0 -10 20 20');
  marker.setAttribute('refX', '14');
  marker.setAttribute('refY', '0');
  marker.setAttribute('orient', 'auto');
  let path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M 0,-10 L 0,10 L 20,0 Z');
  path.setAttribute('fill', color);
  marker.appendChild(path);
  $('#board-defs').append(marker);
  line.classList.add('board-animation');
  line.setAttribute('id', 'curr-line');
  line.setAttribute('x1', from.offsetLeft + center);
  line.setAttribute('y1', from.offsetTop + center);
  line.setAttribute('x2', to.offsetLeft + center);
  line.setAttribute('y2', to.offsetTop + center);
  line.setAttribute('stroke', color);
  line.setAttribute('stroke-width', '10');
  line.setAttribute('marker-end', 'url(#' + marker_id + ')');
  $('#board-svg').append(line);

  let white_text_elem = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  white_text_elem.setAttribute('x', (from.offsetLeft + to.offsetLeft) / 2 + center);
  white_text_elem.setAttribute('y', (from.offsetTop + to.offsetTop) / 2 + center);
  white_text_elem.setAttribute('fill', 'white');
  white_text_elem.setAttribute('stroke', 'white');
  white_text_elem.setAttribute('stroke-width', '5');
  white_text_elem.setAttribute('text-anchor', 'middle');
  white_text_elem.innerHTML = text;
  white_text_elem.classList.add('board-animation');
  $('#board-svg').append(white_text_elem);
  let text_elem = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text_elem.setAttribute('x', (from.offsetLeft + to.offsetLeft) / 2 + center);
  text_elem.setAttribute('y', (from.offsetTop + to.offsetTop) / 2 + center);
  text_elem.setAttribute('fill', 'black');
  text_elem.setAttribute('text-anchor', 'middle');
  text_elem.innerHTML = text;
  text_elem.classList.add('board-animation');
  $('#board-svg').append(text_elem);
}


function clearSVGBoard() {
  $('.board-animation').remove();
}

function drawMoveIcon(square, pattern) {
  console.log('drawing move icon ' + square + ' ' + pattern);
  let pos = document.querySelector('#board .square-' + square);;
  let square_size = $('#board .square-55d63').width();
  let rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  rect.setAttribute('x', pos.offsetLeft);
  rect.setAttribute('y', pos.offsetTop);
  rect.setAttribute('width', square_size);
  rect.setAttribute('height', square_size);
  rect.setAttribute('fill', 'url(#' + pattern + ')');
  rect.classList.add('board-animation');
  $('#board-svg').append(rect);
}

function drawBlunder(square) {
  drawMoveIcon(square, 'blunder-pattern');
}

function drawInaccuracy(square) {
  drawMoveIcon(square, 'inaccuracy-pattern');
}

function drawBookUnknown(square) {
  drawMoveIcon(square, 'book-unknown-pattern');
}

function drawBookSideline(square) {
  drawMoveIcon(square, 'book-sideline-pattern');
}

function drawBookMainline(square) {
  drawMoveIcon(square, 'book-mainline-pattern');
}