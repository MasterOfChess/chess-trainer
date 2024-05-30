from flask import Flask, render_template, request
from book_reader_protocol import BookReader
# from book_reader_protocol import EchoProtocol
import chess
import random

# create web app instance
app = Flask(__name__)

book_reader = BookReader.popen('../tree-generation/book_reader',
                               '../tree-generation/tree.bin')


# define root(index) route
@app.route('/')
async def root():
    return render_template('index.html')


@app.route('/make_move', methods=['POST'])
async def make_move():
    fen = request.form.get('fen')
    board = chess.Board(fen)
    move = random.choice(list(board.legal_moves))
    board.push(move)
    # fen = board.fen()
    # print('Making move')
    # print(fen)
    # edge_result = book_reader.from_fen(fen)

    # print('\n'.join(map(str, edge_result.edges)))
    # if edge_result.edges:
    #     board.push(edge_result.edges[0].move)
    fen = board.fen()

    return {'fen': fen}


# main driver
if __name__ == '__main__':
    # start HTTP server
    app.run(debug=True, threaded=True)
