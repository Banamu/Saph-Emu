from enum import Enum
import socket
import struct
import threading
import time

from durator.world.world_connection import WorldConnection
from pyshgck.concurrency import simple_thread
from pyshgck.logger import LOG


class Population(Enum):

    LOW     = 0
    AVERAGE = 1
    HIGH    = 2
    FULL    = 3

    def as_float(self):
        return float(self.value)


class WorldServer(object):
    """ World server accepting connections from clients.

    It also updates its state regularly to the login server.
    """

    # Hardcoded values, change that TODO
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 13250
    BACKLOG_SIZE = 64

    def __init__(self):
        self.name = "excelen"
        self.population = Population.AVERAGE
        self.host = WorldServer.DEFAULT_HOST
        self.port = WorldServer.DEFAULT_PORT

        self.login_server_socket = None
        self.clients_socket = None
        self.shutdown_flag = threading.Event()

    def start(self):
        LOG.info("Starting world server " + self.name)
        self._start_listening()

        simple_thread(self._handle_login_server_connection)
        self._accept_client_connections()

        self.shutdown_flag.set()
        self._stop_listening()
        LOG.info("World server stopped.")

    def _start_listening(self):
        self.clients_socket = socket.socket()
        self.clients_socket.settimeout(1)
        address = (self.host, self.port)
        self.clients_socket.bind(address)
        self.clients_socket.listen(WorldServer.BACKLOG_SIZE)

    def _accept_client_connections(self):
        try:
            while True:
                self._try_accept_client_connection()
        except KeyboardInterrupt:
            LOG.info("KeyboardInterrupt received, stop accepting clients.")

    def _try_accept_client_connection(self):
        try:
            connection, address = self.clients_socket.accept()
            self._handle_client_connection(connection, address)
        except socket.timeout:
            pass

    def _handle_client_connection(self, connection, address):
        LOG.info("Accepting client connection from " + str(address))
        world_connection = WorldConnection(self, connection, address)
        simple_thread(world_connection.handle_connection)

    def _handle_login_server_connection(self):
        """ Update forever the realm state to the login server. """
        while not self.shutdown_flag.is_set():
            LOG.debug("Sending heartbeat to login server")
            state_packet = self._get_state_packet()
            self._open_login_server_socket()
            if self.login_server_socket:
                self.login_server_socket.sendall(state_packet)
            self._close_login_server_socket()
            time.sleep(30)

    def _get_state_packet(self):
        packet = b""
        name = self.name.encode("ascii")
        packet += int.to_bytes(len(name), 1, "little")
        packet += name
        packet += struct.pack("f", self.population.as_float())
        address = (self.host + ":" + str(self.port)).encode("ascii")
        packet += int.to_bytes(len(address), 1, "little")
        packet += address
        packet = int.to_bytes(len(packet), 1, "little") + packet
        return packet

    def _open_login_server_socket(self):
        self.login_server_socket = socket.socket()
        # Hardcoded login server address, change that TODO
        address = ("127.0.0.1", 3725)
        try:
            self.login_server_socket.connect(address)
        except ConnectionError as exc:
            LOG.error("Couldn't join login server! " + str(exc))
            self.login_server_socket = None

    def _close_login_server_socket(self):
        self.login_server_socket.close()
        self.login_server_socket = None

    def _stop_listening(self):
        self.clients_socket.close()
        self.clients_socket = None
