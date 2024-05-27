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
 * book filename
 *
 * Handles the following commands:
 * 1. positionfromseq <number of halfmoves> <sequence of moves>
 *    Responds with the number of moves from the position and the moves
 *    sorted by the number of appearances in the book.
 * 2. exit
 */
#include "./chess-library/include/chess.hpp"
#include <fstream>
#include <iomanip>
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

static vector<BookEntry> book;
static queue<Command> command_queue;

static void ReadBook(const string &filename) {
  std::ifstream in(filename, std::ios::binary);
  if (!in) {
    cerr << "Cannot open file " << filename << std::endl;
    exit(1);
  }
  BookEntry entry;
  while (in.read(reinterpret_cast<char *>(&entry), sizeof(entry))) {
    book.push_back(entry);
  }
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

static vector<Edge> FindEdgesFromPosition(const Board &board,
                                          uint64_t pos_hash) {
  vector<Edge> edges;
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

static void ExecuteCommand(const Command &command) {
  if (command.name == "positionfromseq") {
    if (command.args.empty()) {
      cerr << "Usage: positionfromseq <number of halfmoves> <sequence of "
              "moves>\n";
      return;
    }
    int halfmoves = std::stoi(command.args[0]);
    if ((int)command.args.size() < halfmoves + 1) {
      cerr << "Usage: positionfromseq <number of halfmoves> <sequence of "
              "moves>\n";
      return;
    }
    Board board;
    for (int i = 1; i <= halfmoves; i++) {
      board.makeMove(uci::uciToMove(board, command.args[i]));
    }
    uint64_t pos_hash = board.hash();
    vector<Edge> edges = FindEdgesFromPosition(board, pos_hash);
    cout << "positionmoves " << edges.size() << '\n';
    for (const Edge &edge : edges) {
      cout << edge.move << " " << edge.count << '\n';
    }
    cout.flush();
    return;
  }
  if (command.name == "exit") {
    exit(0);
  }
}

int main(int argc, char *argv[]) {
  std::ios_base::sync_with_stdio(false);
  std::cin.tie(nullptr);
  if (argc < 2) {
    cerr << "Usage: " << argv[0] << " <input file>\n";
    return 1;
  }
  ReadBook(argv[1]);
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