from sysqtt.sensor_values import get_board_info


# The Sensor object stores sensor properties and
# MQTT config for each sensor for the current session
class SensorObject(object):
    make = get_board_info('board_vendor')
    model = get_board_info('board_name')
    display_name = ''
    device_name = ''

    def __init__(self, properties: dict, **kwargs) -> None:
        self.properties = properties
        self.properties['type'] = 'sensor'
        self.config = SensorObject.MqttConfig(self)
        self.failed_count = 0

    class MqttConfig(object):
        parent = None
        topic = ''
        qos = 1
        retain = True

        def __init__(self, s_obj: object, **kwargs) -> None:
            self.parent = s_obj
            self.qos = kwargs.get('qos', self.qos)
            self.retain = kwargs.get('retain', self.retain)
            props = self.parent.properties
            so = SensorObject
            # Topic in kwargs will override auto generated ones
            if 'topic' in kwargs:
                self.topic = kwargs['topic']
            else:
                self.topic = f'homeassistant/sensor/{so.device_name}\
                    /{props["name"]}/config'
            # Payload in kwargs will override auto generated ones
            if 'payload' in kwargs:
                self.payload = kwargs['payload']
                return
            self.payload = (
                '{{'
                + (f'"device_class":"{props["class"]}",' if 'class' in props else '')
                + f'"name":"{so.display_name} {props["title"]}",'
                + f'"state_topic":"sys-qtt/sensor/{so.device_name}/state",'
                + (f'"unit_of_measurement":"{props["unit"]}",' if 'unit' in props else '')
                + f'"value_template":"{{{{value_json.{props["name"]}}}}}",'
                + f'"unique_id":"{so.device_name}_sensor_{props["name"]}",'
                + f'"availability_topic":"sys-qtt/sensor/{so.device_name}/availability",'
                + f'"device":{{"identifiers":["{so.device_name}_sensor"],'
                + f'"name":"{so.display_name}",'
                + f'"manufacturer":"{so.make}","model":"{so.model}"}}'
                + (f',"icon":"mdi:{props["icon"]}"' if 'icon' in props else '')
                + '}}'
            )
