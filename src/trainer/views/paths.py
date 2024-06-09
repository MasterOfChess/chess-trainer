import os
import glob

PROJECT_DIR = os.path.join('trainer')
BOOK_READER_PATH = os.path.join(PROJECT_DIR, 'static', 'book_reader')
STOCKFISH_PATH = glob.glob(
    os.path.join(PROJECT_DIR, 'static', 'stockfish', 'stockfish*'))[0]
BOOKS_DIR = os.path.join(PROJECT_DIR, 'static', 'books')
