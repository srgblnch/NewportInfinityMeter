#!/usr/bin/env python

##############################################################################
## license : GPLv3+
##============================================================================
##
## File :        infs.py
## 
## Project :     NewportInfinityMeter
##
## This file is part of Tango device class.
## 
## Tango is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## Tango is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
## 
## You should have received a copy of the GNU General Public License
## along with Tango.  If not, see <http://www.gnu.org/licenses/>.
## 
##
## $Author :      sblanch$
## Copyright 2013 CELLS / ALBA Synchrotron, Bellaterra, Spain
##
## $Revision :    $
##
## $Date :        $
##
## $HeadUrl :     $
##############################################################################

import PyTango
import taurus
import array
import time
import traceback

MINREADTIME = 0.1
ANSWERRETRIES = 5

class InfinityMeterSerial(taurus.Logger):
    '''The abstract superclass.
    '''
    def __init__(self):
        taurus.Logger.__init__(self,"INFS")

class INFSSerialDevFile(InfinityMeterSerial):
    '''Class to manage the communications using a /dev/tty* file.
    '''
    def __init__(self,fileName):
        InfinityMeterSerial.__init__(self)
        self._fileName =fileName
        self._file = None
    def open(self):
        self._file = open(self._fileName,'r+')#Read and write
    def close(self):
        if self._file != None:
            self._file.close()
    def isOpen(self):
        if self._file != None and not self._file.closed:
            return True
        return False
    def flush(self):
        self._file.flush()
        while len(self._file.readline()) != 0:
            pass
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        self.debug("sending: %s"%(repr(cmd)))
        self._file.write(cmd)
    def read(self):
        answer = self._file.readline()
        self.debug("received %s"%(repr(answer)))
        return answer

class INFSTango(InfinityMeterSerial):
    '''Abstract class for communicate using Tango.
    '''
    def __init__(self,proxy):
        InfinityMeterSerial.__init__(self)
        self._proxy = proxy

class INFSSerialDevice(INFSTango):
    '''Class to manage the communications using a Tango device 
       with Serial DeviceClass.
    '''
    def __init__(self,proxy):
        INFSTango.__init__(self,proxy)
    #FIXME: check this device class methods for open&close (and isOpen)
    def open(self):
        pass
    def close(self):
        pass
    def isOpen(self):
        pass
    def flush(self):
        self._proxy.DevSerFlush(2)
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        self.debug("sending: %s"%(repr(cmd)))
        self._proxy.DevSerWriteString(cmd)
    def read(self):
        answer = self._proxy.DevSerReadNChar(13)
        self.debug("received %s"%(repr(answer)))
        return answer

class INFSPySerialDevice(INFSTango):
    '''Class to manage the communications using a Tango device 
       with PySerial DeviceClass.
    '''
    def __init__(self,proxy):
        INFSTango.__init__(self,proxy)
    def open(self):
        if self._proxy.state() == PyTango.DevState.OFF:
            self._proxy.open()
    def close(self):
        if self._proxy.state() == PyTango.DevState.ON:
            self._proxy.close()
    def isOpen(self):
        if self._proxy.state() == PyTango.DevState.ON:
            return True
        return False
    def flush(self):
        self._proxy.FlushInput()
        self._proxy.FlushOutput()
    def write(self,address,command):
        cmd = "*%s%s\r"%(address,command)
        cmdlist = array.array('B',cmd).tolist()
        self.debug("sending: %s"%(repr(cmd)))
        self._proxy.write(cmdlist)
    def read(self):
        answer = array.array('B',self._proxy.readline()).tostring()
        self.debug("received %s"%(repr(answer)))
        return answer

class InfinityMeter(taurus.Logger):
    '''Interface class to made the connection transparent and 
       homogeneous access.
    '''

    commands = {'UnfilteredValue':'X01',
                'PeakValue':      'X02',
                'ValleyValue':    'X03',
                'FilteredValue':  'X04'}

    def __init__(self,serialName,
                 addr='',sleepTime=MINREADTIME,logLevel=taurus.Logger.Info):
        taurus.Logger.__init__(self,"InfinityMeter")
        if serialName.startswith('/dev/tty'):
            #this will connect direct by serial line
            self._serial = INFSSerialDevFile(serialName)
        else:
            #other way, it shall be a tango device name 
            #of a serial or a pyserial
            try:
                proxy = PyTango.DeviceProxy(serialName)
            except PyTango.DevFailed,e:
                raise NameError(e.args[-1].desc)
            if proxy.info().dev_class == 'PySerial':
                self._serial = INFSPySerialDevice(proxy)
            elif proxy.info().dev_class == 'Serial':
                self._serial = INFSSerialDevice(proxy)
            else:
                raise NotImplementedError("Unable to identify how to manage "\
                                          "the given name %s"%(serialName))
        self._serial.setLogLevel(logLevel)
        self._address = addr
        if sleepTime>=MINREADTIME:
            self._sleepTime = sleepTime
        else:
            #TODO: trace that
            self._sleepTime = MINREADTIME

    def open(self):
        self._serial.open()
    def close(self):
        self._serial.close()
    def _flush(self):
        self._serial.flush()
    def _write(self,command):
        self._serial.write(self._address,command)
    def _read(self):
        return self._serial.read()
    
    def _sendAndReceive(self,cmd):
        self._flush()
        self._write(cmd)
        i = 0
        while i < ANSWERRETRIES:
            time.sleep(self._sleepTime)
            answer = self._read()
            if len(answer) != 0:
                break
            i += 1
        if i == ANSWERRETRIES:
            self.error("Too many null answers to '%s%s'"
                       %(self._address,repr(cmd)[1:-1]))
            raise ValueError("No answer received to '%s%s'"
                             %(self._address,repr(cmd)[1:-1]))
        return self._postprocessAnswer(cmd, answer)
    
    def _postprocessAnswer(self,cmd,answer):
        if answer.count('?'):
            # IN CASE OF OVERFLOW, THE ANSWER IS: '0_X0_?+999999\r'
            self.warning("Received an overflow answer: %s"%(repr(answer)))
            #raise OverflowError("")
            return float('NaN')
        if not answer.startswith(self._address):
            self.error("Answer %s is not from the expected address %s."
                       %(repr(answer),self._address))
            return float('NaN')
        command = "%s%s"%(self._address,cmd)
        if not answer.startswith(command):
            self.error("Answer %s is not to my question '*%s\\r'."
                       %(repr(answer),command))
            return float('NaN')
        else:
            #FIXME: this is no exception protected.
            answer = answer.strip().replace(command,'')
            self.debug("Answer string: %s"%(repr(answer)))
            return float(answer)
    #####
    #---- object methods
    
    def getUnfilteredValue(self):
        return self._sendAndReceive(self.commands['UnfilteredValue'])
    def getPeakValue(self):
        return self._sendAndReceive(self.commands['PeakValue'])
    def getValleyValue(self):
        return self._sendAndReceive(self.commands['ValleyValue'])
    def getFilteredValue(self):
        return self._sendAndReceive(self.commands['FilteredValue'])

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-s',"--serial",default=None,
                      help="String with the reference name "\
                      "to use for serial line connection.")
    parser.add_option('-a',"--address",default='',
                      help="Two digit string with the address of the INFS.")
    parser.add_option('-t',"--sleep",type="float",default=MINREADTIME,
                      help="Wait time between write and read operations")
    parser.add_option('',"--log-level",default="info",
                      help="Define the logging level to print out. Allowed "\
                      "values error|warning|info|debug, being info the "\
                      "default")
    parser.add_option('-r',"--reads",type='int',default=1,
                      help="Number of consecutive sets of readings")
    (options, args) = parser.parse_args()
    logLevel = {'error':taurus.Logger.Error,
                'warning':taurus.Logger.Warning,
                'info':taurus.Logger.Info,
                'debug':taurus.Logger.Debug
               }[options.log_level.lower()]
    if options.serial != None:
        try:
            infs = InfinityMeter(options.serial,options.address,
                                 options.sleep,logLevel)
            for i in range(1,options.reads+1):
                infs.open()
                infs._flush()
                unfiltered = infs.getUnfilteredValue()
                peak = infs.getPeakValue()
                valley = infs.getValleyValue()
                filtered = infs.getFilteredValue()
                print("read: %d/%d\n"\
                      "Unfiltered Value: %g\n"\
                      "Filtered:         %g\n"\
                      "Peak:             %g\n"\
                      "Valley:           %g\n"
                      %(i,options.reads,unfiltered,filtered,peak,valley))
                infs.close()
        except Exception,e:
            print("Error testing the Infinity Meter: '%s'"%(e))
            traceback.print_exc()
            sys.exit(-1)

if __name__ == "__main__":
    '''When this file is called from the command line a test is performed 
       using the argument as the builder for the serial line communication.
    '''
    import sys
    main()
    
