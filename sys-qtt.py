#!/usr/bin/env python3

import sys, time, yaml, json, signal, pathlib, argparse, schedule
import paho.mqtt.client as mqtt

from sysqtt.c_print import *
from sysqtt.utils import set_timezone
from sysqtt.sensors import SensorValues, APT_DISABLED
from sysqtt.sensor_object import SensorObject


poll_interval = 60
retry_time = 10
mqtt_client = None
device_name = None


SETTINGS = {}
SENSOR_JSON = 'sysqtt/sensor_base.json'
SENSOR_BASE = {}

sensor_list = []

sensors_dict = {}
disks_dict = {}
mounted_disks = []

connected = False
program_killed = False

class ProgramKilled(Exception):
    pass

def signal_handler(signum, frame):
    global program_killed
    program_killed = True
    raise ProgramKilled


def update_sensors():
    if not connected or program_killed:
        return None

    c_print('Sending update sensor payload...', status='wait')
    payload_size = 0
    failed_size = 0
    payload_str = f'{{'
    for sensor, attr in sensor_objects.items():
        if program_killed:
            break
        try:
            # Skip sensors that have been disabled or are missing
            if sensor in mounted_disks or (SETTINGS['sensors'][sensor] is not None and SETTINGS['sensors'][sensor] == True):
                payload_str += f'"{sensor}": "{attr["function"]()}",'
                payload_size += 1
        except Exception as e:
            c_print(f'Error while adding {text_color.B_HLIGHT}{sensor}{text_color.RESET} '
                f'to payload: {text_color.B_HLIGHT}{e}', tab=1, status='fail')
            failed_size += 1
    payload_str = payload_str[:-1]
    payload_str += f'}}'
    if failed_size > 0:
        c_print(f'{text_color.B_HLIGHT}{failed_size}{text_color.RESET} sensor '
        f'update{"s" if failed_size > 1 else ""} unable to be sent.', tab=1, status='fail')
    try:
        mqtt_client.publish(
            topic=f'sys-qtt/{attr["sensor_type"]}/{device_name}/state',
            payload=payload_str,
            qos=1,
            retain=False,)
    except Exception as e:
        c_print(f'Unable to publish payload {text_color.B_HLIGHT}{sensor}{text_color.RESET}: {text_color.B_HLIGHT}{e}', tab=1, status='fail')

    c_print(f'{text_color.B_HLIGHT}{payload_size}{text_color.RESET} sensor '
        f'update{"s" if payload_size > 1 else ""} sent to MQTT broker.', tab=1, status='ok')

    c_print(f'{text_color.B_HLIGHT}{poll_interval}{text_color.RESET} seconds until next update...', tab=1, status='wait')


def send_config_message(mqttClient):
    c_print('Publishing sensor configurations...', tab=1, status='wait')
    make = get_board_info('board_vendor')
    model = get_board_info('board_name')
    payload_size = 0
    for sensor, attr in sensor_objects.items():
        try:
            if sensor in mounted_disks or SETTINGS['sensors'][sensor]:
                mqttClient.publish(
                    topic=f'homeassistant/{attr["sensor_type"]}/{device_name}/{sensor}/config',
                    payload = (f'{{'
                            + (f'"device_class":"{attr["class"]}",' if 'class' in attr else '')
                            + f'"name":"{display_name} {attr["name"]}",'
                            + f'"state_topic":"sys-qtt/sensor/{device_name}/state",'
                            + (f'"unit_of_measurement":"{attr["unit"]}",' if 'unit' in attr else '')
                            + f'"value_template":"{{{{value_json.{sensor}}}}}",'
                            + f'"unique_id":"{device_name}_sensor_{sensor}",'
                            + f'"availability_topic":"sys-qtt/sensor/{device_name}/availability",'
                            + f'"device":{{"identifiers":["{device_name}_sensor"],'
                            + f'"name":"{display_name}","manufacturer":"{make}","model":"{model}"}}'
                            + (f',"icon":"mdi:{attr["icon"]}"' if 'icon' in attr else '')
                            + f'}}'
                            ),
                    qos=1,
                    retain=True,
                )
                payload_size += 1
                c_print(f'{sensor}: {text_color.B_HLIGHT}{attr["function"]()}', tab=2, status='ok')
        except Exception as e:
            c_print(f'Could not process {text_color.B_HLIGHT}{sensor}{text_color.RESET} sensor configuration: '
                    f'{text_color.B_HLIGHT}{e}', tab=2, status='warning')
        except ProgramKilled:
            pass
    mqttClient.publish(f'sys-qtt/sensor/{device_name}/availability', 'online', retain=True)
    c_print(f'{text_color.B_HLIGHT}{payload_size}{text_color.RESET} sensor config{"s" if payload_size > 1 else ""} '
            f'sent to MQTT broker.', tab=1, status='ok')


def _parser():
    default_settings_path = str(pathlib.Path(__file__).parent.resolve()) + '/settings.yaml'
    """Generate argument parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', help='path to the settings file', default=default_settings_path)
    return parser


def import_settings_yaml():
    """Use args to import settings.yaml"""
    try:
        args = _parser().parse_args()
        settings_file = args.settings
        with open(settings_file) as f:
            settings_yaml = yaml.safe_load(f)
        return settings_yaml
    except Exception as e:
        c_print(f'{text_color.B_HLIGHT}Could not find settings file. Please check the documentation: {e}', status='fail')
        print()
        sys.exit()


def initialise_settings(settings):
    default_settings = { 'broker_port': 1883, 'update_interval': 60, 'retry_time': 10 }
    required_settings = ['sensors', 'broker_host', 'broker_user', 'broker_pass', 'timezone', 'devicename', 'client_id']
    
    SETTINGS = settings

    # Check for missing required settings
    missing = [x for x in required_settings if x not in SETTINGS]
    if len(missing) > 0:
        for m in missing:
            c_print(f'{text_color.B_HLIGHT}{m}{text_color.RESET} not defined in settings file. '
                    f'Please check the documentation.', tab=1, status='fail')
        raise ProgramKilled

    # Apply defaults to missing settings
    for d, val in default_settings:
        if d not in SETTINGS:
            c_print(f'{text_color.B_HLIGHT}{d}{text_color.RESET} not defined in settings file. '
            f'Defaulting to {text_color.B_HLIGHT}{val}{text_color.RESET}.', tab=1, status='warning')
            SETTINGS[d] = val

    # Load sensor_base.json
    try:
        with open(SENSOR_JSON, 'r') as infile:
            json.load(SENSOR_BASE, infile)
    except Exception as e:
        c_print(f'{text_color.B_HLIGHT}{SENSOR_JSON}{text_color.RESET} does not exist and is required. '
        f'Please download Sys-QTT again.', tab=1, status='fail')
        raise ProgramKilled

    # Initial global config
    set_timezone(SETTINGS['timezone'])


def import_sensors():
    # Main sensor import    
    for sensor, toggle in SETTINGS['sensors']:
        if sensor not in SENSOR_BASE:
            c_print(f'{text_color.B_HLIGHT}{sensor}{text_color.RESET} missing from {text_color.B_HLIGHT}'
                    f'{SENSOR_JSON}{text_color.RESET}. Skipping.', tab=1, status='warning')
            continue
        if sensor != 'disk_mounted':
            if toggle == False:
                continue
            elif sensor in sensor_list:
                c_print(f'Multiple {text_color.B_HLIGHT}{sensor}{text_color.RESET} in settings.yaml {text_color.B_HLIGHT}'
                        f'{SENSOR_JSON}{text_color.RESET}. Ignoring duplicate.', tab=1, status='warning')
                continue
            else:
                sensor_list[sensor] = SensorObject(SENSOR_BASE[sensor])
        else: # Duplicating the code for mounted drive list isn't the neatest way, it'll do for now
            for drive in sensor:
                if drive in sensor_list:
                    c_print(f'Multiple {text_color.B_HLIGHT}{drive}{text_color.RESET} in settings.yaml {text_color.B_HLIGHT}'
                            f'{SENSOR_JSON}{text_color.RESET}. Ignoring duplicate.', tab=1, status='warning')
                    continue
                else:
                    sensor_list[drive] = SensorObject(SENSOR_BASE[drive], path=sensor[drive])
    
    c_print(f'Imported {text_color.B_HLIGHT}{len(sensor_list)}{text_color.RESET} sensors.', tab=1, status='ok')



def connect_to_broker():
    """Initiates connection with MQTT server and """
    while True:
        try:
            c_print(f'Attempting to reach MQTT broker at {text_color.B_HLIGHT}{SETTINGS["mqtt"]["hostname"]}{text_color.RESET} on port '
                f'{text_color.B_HLIGHT}{SETTINGS["mqtt"]["port"]}{text_color.RESET}...', status='wait')
            mqtt_client.connect(SETTINGS['mqtt']['hostname'], SETTINGS['mqtt']['port'])
            c_print(f'{text_color.B_OK}MQTT broker responded.', tab=1, status='ok')
            break
        except ConnectionRefusedError as e:
            c_print(f'MQTT broker is down or unreachable: {text_color.B_FAIL}{e}', tab=1, status='fail')
        except OSError as e:
            c_print(f'Network I/O error. Is the network down? {text_color.B_FAIL}{e}', tab=1, status='fail')
        except Exception as e:
            c_print(f'Terminating connection attempt: {e}', tab=1, status='fail')
        c_print(f'Trying again in {text_color.B_HLIGHT}{retry_time}{text_color.RESET} seconds...', tab=1, status='wait')
        time.sleep(retry_time)
    try:
        send_config_message(mqtt_client)
    except Exception as e:
        c_print(f'Error while sending config to MQTT broker: {text_color.B_FAIL}{e}', tab=1, status='fail')
        raise ProgramKilled

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        try:
            client.subscribe('hass/status')
            mqtt_client.publish(f'sys-qtt/sensor/{device_name}/availability', 'online', retain=True)
            c_print(f'{text_color.B_OK}Success!', tab=1, status='ok')
            c_print(f'Updated {text_color.B_HLIGHT}{device_name}{text_color.RESET} client on broker with {text_color.B_HLIGHT}online'
                    f'{text_color.RESET} status.', tab=1, status='info')
            global connected
            connected = True
        except Exception as e:
            c_print(f'Unable to publish {text_color.B_HLIGHT}online{text_color.RESET} status to broker: {text_color.B_FAIL}{e}', tab=1, status='fail')
    elif rc == 5:
        c_print('Authentication failed.', tab=1, status='fail')
        raise ProgramKilled
    else:
        c_print('Failed to connect.', tab=1, status='fail')

def on_disconnect(client, userdata, rc):
    global connected
    connected = False
    print()
    c_print(f'{text_color.B_FAIL}Disconnected!')
    if rc != 0:
        c_print('Unexpected MQTT disconnection. Will attempt to re-establish connection.', tab=1, status='warning')
    else:
        c_print(f'RC value: {text_color.B_HLIGHT}{rc}', tab=1, status='info')
    if not program_killed:
        print()
        connect_to_broker()

def on_message(client, userdata, message):
    c_print(f'Message received from broker: {text_color.B_HLIGHT}{message.payload.decode()}', status='info')
    if(message.payload.decode() == 'online'):
        send_config_message(client)

if __name__ == '__main__':
    try:
        print()
        c_print(f'{text_color.B_NOTICE}Sys-QTT starting...')
        print()

        import_settings_yaml()
        initialise_settings()


        c_print('Importing settings...', status='wait')
        # Make settings file keys all lowercase
        SETTINGS = {k.lower(): v for k,v in SETTINGS.items()}
        # Prep settings with defaults if keys missing
        SETTINGS = initialise_settings(SETTINGS)
        # Check for settings that will prevent the script from communicating with MQTT broker or break the script
        check_settings(SETTINGS)
        # Build list of external disks
        add_disks()

        device_name = SETTINGS['devicename'].replace(' ', '_').lower()
        display_name = SETTINGS['devicename']

        mqtt_client = mqtt.Client(client_id=SETTINGS['client_id'])

        # MQTT connection callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_message = on_message

        # set the client's availibilty will and user
        mqtt_client.will_set(f'sys-qtt/sensor/{device_name}/availability', 'offline', retain=True)
        if 'user' in SETTINGS['mqtt']:
            mqtt_client.username_pw_set(
                SETTINGS['mqtt']['user'], SETTINGS['mqtt']['password']
            )
        
        # For gracefully exiting
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        c_print(f'{text_color.B_OK}Local configuration complete.', tab=1, status='ok')

        # Initial connection to broker for pushing config
        connect_to_broker()

        # Start the MQTT loop to maintain connection
        c_print('Establishing MQTT connection loop...', status='wait')
        mqtt_client.loop_start()

        # Waits for connection before starting the scheduled update job
        while not connected:
            time.sleep(1)
        try:
            # Start the update job
            c_print(f'Adding {text_color.B_HLIGHT}sensor update{text_color.RESET} job on '
                    f'{text_color.B_HLIGHT}{poll_interval}{text_color.RESET} second schedule...', status='wait')
            job = schedule.every(poll_interval).seconds.do(update_sensors)
            c_print(f'{text_color.B_HLIGHT}{schedule.get_jobs()}', tab=1, status='ok')
        except Exception as e:
            c_print(f'Unable to add job: {text_color.B_FAIL}{e}', tab=1, status='fail')
            sys.exit()

        print()
        c_print(f'{text_color.B_HLIGHT}Sys-QTT running on {text_color.B_OK}{display_name}', status='ok')
        print()

        # Initial sensor update 
        update_sensors()

        while True:
            try:
                sys.stdout.flush()
                schedule.run_pending()
                time.sleep(1)
            except ProgramKilled:
                c_print(f'\n{text_color.B_FAIL}Program killed. Cleaning up...')
                schedule.cancel_job(job)
                mqtt_client.loop_stop()
                if mqtt_client.is_connected():
                    mqtt_client.publish(f'sys-qtt/sensor/{device_name}/availability', 'offline', retain=True)
                    mqtt_client.disconnect()
                print()
                c_print(f'{text_color.B_HLIGHT}Shutdown complete...')
                print()
                sys.stdout.flush()
                break
    except:
        print()
        c_print(f'{text_color.B_FAIL}Processed forced to exit.')
        print()