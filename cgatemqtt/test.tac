from twisted.application import service
from twisted.application.app import  AppLogger
from twisted.internet import reactor
from twisted.logger import Logger, FilteringLogObserver, FileLogObserver, textFileLogObserver, LogLevelFilterPredicate, LogLevel
from twisted.internet.endpoints import clientFromString
from twisted.application.internet import ClientService
from twisted.application.service import Application, Service
from twisted.python.log import ILogObserver
from twisted.python.logfile import DailyLogFile

import sys

log = Logger(namespace='test')

application = service.Application("cgatemqtt")
service.IProcess(application).processName = "cgatemqtt"
serviceCollection = service.IServiceCollection(application)

class MyService(Service):
    def startService(self):
        for i in range(5):
            log.debug('debug log')
            log.info('Info log')
            log.warn('warn log')
            log.error('error log')
            log.critical('critical log')

s = MyService()
s.setServiceParent(serviceCollection)

isLevel = LogLevelFilterPredicate(LogLevel.warn)

lo = FilteringLogObserver(observer=textFileLogObserver(sys.stdout), predicates=[isLevel])

application.setComponent(ILogObserver, lo)
