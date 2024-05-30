"""
This module contains the implementation of a book reader protocol.

The module defines the following classes:
- BaseCommand: Base class for commands used by the book reader agent.
- BaseProtocol: Base class representing a protocol for interacting with a subprocess.
- ExitCommand: Command class for exiting the book reader.
- QuitCommand: Command class for quitting the book reader.
- Edge: Data class representing an edge in the book reader.
- EdgeResult: Data class representing the result of generating edges from a FEN position.
- FromFenCommand: Command class for generating edges from a given FEN position.
- BookReader: Class representing the book reader protocol.

Example usage:
book_reader = BookReader.popen('./book_reader', 'tree.bin')
result = book_reader.from_fen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
print('\n'.join(map(str, result.edges)))
"""
import threading
import queue
import concurrent.futures as cf
import logging
import subprocess
import abc
from typing import TypeVar, Generic
import chess
import dataclasses

logging.basicConfig(format='%(asctime)s:%(threadName)s:%(message)s',
                    level=logging.DEBUG,
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

T = TypeVar('T')
ProtocolT = TypeVar('ProtocolT', bound='BaseProtocol')


class BaseCommand(Generic[ProtocolT, T], metaclass=abc.ABCMeta):
    """Base class for commands used by the book reader agent.

    This class defines the common interface and behavior for all commands.

    Attributes:
        result (concurrent.futures.Future): The future object representing
                                            the result of the command.
    """

    def __init__(self) -> None:
        self.result: cf.Future[T] = cf.Future()

    @abc.abstractmethod
    def start(self, protocol: ProtocolT) -> None:
        """Start the command."""

    @abc.abstractmethod
    def on_line(self, protocol: ProtocolT, line: str) -> None:
        """Process the command line received from the book reader."""

    def set_done(self, value: T | None) -> None:
        if not self.result.done():
            self.result.set_result(value)

    def terminate(self):
        self.result.cancel()

    def is_done(self) -> bool:
        return self.result.done()

    def __repr__(self) -> str:
        return f'<{type(self).__name__}, result={self.result}>'


class BaseProtocol():
    """
    BaseProtocol class represents a base protocol for interacting with a subprocess.

    Attributes:
        proc (subprocess.Popen): The subprocess instance.
        thread (threading.Thread): The thread used to run the protocol.
        queue (queue.Queue): The queue used to store commands.
        curr_command (BaseCommand | None): The current command being executed.
        terminate_event (threading.Event): The event used to signal termination.
        lock (threading.Lock): The lock used for thread synchronization.
        stdin_lock (threading.Lock): The lock used for stdin synchronization.
    """

    def __init__(self, proc: subprocess.Popen):
        self.proc = proc
        self.thread = threading.Thread(target=self.run)
        self.queue: queue.Queue[BaseCommand] = queue.Queue()
        self.curr_command: BaseCommand | None = None
        self.terminate_event = threading.Event()
        self.lock = threading.Lock()
        self.stdin_lock = threading.Lock()
        self.thread.start()

    def _update_curr_command(self):
        with self.lock:
            logger.debug('_update_curr_command')
            if self.curr_command is None or self.curr_command.is_done():
                try:
                    self.curr_command = self.queue.get_nowait()
                    logger.debug('Starting command: %s', self.curr_command)
                    self.curr_command.start(self)
                except queue.Empty:
                    self.curr_command = None

    def send_line(self, line: str):
        with self.stdin_lock:
            logger.debug('%s: Send line: %s', self, line)
            self.proc.stdin.write((line + '\n').encode('utf-8'))
            self.proc.stdin.flush()

    def line_received(self, line: str):
        logger.debug('%s: Received line: %s', self, line)
        self._update_curr_command()
        if self.curr_command is not None:
            self.curr_command.on_line(self, line)

    def run(self):
        while not self.terminate_event.is_set():
            line = self.proc.stdout.readline().decode('utf-8')
            if not line:
                break
            self.line_received(line)
        self._clean_up()

    def add_command(self, command: BaseCommand[ProtocolT, T]) -> T:
        logger.debug('%s: Command added: %s', self, command)
        self.queue.put(command)
        self._update_curr_command()
        return command.result.result()

    @classmethod
    def popen(cls, command: str, *args):
        proc = subprocess.Popen([command, *args],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return cls(proc)

    def close(self):
        self.terminate_event.set()
        return self.proc.wait()

    def _clean_up(self):
        while True:
            try:
                command = self.queue.get_nowait()
                command.terminate()
            except queue.Empty:
                break
        self.proc.terminate()
        return self.proc.wait()


class ExitCommand(BaseCommand[BaseProtocol, None]):

    def start(self, protocol: BaseProtocol):
        logger.debug('Exitting')
        protocol.send_line('exit')
        self.set_done(None)

    def on_line(self, protocol: BaseProtocol, line: str):
        pass


class QuitCommand(BaseCommand[BaseProtocol, None]):

    def start(self, protocol: BaseProtocol):
        logger.debug('Quitting')
        protocol.send_line('quit')
        self.set_done(None)

    def on_line(self, protocol: BaseProtocol, line: str):
        pass


@dataclasses.dataclass
class Edge:
    move: chess.Move
    count: int


@dataclasses.dataclass
class EdgeResult:
    board: chess.Board = chess.Board()
    edges: list[Edge] = dataclasses.field(default_factory=list)


class FromFenCommand(BaseCommand[BaseProtocol, EdgeResult]):
    """
    Represents a command to generate edges from a given FEN position.

    Attributes:
        fen (str): The FEN position.
        edge_result (EdgeResult): The result of the command execution.
        expected_lines (int): The number of expected lines to process.
        processed_lines (int): The number of lines processed so far.
    """

    def __init__(self, fen: str) -> None:
        super().__init__()
        self.fen = fen
        self.edge_result = EdgeResult(board=chess.Board(fen))
        self.expected_lines = None
        self.processed_lines = 0

    def start(self, protocol: BaseProtocol) -> None:
        protocol.send_line(f'fromfen {self.fen}')

    def on_line(self, _: BaseProtocol, line: str) -> None:
        words = line.strip().split()
        if words[0] == 'positionmoves':
            self.expected_lines = int(words[1])
            if self.expected_lines == 0:
                self.set_done(self.edge_result)
            return
        assert self.expected_lines is not None
        self.processed_lines += 1
        self.edge_result.edges.append(
            Edge(chess.Move.from_uci(words[0]), int(words[1])))
        if self.processed_lines == self.expected_lines:
            self.set_done(self.edge_result)


class BookReader(BaseProtocol):

    def exit(self) -> int:
        self.add_command(ExitCommand())
        return self.close()

    def quit(self) -> int:
        self.add_command(QuitCommand())
        return self.close()

    def from_fen(self, fen: str):
        return self.add_command(FromFenCommand(fen))


#######################################################
# Example usage
#######################################################

if __name__ == '__main__':

    def main():
        book_reader = BookReader.popen('./book_reader', 'tree.bin')
        while True:
            message = input()
            if message.startswith('exit'):
                print(book_reader.exit())
                break
            if message.startswith('quit'):
                print(book_reader.quit())
                break
            if message.startswith('fromfen'):
                fen = message.split(None, 1)[1]
                result = book_reader.from_fen(fen)
                print('\n'.join(map(str, result.edges)))
                continue

    main()
