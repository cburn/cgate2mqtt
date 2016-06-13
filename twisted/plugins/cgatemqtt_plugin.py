from twisted.application.service import ServiceMaker

cgatemqtt = ServiceMaker('cgatemqtt', 'cgatemqtt.tap', 'Run a CGate to MQTT bridge', 'cgatemqtt')
