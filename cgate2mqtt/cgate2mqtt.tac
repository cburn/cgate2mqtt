import re
import sys

from twisted.application import service
from twisted.internet import reactor
from twisted.logger import Logger
from twisted.internet.endpoints import clientFromString
from twisted.application.internet import ClientService
from twisted.logger import LogLevel, ILogObserver, FilteringLogObserver, LogLevelFilterPredicate, textFileLogObserver
from txcgate.service import CGateService
import txcgate.command as command

from mqtt.client.factory import MQTTFactory

log = Logger(namespace='CGate2MQTT')
loglevel = LogLevel.info
filterlog = True

class CGate(CGateService):
    def setMqttService(self, mqtt):
        self.mqtt_service = mqtt
        def handleMessage(message):
            log.debug(str(message))
            if isinstance(message, command.Command):
                self.mqtt_service.publish("cbus/status/command", str(message))
                if message.level != None and message.address != None:
                    self.mqtt_service.publish(
                        'cbus/status/' + message.address.lstrip('/') + '/level',
                        str(message.level))
                    self.mqtt_service.publish(
                        'cbus/status/' + message.address.lstrip('/') + '/state',
                        '1' if message.level > 0 else '0')
            else:
                log.debug("Received unhandled command: {command}", command=message)

        self.setStatusMessageHandler(handleMessage)

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
        self.protocol.subscribe("cbus/set/#", 2 )
        self.protocol.subscribe("cbus/command", 2 )
        self.protocol.setPublishHandler(self.onPublish)

    def connectMqtt(self, protocol):
        self.protocol=protocol
        d = self.protocol.connect("CGate2Mqtt", willTopic="cbus/connected", willMessage="0", willQoS=2, willRetain=True)
        self.protocol.setWindowSize(16)
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
            d = self.protocol.publish(topic=topic, qos=2, message=message, retain=True)
            d.addErrback(self.printError)
        else:
            log.debug('Not connected to MQTT')

    def printError(self, *args):
        log.debug("args={args!s}", args=args)

    def onPublish(self, topic, payload, qos, dup, retain, msgId):
        if topic == 'cbus/command':
            self.cgate.send(payload)
        else: # cbus/set/HOME/254/56/1/level
            address = re.match('cbus/set/(.*)/level', topic)
            if address:
                if address.group(1).split('/')[2] in ('56'):
                    self.cgate.ramp('//' + address.group(1), payload)
                elif address.group(1).split('/')[2] in ('202'):
                    self.cgate.trigger_event('//' + address.group(1), payload)
            else:
                address = re.match('cbus/set/(.*)/state', topic)
                if address:
                    if address.group(1).split('/')[2] in ('56'):
                        if bool(int(payload)):
                            self.cgate.on('//' + address.group(1))
                        else:
                            self.cgate.off('//' + address.group(1))

STATUS_EP = clientFromString(reactor, "tcp:localhost:20025")
COMMAND_EP = clientFromString(reactor, "tcp:localhost:20023")

application = service.Application("cgate2mqtt")
service.IProcess(application).processName = "cgate2mqtt"
serviceCollection = service.IServiceCollection(application)

cgate_service = CGate(STATUS_EP, COMMAND_EP)
cgate_service.setName('cgate')
cgate_service.setServiceParent(serviceCollection)

mqtt_service = MQTTService(clientFromString(reactor, "tcp:localhost:1883"),
    MQTTFactory(profile=MQTTFactory.PUBLISHER | MQTTFactory.SUBSCRIBER))
mqtt_service.setName('mqtt')
mqtt_service.setServiceParent(serviceCollection)

cgate_service.setMqttService(mqtt_service)
mqtt_service.setCGateService(cgate_service)

if filterlog:
    isLevel = LogLevelFilterPredicate(loglevel)
    lo = FilteringLogObserver(observer=textFileLogObserver(sys.stdout), predicates=[isLevel])
    application.setComponent(ILogObserver, lo)
