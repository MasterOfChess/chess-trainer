# Chess Openings Trainer
## Instalation
Download the repository and run:
```bash
cd chess-trainer
chmod +x install.sh
./install.sh
```
or execute following commands:
```bash
cd chess-trainer
# Install required packages
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


# Download and build stockfish
# You can also just put the binary in the src/static/stockfish/ directory
git clone https://github.com/official-stockfish/Stockfish.git
cd Stockfish/src
make -j profile-build ARCH=x86-64
cd ../..
mkdir src/trainer/static/stockfish
cp Stockfish/src/stockfish* src/trainer/static/stockfish/
rm -rf Stockfish

# Compile book_reader.cc
cd tree-generation
make book_reader
mv book_reader ../src/trainer/static/book_reader
cd ..

# Make bash scripts executable
chmod +x run_trainer.sh
```

## Running the app
You can run the app with `run_trainer.sh` script.
Opening app is as easy as opening `http://localhost:5000` in your browser.