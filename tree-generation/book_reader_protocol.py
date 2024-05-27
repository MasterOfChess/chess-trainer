import asyncio
import queue
import logging
import enum
from typing import TypeVar, Generic, Any
import abc
import chess
import dataclasses

logger = logging.getLogger(__name__)
T = TypeVar('T')
BookProtocolT = TypeVar('BookProtocolT', bound='BookProtocol')


class CommandState(enum.Enum):
    WAITING = enum.auto()
    RUNNING = enum.auto()
    DONE = enum.auto()


class BaseCommand(Generic[BookProtocolT, T], metaclass=abc.ABCMeta):
    """Base class for commands used by the book reader agent.

    This class defines the common interface and behavior for all commands.

    Attributes:
        state (CommandState):    The current state of the command.
        result (asyncio.Future): The future object representing
                                 the result of the command.
    """

    def __init__(self) -> None:
        self.state = CommandState.WAITING
        self.result: asyncio.Future[T] = asyncio.Future()

    @abc.abstractmethod
    def start(self, book_reader: BookProtocolT) -> None:
        """Start the command. Should set the command state to RUNNING."""

    @abc.abstractmethod
    def on_line(self, book_reader: BookProtocolT, line: str) -> None:
        """Process the command line received from the book reader."""

    def set_done(self, value: T | None) -> None:
        self.state = CommandState.DONE
        if not self.result.done():
            self.result.set_result(value)

    def is_done(self) -> bool:
        return self.state == CommandState.DONE

    def __repr__(self) -> str:
        return (f'<{type(self).__name__}'
                f'(state={self.state}, result={self.result}>')


class BookProtocol(asyncio.SubprocessProtocol):
    """
    Protocol for interacting with a book reader agent.

    This protocol handles the communication between the book reader agent and the client.
    It provides methods for adding commands, sending lines, and receiving data from the agent.

    Attributes:
        loop (asyncio.AbstractEventLoop): The event loop associated with the protocol.
        transport (asyncio.SubprocessTransport | None): The transport used for communication.
        output (bytearray): Buffer for storing the received output from the agent.
        queue (queue.Queue): Queue for storing commands to be executed.
        command (BaseCommand[BookProtocolT, Any] | None): The current command being executed.
    """

    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.transport: asyncio.SubprocessTransport | None = None
        self.output = bytearray()
        self.queue = queue.Queue()
        self.command: BaseCommand[BookProtocolT, Any] | None = None

    def _update_current_command(self) -> None:
        if self.command is None or self.command.is_done():
            try:
                self.command = self.queue.get()
                self.command.start(self)
            except queue.Empty:
                self.command = None

    def connection_made(self, transport: asyncio.SubprocessTransport) -> None:
        self.transport = transport
        logger.debug('%s: Connection made', self)

    def pipe_data_received(self, fd: int, data: bytes) -> None:
        logger.debug('%s: Pipe data received (fd: %s, data: %r)', self, fd,
                     data)
        if fd != 1:
            return
        self.output.extend(data)
        lines = self.output.split(b'\n')
        self.output = lines.pop()
        for line in lines:
            self._update_current_command()
            self.loop.call_soon(self.command.on_line, self,
                                line.decode('utf-8'))

    async def add_command(self, command: BaseCommand[BookProtocolT, T]) -> T:
        logger.debug('%s: Command added: %s', self, command)
        self.queue.put(command)
        self._update_current_command()
        return await command.result

    def send_line(self, line: str) -> None:
        stdin = self.transport.get_pipe_transport(0)
        stdin.write((line + '\n').encode('utf-8'))

    def pipe_connection_lost(self, fd: int, exc: Exception | None) -> None:
        logger.debug('%s: Pipe connection lost (fd: %s, exc: %r)', self, fd,
                     exc)

    def __repr__(self) -> str:
        if self.transport is not None:
            pid = self.transport.get_pid()
        else:
            pid = '?'
        return f'<{type(self).__name__} (pid={pid})>'


class QuitCommand(BaseCommand[BookProtocol, None]):

    def start(self, book_reader: BookProtocol) -> None:
        self.state = CommandState.RUNNING
        book_reader.send_line('quit')
        self.set_done(None)

    def on_line(self, book_reader: BookProtocol, line: str) -> None:
        pass


class ExitCommand(BaseCommand[BookProtocol, None]):

    def start(self, book_reader: BookProtocol) -> None:
        self.state = CommandState.RUNNING
        book_reader.send_line('exit')
        self.set_done(None)

    def on_line(self, book_reader: BookProtocol, line: str) -> None:
        pass


@dataclasses.dataclass
class Edge:
    move: chess.Move
    count: int


@dataclasses.dataclass
class EdgeResult:
    board: chess.Board = chess.Board()
    edges: list[Edge] = dataclasses.field(default_factory=list)


class FromFenCommand(BaseCommand[BookProtocol, EdgeResult]):
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

    def start(self, book_reader: BookProtocol) -> None:
        self.state = CommandState.RUNNING
        book_reader.send_line(f'fromfen {self.fen}')

    def on_line(self, book_reader: BookProtocol, line: str) -> None:
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


class BookReader:
    """
    A class representing a book reader agent.

    Attributes:
        transport (asyncio.SubprocessTransport): The transport used for communication.
        protocol (BookProtocol): The protocol used for communication.

    Methods:
        from_fen: Reads a book from a given FEN string.
        quit: Sends a quit command to the book reader.
        exit: Sends an exit command to the book reader.
        popen: Opens a book reader process.

    """

    def __init__(self, transport: asyncio.SubprocessTransport,
                 protocol: BookProtocol) -> None:
        self.transport = transport
        self.protocol = protocol

    async def from_fen(self, fen: str) -> EdgeResult:
        """
        Reads a book from a given FEN string.

        Args:
            fen (str): The FEN string representing the board position.

        Returns:
            EdgeResult: The result of the operation.

        """
        from_fen_command = FromFenCommand(fen)
        return await self.protocol.add_command(from_fen_command)

    async def quit(self) -> None:
        """
        Sends a quit command to the book reader.

        """
        logger.debug('Quitting')
        quit_command = QuitCommand()
        await self.protocol.add_command(quit_command)

    async def exit(self) -> None:
        """
        Sends an exit command to the book reader.

        """
        exit_command = ExitCommand()
        await self.protocol.add_command(exit_command)

    @classmethod
    async def popen(cls, command: str, *args):
        """
        Opens a book reader process.

        Args:
            command (str): The command to execute.
            *args: Additional arguments to pass to the command.

        Returns:
            BookReader: An instance of the BookReader class.

        """
        transport, protocol = await asyncio.get_running_loop().subprocess_exec(
            BookProtocol, command, *args)
        return cls(transport, protocol)


#----------------------------------------------------------------
# Example usage
#----------------------------------------------------------------

if __name__ == '__main__':

    async def main():
        # logger.setLevel(logging.INFO)
        book_reader = await BookReader.popen('./book_reader', 'tree.bin')
        while True:
            message = input()
            if message.startswith('exit'):
                await book_reader.exit()
                break
            if message.startswith('quit'):
                await book_reader.quit()
                break
            if message.startswith('fromfen'):
                fen = message.split(None, 1)[1]
                result = await book_reader.from_fen(fen)
                print('\n'.join(map(str, result.edges)))
                continue

    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
