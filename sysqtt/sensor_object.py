from sysqtt.sensors import get_board_info
from sysqtt.c_print import *

class SensorObject(object):
    make = get_board_info('board_vendor')
    model = get_board_info('board_name')

    display_name = ''
    device_name = ''

    def __init__(self, details: dict, **kwargs) -> None:
        self.details = details
        self.details['type'] = 'sensor'
        # Assume dynamic value if no static keyword in config
        if 'static' not in self.details:
            self.details['static'] = False
        # Detect mounted drive path objects
        if 'path' in kwargs:
            self.details['title'] = f'Disk {details["title"]}'
            self.details['path'] = kwargs['path']
            self.details['mounted'] = True
        else:
            self.details['mounted'] = False
        # Create a MQTT config for the new sensor object
        self.config = SensorObject.MqttConfig(self)

    class MqttConfig(object):
        sensor_object = None
        topic = ''
        qos = 1
        retain = True
        
        def __init__(self, s_obj: object, **kwargs) -> None:
            self.sensor_object = s_obj
            self.qos = kwargs['qos'] if 'qos' in kwargs else self.qos
            self.retain = kwargs['retain'] if 'retain' in kwargs else self.retain
            _details = self.sensor_object.details
            # Topic in kwargs will override auto generated ones
            if 'topic' in kwargs:
                self.topic = kwargs['topic']
            else:
                self.topic = f'homeassistant/sensor/{SensorObject.device_name}/{_details["name"]}/config'

            # Payload in kwargs will override auto generated ones
            if 'payload' in kwargs:
                self.payload = kwargs['payload']
            else:
                self.payload = (f'{{'
                + (f'"device_class":"{_details["class"]}",' if 'class' in _details else '')
                + f'"name":"{SensorObject.display_name} {_details["title"]}",'
                + f'"state_topic":"sys-qtt/sensor/{SensorObject.device_name}/state",'
                + (f'"unit_of_measurement":"{_details["unit"]}",' if 'unit' in _details else '')
                + f'"value_template":"{{{{value_json.{_details["name"]}}}}}",'
                + f'"unique_id":"{SensorObject.device_name}_sensor_{_details["name"]}",'
                + f'"availability_topic":"sys-qtt/sensor/{SensorObject.device_name}/availability",'
                + f'"device":{{"identifiers":["{SensorObject.device_name}_sensor"],'
                + f'"name":"{SensorObject.display_name}","manufacturer":"{SensorObject.make}","model":"{SensorObject.model}"}}'
                + (f',"icon":"mdi:{_details["icon"]}"' if 'icon' in _details else '')
                + f'}}'
                )