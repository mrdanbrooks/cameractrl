#!/usr/bin/env python
import argparse
import re
import sys
sys.DONT_WRITE_BYTECODE = True
import subprocess
import syslog

from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import LineReceiver


def log(msg, priority=syslog.LOG_INFO):
    """ Prints a message and also saves it to the syslog """
    print msg
    syslog.syslog(priority, msg)

class MochadListener(LineReceiver):
    """ Receives messages from mochad server and logs the data """
    delimiter = '\n'

    def __init__(self, mochad_code, start_command, stop_command):
        self.__pattern = "(?:\d{2}/\d{2}) (?:\d{2}:\d{2}:\d{2}) (?:Rx|Tx) (?:RF|RFSEC|PL) (?:[a-zA-Z]+:) (\S+) Func: (\S+)"
        self.__code = mochad_code
        self.__commands = {"On": start_command, "Off": stop_command}

    def connectionMade(self):
        log("Connected!")

    def lineReceived(self, line):
        try:
            input_code, input_cmd = re.findall(self.__pattern, line)[0]
        except Exception as e:
            log("Could not parse input '%s'. Aborting." % line, syslog.LOG_ALERT)
            return

        # Ignore if this is not the code we are looking for
        if not self.__code == input_code:
            log("wrong device, ignoring.", syslog.LOG_INFO)
            return

        # Create command - commands with arguments need put into a list
        if not input_cmd in self.__commands:
            log("Command '%s' not accepted. Supported commands: %s. Aborting." % 
                (input_cmd, ",".join(self.__commands.keys())),
                syslog.LOG_ALERT)
            return

        cmd = self.__commands[input_cmd]
        log("calling '%s'"  % cmd)
        cmd = cmd.split() if ' ' in cmd else cmd
        try:
            ret = subprocess.call(cmd, stdout=open("/dev/null", "w"))
        except Exception:
            log("Command Failed", syslog.LOG_ALERT)
        return

class ConnectionManager(ReconnectingClientFactory):
    """ Automatically manage the connection to the server, reconnecting if the
    connection is lost, and backing off the amount of time between tries. 
    """
    def __init__(self, callback_protocol):
        if not isinstance(callback_protocol, LineReceiver):
            raise Exception("callback_protocol must be instance of type LineReceiver")
        self.callback_protocol = callback_protocol

    def buildProtocol(self, addr):
        """ Returns the callback protocol instance """
        return self.callback_protocol

    def clientConnectionLost(self, connector, reason):
        log("Lost Connection, reason: %s" % reason.getErrorMessage(), syslog.LOG_WARNING)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        log("Connection failed, reason: %s" % reason.getErrorMessage(), syslog.LOG_WARNING)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)

if __name__ == "__main__":
    parser = argparse.ArgumentParser("cameractrl", description="Motion Camera Control")
    parser.add_argument('--host', type=str, required=True, help="ip address of mochad server")
    parser.add_argument('--port', type=int, default=1099, help="mochad listening port")
    parser.add_argument('--code', type=str, default="C1", help="mochad device code to listen to for input signal")
    parser.add_argument('--motion-start-cmd', default='/etc/init.d/motion start', help="motion start command")
    parser.add_argument('--motion-stop-cmd', default='/etc/init.d/motion stop', help="motion stop command")
    args = parser.parse_args()

    listener = MochadListener(args.code, args.motion_start_cmd, args.motion_stop_cmd)
    connection_manager = ConnectionManager(listener)
    reactor.connectTCP(args.host, args.port, connection_manager)
    reactor.run()
