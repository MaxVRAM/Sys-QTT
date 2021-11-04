from sysqtt.sensors import SensorValues

class SensorObject(object):
    display_name = ''
    device_name = display_name.replace(' ', '_').lower()

    mounted = False
    sensor_type = 'sensor'

    def __init__(self, details: dict, **kwargs) -> None:
        self.details = details
        self.details.type = 'sensor'
        if self.details['mounted'] == True:
            self.details['name'] = f'Disk {details.name}'
            self.details['path'] = kwargs['path']
        self.config = SensorObject.MqttConfig(self)

    def update():
        SensorValues.

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
            if 'topic' in kwargs:
                self.topic = kwargs['topic']
            else:
                self.topic = f'sys-qtt/{_details["sensor_type"]}/{SensorObject.device_name}/state',
            if 'payload' in kwargs:
                self.payload = kwargs['payload']
            else:
                self.payload = f'{{'
                f'"device_class":"{_details["class"]}",' if 'class' in _details else ''
                f'"name":"{SensorObject.display_name} {_details["name"]}",'
                f'"state_topic":"sys-qtt/sensor/{{SensorObject.device_name}}/state",'
                (f'"unit_of_measurement":"{_details["unit"]}",' if 'unit' in _details else '')
                f'"value_template":"{{{{value_json.{_details["name"]}}}}}",'
                f'"unique_id":"{SensorObject.device_name}_sensor_{_details["name"]}",'
                f'"availability_topic":"sys-qtt/sensor/{SensorObject.device_name}/availability",'
                f'"device":{{"identifiers":["{SensorObject.device_name}_sensor"],'
                f'"name":"{SensorObject.display_name}","manufacturer":"{_details["make"]}","model":"{self.details["model"]}"}}'
                (f',"icon":"mdi:{_details["icon"]}"' if 'icon' in _details else '')
                f'}}'