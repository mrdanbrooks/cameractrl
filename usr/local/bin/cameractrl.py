#!/usr/bin/env python
# Copyright 2014 Dan Brooks
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""" Listens to X10 signals from Mochad Server and turns on and off Motion camera service """
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
    """ Listens to mochad sever for signals to control Motion webcam and security light """
    delimiter = '\n'

    def __init__(self, mochad_inputcode, start_command, stop_command, mochad_lightcode):
        self.__pattern = "(?:\d{2}/\d{2}) (?:\d{2}:\d{2}:\d{2}) (?:Rx|Tx) (?:RF|RFSEC|PL) (?:[a-zA-Z]+:) (\S+) Func: (\S+)"
        self.__inputcode = mochad_inputcode
        self.__motioncommands = {"On": start_command, "Off": stop_command}
        self.__lightcode = mochad_lightcode

    def connectionMade(self):
        log("Connected!")

    def lineReceived(self, line):
        try:
            input_code, input_cmd = re.findall(self.__pattern, line)[0]
        except Exception as e:
            log("Could not parse input '%s'. Aborting." % line, syslog.LOG_ALERT)
            return

        # Ignore if this is not the input code we are looking for
        if not self.__inputcode.lower() == input_code.lower():
#             log("wrong device, ignoring.", syslog.LOG_INFO)
            return

        # Ignore if we do not understand the command
        if not input_cmd in self.__motioncommands:
            log("Command '%s' not accepted. Supported commands: %s. Aborting." % 
                (input_cmd, ",".join(self.__motioncommands.keys())),
                syslog.LOG_ALERT)
            return

        # Execute camera command. Commands with arguments need to be put into a list
        cmd = self.__motioncommands[input_cmd]
        cmd = cmd.split() if ' ' in cmd else cmd
        log("executing '%s'"  % self.__motioncommands[input_cmd], syslog.LOG_DEBUG)
        try:
            ret = subprocess.call(cmd, stdout=open("/dev/null", "w"))
        except Exception:
            log("Command Failed", syslog.LOG_ALERT)
            return

        # Execute Light Command
        cmd = "rf %s %s" % (self.__lightcode, input_cmd.lower())
        log("Sending mochad '%s'" % cmd, syslog.LOG_DEBUG)
        self.sendLine(cmd)
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
    parser.add_argument('--inputcode', type=str, default="A1", help="mochad device code to listen to for input signal")
    parser.add_argument('--motion-start-cmd', default='/etc/init.d/motion start', help="motion start command")
    parser.add_argument('--motion-stop-cmd', default='/etc/init.d/motion stop', help="motion stop command")
    parser.add_argument('--camera-light-code', default='a2', help="X10 device code for camera infrared light")
    args = parser.parse_args()

    listener = MochadListener(args.inputcode, 
                              args.motion_start_cmd, 
                              args.motion_stop_cmd, 
                              args.camera_light_code)
    
    connection_manager = ConnectionManager(listener)
    reactor.connectTCP(args.host, args.port, connection_manager)
    reactor.run()
    log("Shutting down")
