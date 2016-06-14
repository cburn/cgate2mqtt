import re
import sys

from twisted.application import service
from twisted.internet import reactor
from twisted.logger import Logger
from twisted.internet.endpoints import clientFromString
from twisted.application.internet import ClientService
from twisted.logger import LogLevel, ILogObserver, FilteringLogObserver, LogLevelFilterPredicate, LegacyLogObserverWrapper
from twisted.python import syslog
from txcgate.service import CGateService
import txcgate.command as command

from mqtt.client.factory import MQTTFactory

log = Logger(namespace='CGateMQTT')
loglevel = LogLevel.info
filterlog = True

class CGate(CGateService):
    def setMqttService(self, mqtt):
        self.mqtt_service = mqtt
        def handleMessage(message):
            log.debug(str(message))
            if isinstance(message, command.Command):
                self.mqtt_service.publish("ha/cbus/raw/status", str(message))
                if message.level != None and message.address != None:
                    self.mqtt_service.publish(
                        'ha/cbus/' + message.address.lstrip('/') + '/value',
                        str(message.level))
            else:
                log.debug("Received unhandled command: {command}", command=message)

        self.setMessageHandler(handleMessage)


class MQTTService(ClientService):
    def __init__(self, *args, **kwargs):
        self.protocol = None
        self.cgate = None

        ClientService.__init__(self, *args, **kwargs)

    def setCGateService(self, cgate):
        self.cgate = service.IService(cgate)

    def startService(self):
        ClientService.startService(self)
        self.whenConnected().addCallback(self.connectMqtt)

    def stopService(self):
        self.protocol.disconnect()
        ClientService.stopService(self)

    def subscribe(self, *args):
        self.protocol.subscribe("ha/cbus/#", 1 )
        self.protocol.setPublishHandler(self.onPublish)

    def connectMqtt(self, protocol):
        self.protocol=protocol
        d = self.protocol.connect("CGateMqtt")
        self.protocol.publisher.setWindowSize(16)
        self.protocol.subscriber.setWindowSize(16)
        d.addCallback(self.subscribe)

        def retryConnect():
            self.whenConnected().addCallback(self.connectMqtt)

        def delayRetryConnect(reason):
            log.debug("Disconnected {reason}", reason=reason)
            self.protocol = None
            reactor.callLater(1, retryConnect)

        self.protocol.setDisconnectCallback(delayRetryConnect)

    def publish(self, topic, message):
        if self.protocol:
            d = self.protocol.publish(topic=topic, qos=1, message=message, retain=True)
            d.addErrback(self.printError)
        else:
            info.debug('Not connected to MQTT')

    def printError(self, *args):
        log.debug("args={args!s}", args=args)

    def onPublish(self, topic, payload, qos, dup, retain, msgId):
        if topic == 'ha/cbus/raw/command':
            self.cgate.send(payload)
        else:
            address = re.match('ha/cbus/(.*)/value/set', topic)
            if address:
                if address.group(1).split('/')[2] in ('56'):
                    self.cgate.send('RAMP //{address} {level}'.format(address=address.group(1), level=payload))

STATUS_EP = clientFromString(reactor, "tcp:cgate:20025")
COMMAND_EP = clientFromString(reactor, "tcp:cgate:20023")

application = service.Application("cgatemqtt")
service.IProcess(application).processName = "cgatemqtt"
serviceCollection = service.IServiceCollection(application)

cgate_service = CGate(STATUS_EP, COMMAND_EP)
cgate_service.setName('cgate')
cgate_service.setServiceParent(serviceCollection)

mqtt_service = MQTTService(clientFromString(reactor, "tcp:mosquitto:1883"),
    MQTTFactory(profile=MQTTFactory.PUBLISHER | MQTTFactory.SUBSCRIBER))
mqtt_service.setName('mqtt')
mqtt_service.setServiceParent(serviceCollection)

cgate_service.setMqttService(mqtt_service)
mqtt_service.setCGateService(cgate_service)

if filterlog:
    isLevel = LogLevelFilterPredicate(loglevel)
    lo = FilteringLogObserver(observer=LegacyLogObserverWrapper(syslog.SyslogObserver('cgatemqqt').emit), predicates=[isLevel])
    application.setComponent(ILogObserver, lo)
