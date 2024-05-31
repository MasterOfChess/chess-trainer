# chess-trainer
# Instalation
Download the repository and run following commands from the repository directory.
```bash
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
mkdir src/static/stockfish
cp Stockfish/stockfish* src/static/stockfish/
rm -rf Stockfish

# Compile book_reader.cc
cd tree-generation
make book_reader
mv book_reader ../src/static/book_reader
cd ..

# Make bash scripts executable
chmod +x run_trainer.sh
chmod +x open_app.sh
```

# Running the app
You can ran the app with `run_trainer.sh` script.
Opening app is as easy as opening `http://localhost:5000` in your browser.
Alternatively you can use `open_app.sh` script.