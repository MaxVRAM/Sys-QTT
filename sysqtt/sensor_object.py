from sysqtt.sensor_values import get_board_info

# The Sensor object stores sensor properties and MQTT config for each sensor for the current session
class SensorObject(object):
    make = get_board_info('board_vendor')
    model = get_board_info('board_name')
    display_name = ''
    device_name = ''
    def __init__(self, properties: dict, **kwargs) -> None:
        # Add properties provided and assume 'sensor' type
        self.properties = properties
        self.properties['type'] = 'sensor'
        # Create a MQTT config for this sensor
        self.config = SensorObject.MqttConfig(self)
        # Define a counter to track failed value calls
        self.failed_count = 0
        
    class MqttConfig(object):
        sensor_object = None
        topic = ''
        qos = 1
        retain = True
        def __init__(self, s_obj: object, **kwargs) -> None:
            self.sensor_object = s_obj
            self.qos = kwargs['qos'] if 'qos' in kwargs else self.qos
            self.retain = kwargs['retain'] if 'retain' in kwargs else self.retain
            _properties = self.sensor_object.properties
            # Topic in kwargs will override auto generated ones
            if 'topic' in kwargs:
                self.topic = kwargs['topic']
            else:
                self.topic = f'homeassistant/sensor/{SensorObject.device_name}/{_properties["name"]}/config'
            # Payload in kwargs will override auto generated ones
            if 'payload' in kwargs:
                self.payload = kwargs['payload']
            else:
                self.payload = (f'{{'
                + (f'"device_class":"{_properties["class"]}",' if 'class' in _properties else '')
                + f'"name":"{SensorObject.display_name} {_properties["title"]}",'
                + f'"state_topic":"sys-qtt/sensor/{SensorObject.device_name}/state",'
                + (f'"unit_of_measurement":"{_properties["unit"]}",' if 'unit' in _properties else '')
                + f'"value_template":"{{{{value_json.{_properties["name"]}}}}}",'
                + f'"unique_id":"{SensorObject.device_name}_sensor_{_properties["name"]}",'
                + f'"availability_topic":"sys-qtt/sensor/{SensorObject.device_name}/availability",'
                + f'"device":{{"identifiers":["{SensorObject.device_name}_sensor"],'
                + f'"name":"{SensorObject.display_name}","manufacturer":"{SensorObject.make}","model":"{SensorObject.model}"}}'
                + (f',"icon":"mdi:{_properties["icon"]}"' if 'icon' in _properties else '')
                + f'}}'
                )