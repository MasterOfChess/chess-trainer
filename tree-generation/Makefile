ifeq ($(OS),Windows_NT)
    CXX = g++
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Linux)
        CXX = g++
    endif
    ifeq ($(UNAME_S),Darwin)
        CXX = clang++
    endif
endif

CXXFLAGS = -std=c++17 -O3 -march=native -g -W -Wall -Wextra

all: book_reader make_book

make_book: make_book.cc
	$(CXX) $(CXXFLAGS) -o $@ $<

book_reader: book_reader.cc
	$(CXX) $(CXXFLAGS) -o $@ $<

clean:
	rm -f book_reader make_book