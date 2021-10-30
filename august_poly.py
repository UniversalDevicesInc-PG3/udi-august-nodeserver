#!/usr/bin/env python3

"""
This is a NodeServer for August written by automationgeek (Jean-Francois Tremblay)
based on the NodeServer template for Polyglot v2 written in Python2/3 by Einstein.42 (James Milne) milne.james@gmail.com
"""

import udi_interface
import hashlib
import uuid
import time
import json
import sys
import ast
from copy import deepcopy
from august.api import Api 
from august.authenticator import Authenticator, AuthenticationState, ValidationResult
from august.lock import LockDetail, LockDoorStatus, LockStatus


LOGGER = udi_interface.LOGGER
Custom = udi_interface.Custom

class Controller(udi_interface.Node):

    def __init__(self, polyglot, primary, address, name):
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.name = 'August'
        self.poly = polyglot
        self.queryON = False
        self.email = ""
        self.password = ""
        self.install_id = ""
        self.userDict = ""
        self.hb = 0
        self.api = None
        self.authenticator = None
        self.authentication = None
        self.userDictEnable = False

        self.CustomData = Custom(polyglot, 'customdata')

        polyglot.subscribe(polyglot.START, self.start, address)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.POLL, self.shortPoll)

        polyglot.read()
        polyglot.addNode(self)

    def parameterHandler(self, params):
        try:
            if 'email' in params:
                self.email = params['email']
            else:
                self.email = ""
                
            if 'password' in params:
                self.password = params['password']
            else:
                self.password = ""
            
            # Generate a UUID ( 11111111-1111-1111-1111-111111111111 )
            if 'install_id' in params:
                self.install_id = params['install_id']
            else:
                # FIXME: this saves in custom data but never queries custom data
                self.install_id = str(uuid.uuid4())
                self.CustomData['install_id'] = self.install_id
                LOGGER.debug('UUID Generated: {}'.format(self.install_id))

            if 'tokenFilePath' in params:
                self.tokenFilePath = params['tokenFilePath']
            else:
                self.tokenFilePath = ""
            
            # {'John Doe': 1, 'Paul Doe':2}
            if 'userDict' in params:
                self.userDict = params['userDict']
                self.userDictEnable = True
            else:
                self.userDict = "{'None': 0}"
            
            if self.email == "" or self.password == "" or self.tokenFilePath == "":
                LOGGER.error('August requires email,password,tokenFilePath parameters to be specified in custom configuration.')
                return False
            else:
                self.discover()

        except Exception as ex:
            LOGGER.error('Error starting August NodeServer: %s', str(ex))

    def start(self):
        LOGGER.info('Started August for v2 NodeServer version %s', str(VERSION))
        self.setDriver('ST', 1)
        self.poly.updateProfile()
        self.poly.setCustomParamsDoc()
    
    def query(self):
        for node in self.poly.nodes():
            node.reportDrivers()
    
    def poll(self, pollflag):
        if 'shortPoll' in pollflag:
            self.setDriver('ST', 1)
            for node in self.poly.nodes():
                if  node.queryON == True :
                    node.update()
        else:
            self.heartbeat()
        
            # Refresh Token
            self.authenticator.refresh_access_token()

    def heartbeat(self):
        LOGGER.debug('heartbeat: hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def discover(self, *args, **kwargs):
        count = 1
        
        self.api = Api(timeout=20)
        self.authenticator = Authenticator(self.api, "email", self.email, self.password, install_id=self.install_id, access_token_cache_file=self.tokenFilePath)
        self.authentication = self.authenticator.authenticate()
        if ( self.authentication.state is AuthenticationState.AUTHENTICATED ) :
            locks = self.api.get_locks(self.authentication.access_token)
            for lock in locks:
                myhash =  str(int(hashlib.md5(lock.device_id.encode('utf8')).hexdigest(), 16) % (10 ** 8))
                self.poly.addNode(AugustLock(self.poly,self.address,myhash,  "lock_" + str(count),self.api, self.authentication, lock ))
                count = count + 1
        else :
            self.authenticator.send_verification_code()
            LOGGER.error('August requires validation, please send your authentification code')
        
    def delete(self):
        LOGGER.info('Deleting August')

    def send_validation_code(self,command) :
        LOGGER.info("Send Validation Code")
        val = int(command.get('value'))
        validation_result = self.authenticator.validate_verification_code(val)
        
        if ( validation_result is ValidationResult.INVALID_VERIFICATION_CODE ) :
            LOGGER.info("Invalid Verification Code : %s", str(val) )
            
        self.authentication = self.authenticator.authenticate()
        if ( self.authentication.state is not AuthenticationState.AUTHENTICATED ) :
            LOGGER.info("Invalid Authentication Code")
        else :
            LOGGER.info("Successfully Authentificated")

    id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'VALIDATE_CODE': send_validation_code,
    }
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}, 
               {'driver': 'GV3', 'value': 0, 'uom': 56}]

class AugustLock(udi_interface.Node):

    def __init__(self, polyglot, primary, address, name, api, authentication, lock):

        super(AugustLock, self).__init__(polyglot, primary, address, name)
        self.queryON = True
        self.api = api
        self.authentication = authentication
        self.lock = lock
        self.userDictEnable = self.primary.userDictEnable
        self.userDict = ast.literal_eval(self.primary.userDict)

    def start(self):
        self.setDriver('GV2', 101)
        self.setDriver('GV4', 101)

    def setOn(self, command):
        self.api.lock(self.authentication.access_token,self.lock.device_id)
        self.setDriver('GV2', 100)
        self.reportCmd('LOCK')
        
    def setOff(self, command):
        self.api.unlock(self.authentication.access_token,self.lock.device_id)
        self.setDriver('GV2', 0)
        self.reportCmd('UNLOCK')
    
    def query(self):
        self.reportDrivers()
    
    def update(self):
        try :
            if self.api.get_lock_status(self.authentication.access_token,self.lock.device_id) is LockStatus.UNLOCKED :
                self.setDriver('GV2', 0) 
            elif self.api.get_lock_status(self.authentication.access_token,self.lock.device_id) is LockStatus.LOCKED :
                self.setDriver('GV2', 100) 
            else :
                self.setDriver('GV2', 101) 

            battlevel = self.api.get_lock_detail(self.authentication.access_token,self.lock.device_id).battery_level
            self.setDriver('GV1', int(battlevel))
            
            doorStatus = self.api.get_lock_door_status(self.authentication.access_token,self.lock.device_id)
            if doorStatus is LockDoorStatus.OPEN :
                self.setDriver('GV4', 0)
            elif doorStatus is LockDoorStatus.CLOSED :
                self.setDriver('GV4', 100)
            else :
                self.setDriver('GV4', 101)

            if ( self.userDictEnable ) :
                lastUser = self.api.get_house_activities(self.authentication.access_token,self.lock.house_id)[0].operated_by
                val = 0 
                for key in self.userDict  :
                    if key == lastUser :
                        val = self.userDict[key]
                self.setDriver('GV5',val)
            
        except Exception as ex:
            LOGGER.error('query: %s', str(ex))
            self.setDriver('GV1', 0)
            self.setDriver('GV2', 101)
            self.setDriver('GV4', 101)

    drivers = [{'driver': 'GV2', 'value': 100, 'uom': 11},
               {'driver': 'GV1', 'value': 0, 'uom': 51},
               {'driver': 'GV4', 'value': 100, 'uom': 79},
               {'driver': 'GV5', 'value': 0, 'uom': 56}]

    id = 'AUGUST_LOCK'
    commands = {
                    'LOCK': setOn,
                    'UNLOCK': setOff
                }

if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start()
        Controller(polyglot, 'controller', 'controller', 'AugustNodeServer')
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
