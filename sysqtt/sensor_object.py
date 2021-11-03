
def external_disk_object(disk, path) -> dict:
    return {
        'name': f'Disk {disk}',
        'unit': '%',
        'icon': 'harddisk'
        }


class SensorObject(object):
    display_name = ''
    device_name = display_name.replace(' ', '_').lower()

    sensor_type = 'sensor'

    def __init__(self, details: dict, **kwargs) -> None:
        self.details = details
        self.details.type = 'sensor'
        self.details.mounted = True if 'path' in kwargs else False

        self.config = SensorObject.MqttConfig(self)

    class MqttConfig(object):
        sensor_object = None
        topic = ''
        qos = 1
        retain = True
        payload = {
            'name':'',
            'icon':'',
            'unique_id':'',
            'state_topic':'',
            'device_class':'',
            'unit_of_measurement':'',
            'value_template':'',
            'availability_topic':'',
            'device': {
                'identifiers':[],
                'name':'',
                'manufacturer':'',
                'model':''
            }
        }

        def __init__(self, sensor_object: object, **kwargs) -> None:
            self.sensor_object = sensor_object
            self.topic = kwargs['topic'] if 'topic' in kwargs else self.topic
            self.qos = kwargs['qos'] if 'qos' in kwargs else self.qos
            self.retain = kwargs['retain'] if 'retain' in kwargs else self.retain
            self.payload = kwargs['payload'] if 'payload' in kwargs else self.payload
