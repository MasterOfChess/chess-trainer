from ..book_reader_protocol import BookReader
from .paths import BOOK_READER_PATH

book_reader = BookReader.popen(BOOK_READER_PATH)
