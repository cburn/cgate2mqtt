from twisted.python import usage
from twisted.application import service
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString
from twisted.logger import LogLevel, FilteringLogObserver, textFileLogObserver, LogLevelFilterPredicate
from twisted.python import syslog
from mqtt.client.factory import MQTTFactory
import cgatemqtt

import sys

logLevelFilterPredicate = LogLevelFilterPredicate(defaultLogLevel=LogLevel.info)
logStdout = textFileLogObserver(sys.stdout)
logSyslog = syslog.SyslogObserver('cgatemqqt').emit
logStdoutOrSyslog = logStdout

class Options(usage.Options):
    optParameters = [
        ['loglevel', 'l', 'info', 'Set the logging level.']
    ]
    optFlags = [
        ['syslog', '', 'Log to syslog']
    ]

def makeService(config):
    global logLevelFilterPredicate
    global logSyslog
    global logStdout
    global logStdoutOrSyslog

    logLevelFilterPredicate.setLogLevelForNamespace(
        namespace='CGateMQTT',
        level=LogLevel.levelWithName(config['loglevel']))
    logLevelFilterPredicate.setLogLevelForNamespace(
        namespace='mqtt',
        level=LogLevel.levelWithName(config['loglevel']))
    if config['syslog']:
        logStdoutOrSyslog = logSyslog

    STATUS_EP = clientFromString(reactor, "tcp:cgate:20025")
    COMMAND_EP = clientFromString(reactor, "tcp:cgate:20023")

    application = service.MultiService()

    cgate_service = cgatemqtt.CGate(STATUS_EP, COMMAND_EP)
    cgate_service.setName('cgate')
    cgate_service.setServiceParent(application)

    mqtt_service = cgatemqtt.MQTTService(clientFromString(reactor, "tcp:mosquitto:1883"),
        MQTTFactory(profile=MQTTFactory.PUBLISHER | MQTTFactory.SUBSCRIBER))
    mqtt_service.setName('mqtt')
    mqtt_service.setServiceParent(application)

    cgate_service.setMqttService(mqtt_service)
    mqtt_service.setCGateService(cgate_service)

    return application

def FilteringLog():
    lo = FilteringLogObserver(observer=logStdoutOrSyslog, predicates=[logLevelFilterPredicate])
    return lo
