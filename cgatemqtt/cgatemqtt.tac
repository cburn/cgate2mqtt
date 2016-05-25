import re

from twisted.application import service
from twisted.internet import reactor
from twisted.logger import Logger
from twisted.internet.endpoints import clientFromString
from twisted.application.internet import ClientService

from txcgate.service import CGateService
import txcgate.command as command

from mqtt.client.factory import MQTTFactory

log = Logger(namespace='CGateMQTT')


class CGate(CGateService):
    def setMqttService(self, mqtt):
        self.mqtt_service = mqtt
        def handleMessage(message):
            log.info(str(message))
            self.mqtt_service.publish("ha/cbus/raw/status", str(message))
            if message.level != None and message.address != None:
                self.mqtt_service.publish(
                    "ha/cbus/" + message.address.lstrip('/') + '/value',
                    str(message.level))

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
        self.whenConnected().addCallback(self.connect)

    def stopService(self):
        self.protocol.disconnect()
        ClientService.stopService(self)

    def subscribe(self, *args):
        self.protocol.subscribe("ha/cbus/#", 0 )
        self.protocol.setPublishHandler(self.onPublish)

    def connect(self, protocol):
        self.protocol = protocol
        d = self.protocol.connect("CGateMqtt")
        d.addCallback(self.subscribe)

        def retryConnect():
            self.whenConnected().addCallback(self.connect)

        def delayRetryConnect(reason):
            self.protocol = None
            reactor.callLater(1, retryConnect)

        self.protocol.setDisconnectCallback(delayRetryConnect)

    def publish(self, topic, message):
        d = self.protocol.publish(topic=topic, qos=1, message=message)
        d.addErrback(self.printError)

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


application = service.Application("cgatemqtt")
service.IProcess(application).processName = "cgatemqtt"
serviceCollection = service.IServiceCollection(application)

cgate_service = CGate()
cgate_service.setName('cgate')
cgate_service.setServiceParent(serviceCollection)

mqtt_service = MQTTService(clientFromString(reactor, "tcp:localhost:1883"),
    MQTTFactory(profile=MQTTFactory.PUBLISHER | MQTTFactory.SUBSCRIBER))
mqtt_service.setName('mqtt')
mqtt_service.setServiceParent(serviceCollection)

cgate_service.setMqttService(mqtt_service)
mqtt_service.setCGateService(cgate_service)
