from twisted.python import usage
from twisted.application import service
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString
from twisted.logger import LogLevel, FilteringLogObserver, textFileLogObserver, LogLevelFilterPredicate
from mqtt.client.factory import MQTTFactory
import cgatemqtt

import sys


class Options(usage.Options):
    optParameters = [
        ['loglevel', 'l', 'info']
    ]

def makeService(config):
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
    config = Options()
    config.parseOptions()

    isLevel = LogLevelFilterPredicate(LogLevel.levelWithName(config['loglevel']))
    lo = FilteringLogObserver(observer=textFileLogObserver(sys.stdout), predicates=[isLevel])
    return lo
