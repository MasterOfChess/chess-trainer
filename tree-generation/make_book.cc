/*
 * make_book.cc
 * reads pgn file from standard input and generates a book (binary file)
 * format of the generated file:
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
 *  book filename
 *  number of games in the input pgn file
 *  expected number of accepted games
 *  max depth of the book tree in halfmoves
 *  first eco code in accepted interval
 *  last eco code in accepted interval
 *  random generator seed
 *
 * Example usage:
 *  zstdcat ../data/lichess_db_standard_rated_2024-04.pgn.zst | \
 *  ./make_book semi_slav 91383489 100000 30 D43 D49 73632
 */
#include "./chess-library/include/chess.hpp"
#include <chrono>
#include <fstream>
#include <iomanip>
#include <memory>
#include <random>
#include <set>
#include <string>
#include <vector>
using std::cerr;
using std::cin;
using std::cout;
using std::set;
using std::string;
using std::vector;
using namespace chess;
using namespace std::chrono;

class Clock {
public:
  Clock() : start(high_resolution_clock::now()) {}
  int64_t Elapsed() const {
    auto end = high_resolution_clock::now();
    return duration_cast<milliseconds>(end - start).count();
  }

private:
  high_resolution_clock::time_point start;
};

class ProgressPrinter {
public:
  ProgressPrinter(int n_games) : NUMBER_OF_GAMES(n_games), internal_clock() {}

  void startPgn() {
    processed_games++;
    PrintProgress();
  }
  void startMoves(int ac) { accepted_games = ac; }

private:
  const int NUMBER_OF_GAMES;
  int accepted_games{0};
  int processed_games{0};
  Clock internal_clock;

  string ReadableNumber(int x) {
    string res;
    if (x == 0) {
      return "0";
    }
    while (x > 0) {
      string y = std::to_string(x % 1000);
      if (x >= 1000) {
        y.insert(y.begin(), 3 - y.size(), '0');
      }
      res = y + " " + res;
      x /= 1000;
    }
    return res;
  }
  void PrintProgress() {
    if (processed_games % 10000 == 0) {
      cout << "\rProgress: " << std::setw(2) << std::setfill(' ')
           << processed_games * 100ll / NUMBER_OF_GAMES;
      cout << "." << std::setw(3) << std::setfill('0')
           << processed_games * 100000ll / NUMBER_OF_GAMES % 1000 << "% ";
      cout << "Elapsed: " << std::setw(3) << std::setfill(' ')
           << internal_clock.Elapsed() / 1000;
      cout << "." << std::setw(3) << std::setfill('0')
           << internal_clock.Elapsed() % 1000 << "s, ";
      cout << "Accepted: " << ReadableNumber(accepted_games);
      cout.flush();
    }
  }
};

class HeaderFilter {
public:
  void header(std::string_view key, std::string_view value) {
    if (key == "TimeControl") {
      time_control = string(value);
    }
    if (key == "WhiteElo") {
      if (value != "" && value != "-") {
        white_elo = std::stoi(string(value));
      }
    }
    if (key == "BlackElo") {
      if (value != "" && value != "-") {
        black_elo = std::stoi(string(value));
      }
    }
    if (key == "Termination" && value == "Abandoned") {
      abandoned = true;
    }
  }

  void startPgn() {
    time_control = "";
    white_elo = -1;
    black_elo = -1;
    abandoned = false;
  }
  bool shouldSkip() {
    return abandoned || white_elo < 0 || black_elo < 0 ||
           std::abs(white_elo - black_elo) > 200 ||
           valid_time_controls.find(time_control) == valid_time_controls.end();
  }

private:
  const set<string> valid_time_controls = {"180+0", "300+0", "600+0", "180+2",
                                           "120+1", "300+3", "600+5"};
  string time_control;
  int white_elo = -1;
  int black_elo = -1;
  bool abandoned = false;
};

struct DumpInfo {
  int n_accepted_games;
  int n_edges;
};

class BookCreator {
public:
  BookCreator(const string &filename, int expected_size, int seed)
      : file(filename, std::ios::binary), ACCEPTED_LIMIT(expected_size),
        gen(seed), distribution(0, expected_size - 1), real_coin(0, 1) {
    if (!file.is_open()) {
      cerr << "Cannot open file " + std::string(filename) << std::endl;
      exit(1);
    }
  }

  int acceptedGames() const { return (int)games.size(); }

  bool shouldSkip() {
    game_count++;
    if ((int)games.size() < ACCEPTED_LIMIT) {
      games.push_back(Game{});
      return false;
    }
    if (real_coin(gen) > ACCEPTED_LIMIT / (double)game_count) {
      return true;
    }
    int index = distribution(gen);
    std::swap(games[index], games.back());
    games.back().game_moves.clear();
    return false;
  }

  void startMoves() {
    board = Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  }

  void move(std::string_view move, std::string_view comment) {
    chess::Move move_repr = uci::parseSan(board, move);
    registerMove(move_repr);
    board.makeMove(move_repr);
  }

  DumpInfo dumpBook() {
    std::vector<Entry> entries;
    for (const auto &game : games) {
      for (const auto &entry : game.game_moves) {
        entries.push_back(entry);
      }
    }
    DumpInfo info{(int)games.size(), (int)entries.size()};
    std::sort(
        entries.begin(), entries.end(), [](const Entry &a, const Entry &b) {
          if (a.zobrist == b.zobrist && a.source_square == b.source_square) {
            return a.destination_square < b.destination_square;
          }
          return a.zobrist < b.zobrist ||
                 (a.zobrist == b.zobrist && a.source_square < b.source_square);
        });
    for (int i = 0; i < (int)entries.size(); i++) {
      int count = 1;
      while (i + 1 < (int)entries.size() &&
             entries[i].zobrist == entries[i + 1].zobrist &&
             entries[i].source_square == entries[i + 1].source_square &&
             entries[i].destination_square ==
                 entries[i + 1].destination_square) {
        count++;
        i++;
      }
      writeMove(entries[i], count);
    }
    file.flush();
    entries.clear();
    return info;
  }

private:
  Board board;
  std::ofstream file;
  struct Entry {
    uint64_t zobrist;
    chess::Square source_square;
    chess::Square destination_square;
    bool promotion;
    chess::PieceType promotion_piece;
  };
  struct Game {
    std::vector<Entry> game_moves;
  };
  std::vector<Game> games;
  const int ACCEPTED_LIMIT;
  std::mt19937 gen;
  std::uniform_int_distribution<int> distribution;
  std::uniform_real_distribution<double> real_coin;
  int game_count{0};

  void registerMove(chess::Move move) {
    Entry entry;
    if (move.typeOf() == move.PROMOTION) {
      entry = Entry{board.hash(), move.from(), move.to(), true,
                    move.promotionType()};
    } else {
      entry = Entry{board.hash(), move.from(), move.to(), false,
                    chess::PieceType::PAWN};
    }
    games.back().game_moves.push_back(entry);
  }

  void writeMove(const Entry &entry, int count) {
    uint64_t zobrist = entry.zobrist;
    uint8_t source_square = entry.source_square.index();
    uint8_t destination_square = entry.destination_square.index();
    uint8_t promotion = entry.promotion;
    uint8_t promotion_piece = entry.promotion_piece;
    uint32_t cnt = count;
    file.write(reinterpret_cast<char *>(&zobrist), sizeof(zobrist));
    file.write(reinterpret_cast<char *>(&source_square), sizeof(source_square));
    file.write(reinterpret_cast<char *>(&destination_square),
               sizeof(destination_square));
    file.write(reinterpret_cast<char *>(&promotion), sizeof(promotion));
    file.write(reinterpret_cast<char *>(&promotion_piece),
               sizeof(promotion_piece));
    file.write(reinterpret_cast<char *>(&cnt), sizeof(cnt));
  }
};

class DepthFilter {
public:
  DepthFilter(int max_depth) : max_depth(max_depth) {}
  void startMoves() { depth = 0; }
  void move(std::string_view move, std::string_view comment) { depth++; }
  bool shouldSkip() { return depth > max_depth; }

private:
  const int max_depth;
  int depth;
};

class EcoFilter {
public:
  EcoFilter(const vector<string> &valid_codes)
      : valid_codes(valid_codes.begin(), valid_codes.end()) {}
  void startPgn() { eco = ""; }
  void header(std::string_view key, std::string_view value) {
    if (key == "ECO") {
      eco = string(value);
    }
  }
  bool shouldSkip() { return valid_codes.find(eco) == valid_codes.end(); }

private:
  set<string> valid_codes;
  string eco;
};

class BookVisitor : public pgn::Visitor {
public:
  explicit BookVisitor(int n_games, int seed, int expected_size,
                       const string &filename, int max_depth,
                       const vector<string> &valid_codes)
      : header_filter(std::make_unique<HeaderFilter>()),
        progress_printer(std::make_unique<ProgressPrinter>(n_games)),
        book_creator(
            std::make_unique<BookCreator>(filename, expected_size, seed)),
        depth_filter(std::make_unique<DepthFilter>(max_depth)),
        eco_filter(std::make_unique<EcoFilter>(valid_codes)) {}
  void startPgn() {
    header_filter->startPgn();
    progress_printer->startPgn();
    eco_filter->startPgn();
  }
  void startMoves() {
    if (header_filter->shouldSkip() || eco_filter->shouldSkip()) {
      skipPgn(true);
      return;
    }
    // Important that this is the last filter called
    if (book_creator->shouldSkip()) {
      skipPgn(true);
      return;
    }
    progress_printer->startMoves(book_creator->acceptedGames());
    book_creator->startMoves();
    depth_filter->startMoves();
  }
  void header(std::string_view key, std::string_view value) {
    header_filter->header(key, value);
    eco_filter->header(key, value);
  }
  void move(std::string_view move, std::string_view comment) {
    depth_filter->move(move, comment);
    if (depth_filter->shouldSkip()) {
      return;
    }
    book_creator->move(move, comment);
  }
  void endPgn() {}
  DumpInfo dumpBook() { return book_creator->dumpBook(); }

private:
  std::unique_ptr<HeaderFilter> header_filter;
  std::unique_ptr<ProgressPrinter> progress_printer;
  std::unique_ptr<BookCreator> book_creator;
  std::unique_ptr<DepthFilter> depth_filter;
  std::unique_ptr<EcoFilter> eco_filter;
};

vector<string> genEcoCodes(const string &start, const string &end) {
  vector<string> codes;
  string code = start;
  while (code != end) {
    codes.push_back(code);
    code[2]++;
    if (code[2] > '9') {
      code[2] = '0';
      code[1]++;
    }
    if (code[1] > '9') {
      code[1] = '0';
      code[0]++;
    }
  }
  codes.push_back(end);
  return codes;
}

int main(int argc, char *argv[]) {
  std::ios_base::sync_with_stdio(false);
  std::cin.tie(nullptr);
  if (argc < 8) {
    cerr << "Usage: " << argv[0]
         << " <output file> <n_games> <n_accepted_games> <max_depth> "
            "<start_eco_code> <end_eco_code> <seed>\n";
    return 1;
  }
  std::string filename = argv[1];
  int n_games = std::stoi(argv[2]);
  int n_accepted_games = std::stoi(argv[3]);
  int max_depth = std::stoi(argv[4]);
  string start_eco_code = argv[5];
  string end_eco_code = argv[6];
  int seed = std::stoi(argv[7]);
  vector<string> valid_codes = genEcoCodes(start_eco_code, end_eco_code);
  auto vis =
      std::make_unique<BookVisitor>(n_games, seed, n_accepted_games,
                                    filename + ".bin", max_depth, valid_codes);

  pgn::StreamParser parser(std::cin);
  parser.readGames(*vis);
  const auto dump_info = vis->dumpBook();
  std::ofstream ofs(filename + ".txt");
  ofs << "Games: " << dump_info.n_accepted_games << '\n'
      << "Moves: " << dump_info.n_edges << '\n';
  ofs.flush();
  ofs.close();
  cout << "\nDumped " << dump_info.n_edges << " edges from "
       << dump_info.n_accepted_games << " games" << std::endl;
}