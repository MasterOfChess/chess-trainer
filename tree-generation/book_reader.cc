/*
 * book_reader.cc
 * Reads a book (binary file). The format of the file is:
 * The sequence of 16 byte entries.
 * One entry consists of:
 * 8 byte zobrist hash of the position
 * 1 byte number of source square of the move
 * 1 byte number of destination square of the move
 * 1 byte number indicating if promotion happened
 * 1 byte number indicating the promotion piece
 * 4 byte number of apperances of the move in that position
 *
 * Arguments:
 *
 * Handles the following commands:
 * 1. fromfen bookname <fen>
 *    Responds with the number of moves from the position and the moves
 *    sorted by the number of appearances in the book.
 * 2. exit
 * 3. quit
 */
#include "./chess-library/include/chess.hpp"
#include <fstream>
#include <iomanip>
#include <map>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>
using std::cerr;
using std::cin;
using std::cout;
using std::queue;
using std::set;
using std::string;
using std::vector;
using namespace chess;

struct BookEntry {
  uint64_t hash;
  uint8_t src;
  uint8_t dst;
  uint8_t promotion;
  uint8_t promotion_piece;
  uint32_t count;
};

struct Command {
  string name;
  vector<string> args;
};

struct Edge {
  chess::Move move;
  uint32_t count;
};

// static vector<BookEntry> book;
static queue<Command> command_queue;

const long long TOTAL_BUFFER_SIZE_ALLOWED = 1 << 24;
static long long total_buffer_size = 0;
std::vector<std::vector<BookEntry>> book_buffers;
static long long time_point = 0;

struct Book {
  std::string filename;
  long long last_accessed;
  int buffer_idx;
};

std::map<std::string, Book> name_to_book;

static void ReadBook(const string &filename, vector<BookEntry> *book) {
  std::ifstream in(filename, std::ios::binary);
  if (!in) {
    cerr << "Cannot open file " << filename << std::endl;
    return;
  }
  BookEntry entry;
  while (in.read(reinterpret_cast<char *>(&entry), sizeof(entry))) {
    book->push_back(entry);
  }
}

static int ApplyLRU() {
  int min_time = time_point;
  std::string min_name;
  for (const auto &entry : name_to_book) {
    if (entry.second.last_accessed < min_time) {
      min_time = entry.second.last_accessed;
      min_name = entry.first;
    }
  }
  int buffer_idx = name_to_book[min_name].buffer_idx;
  total_buffer_size -= book_buffers[buffer_idx].size();
  book_buffers[buffer_idx].clear();
  name_to_book.erase(min_name);
  for (auto &entry : name_to_book) {
    if (entry.second.buffer_idx + 1 == (int)book_buffers.size()) {
      entry.second.buffer_idx = buffer_idx;
      std::swap(book_buffers[buffer_idx], book_buffers.back());
      book_buffers.pop_back();
      break;
    }
  }
  return buffer_idx;
}

static std::vector<BookEntry> &GetBookBuffer(const std::string &filename) {
  if (name_to_book.find(filename) == name_to_book.end()) {
    name_to_book[filename] = Book{filename, time_point, -1};
  }
  time_point++;
  name_to_book[filename].last_accessed = time_point;
  if (name_to_book[filename].buffer_idx == -1) {
    name_to_book[filename].buffer_idx = book_buffers.size();
    book_buffers.push_back({});
    ReadBook(filename, &book_buffers.back());
    total_buffer_size += book_buffers.back().size();
    if (total_buffer_size > TOTAL_BUFFER_SIZE_ALLOWED) {
      ApplyLRU();
    }
  }
  return book_buffers[name_to_book[filename].buffer_idx];
}

static void ParseCommand(const string &line) {
  Command command;
  std::istringstream iss(line);
  iss >> command.name;
  string arg;
  while (iss >> arg) {
    command.args.push_back(arg);
  }
  command_queue.push(command);
}

static vector<Edge> FindEdgesFromPosition(const std::string &bookname,
                                          uint64_t pos_hash) {
  vector<Edge> edges;
  auto &book = GetBookBuffer(bookname);
  auto it = std::lower_bound(
      book.begin(), book.end(), pos_hash,
      [](const BookEntry &entry, uint64_t hash) { return entry.hash < hash; });
  while (it != book.end() && it->hash == pos_hash) {
    chess::Move move;
    chess::Square src(it->src);
    chess::Square dst(it->dst);
    chess::PieceType promotion_piece(
        static_cast<chess::PieceType::underlying>(it->promotion_piece));
    if (it->promotion) {
      move =
          chess::Move::make<chess::Move::PROMOTION>(src, dst, promotion_piece);
    } else {
      move = chess::Move::make(src, dst);
    }
    edges.push_back({move, it->count});
    it++;
  }
  std::sort(edges.begin(), edges.end(),
            [](const Edge &a, const Edge &b) { return a.count > b.count; });
  return edges;
}

static void ExecuteQuitCommand(const Command &command) {
  if (command.name == "quit") {
    exit(0);
  }
}
static void ExecuteExitCommand(const Command &command) {
  if (command.name == "exit") {
    exit(0);
  }
}

static void ExecuteFromFenCommand(const Command &command) {
  if (command.name == "fromfen") {
    if (command.args.empty() || command.args.size() != 7) {
      cerr << "Usage: fromfen <fen>\n";
      return;
    }
    const std::string &bookname = command.args[0];
    std::string fen;
    for (int i = 1; i < 7; i++) {
      fen += command.args[i];
      if (i != 5) {
        fen += " ";
      }
    }
    Board board(fen);
    uint64_t pos_hash = board.hash();
    vector<Edge> edges = FindEdgesFromPosition(bookname, pos_hash);
    cout << "positionmoves " << edges.size() << '\n';
    for (const Edge &edge : edges) {
      cout << edge.move << " " << edge.count << '\n';
    }
    cout.flush();
  }
}

static void ExecuteCommand(const Command &command) {
  ExecuteQuitCommand(command);
  ExecuteExitCommand(command);
  ExecuteFromFenCommand(command);
}

int main() {
  std::ios_base::sync_with_stdio(false);
  std::cin.tie(nullptr);

  while (true) {
    string line;
    std::getline(cin, line);
    ParseCommand(line);
    while (!command_queue.empty()) {
      ExecuteCommand(command_queue.front());
      command_queue.pop();
    }
  }
}