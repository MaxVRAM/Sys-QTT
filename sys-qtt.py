#!/usr/bin/env python3

import sys, time, yaml, json, signal, pathlib, argparse, schedule
import paho.mqtt.client as mqtt

from sysqtt.c_print import *
from sysqtt.utils import set_timezone
from sysqtt.sensors import SensorValues, APT_DISABLED
from sysqtt.sensor_object import SensorObject

MQTT_CLIENT = None
SETTINGS = {}
SENSOR_JSON = 'sysqtt/sensor_base.json'
SENSOR_DETAILS = {}
SENSOR_DICT = {}
VALUE_GENERATOR = SensorValues()

connected = False
program_killed = False


class ProgramKilled(Exception):
    pass

# Graceful exit handler
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
    # Payload construction
    payload_str = f'{{'
    for s in SENSOR_DICT:
        if program_killed:
            sys.exit()
        try:
            payload_str += f'"{s}": "{VALUE_GENERATOR.value(SENSOR_DICT[s])}",'
            payload_size += 1
        except Exception as e:
            c_print(f'Error while adding {text_color.B_HLIGHT}{s}{text_color.RESET} '
                f'to update payload: {text_color.B_FAIL}{e}', tab=1, status='fail')
            failed_size += 1
    payload_str = payload_str[:-1]
    payload_str += f'}}'

    # Report failed sensors
    if failed_size > 0:
        c_print(f'{text_color.B_HLIGHT}{failed_size}{text_color.RESET} sensor '
        f'update{"s" if failed_size > 1 else ""} unable to be sent.', tab=1, status='fail')

    # Now let's ship this sucker off!
    try:
        MQTT_CLIENT.publish(topic=f'sys-qtt/sensor/{SensorObject.device_name}/state',
            payload=payload_str, qos=1, retain=False)
    except Exception as e:
        c_print(f'Unable to publish update payload: {text_color.B_FAIL}{e}', tab=1, status='fail')

    c_print(f'{text_color.B_HLIGHT}{payload_size}{text_color.RESET} sensor '
        f'update{"s" if payload_size > 1 else ""} sent to MQTT broker.', tab=1, status='ok')
    c_print(f'{text_color.B_HLIGHT}{SETTINGS["update_interval"]}{text_color.RESET} seconds until next update...', tab=1, status='wait')


# Argument parser
def _parser():
    default_settings_path = str(pathlib.Path(__file__).parent.resolve()) + '/settings.yaml'
    """Generate argument parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', help='path to the settings file', default=default_settings_path)
    return parser


def import_settings_yaml():
    """Import settings.yaml either via supplied argument, or check in default location"""
    c_print('Importing settings.yaml...', status='wait')
    try:
        args = _parser().parse_args()
        settings_file = args.settings
        with open(settings_file) as f:
            settings_yaml = yaml.safe_load(f)
        c_print(f'Settings file found.', tab=1, status='ok')
        return settings_yaml
    except Exception as e:
        c_print(f'{text_color.B_HLIGHT}Could not find settings file. Please check the documentation: {e}', status='fail')
        print()
        sys.exit()


# Check that imported config is valid
def initialise_settings(settings) -> dict:
    c_print('Processing settings...', status='wait')
    default_settings = { 'broker_port': 1883, 'update_interval': 60, 'retry_time': 10 }
    required_settings = ['sensors', 'broker_host', 'broker_user', 'broker_pass', 'timezone', 'device_name', 'client_id']
    # Check for missing required settings
    if len(missing := [x for x in required_settings if x not in settings]) > 0:
        for m in missing:
            c_print(f'{text_color.B_HLIGHT}{m}{text_color.RESET} not defined in settings file. '
                    f'Please check the documentation.', tab=1, status='fail')
        raise ProgramKilled

    for d in default_settings:
        if d not in settings:
            c_print(f'{text_color.B_HLIGHT}{d}{text_color.RESET} not defined in settings file. '
            f'Defaulting to {text_color.B_HLIGHT}{default_settings[d]}{text_color.RESET}.', tab=1, status='warning')
            settings[d] = default_settings[d]

    c_print(f'Settings initialised.', tab=1, status='ok')
    c_print('Importing default sensor details...', status='wait', tab=1)
    global SENSOR_DETAILS
    detail_file = str(pathlib.Path(__file__).parent.resolve()) + '/sysqtt/sensor_details.json'
    try:
        with open(detail_file, 'r') as infile:
            SENSOR_DETAILS= json.load(infile)
    except Exception as e:
        c_print(f'Could not load {text_color.B_HLIGHT}{detail_file}{text_color.RESET}. Check if it exists. If not, '
        f'please download Sys-QTT again: {e}', tab=1, status='fail')
        raise ProgramKilled
    c_print(f'Sensor details loaded.', tab=2, status='ok')
    # Initial global config
    set_timezone(settings['timezone'])
    c_print(f'Settings applied successfully!', tab=1, status='ok')
    return settings


# Main sensor config import process
def import_sensors(sensor_dict: dict) -> dict:
    c_print('Importing sensor configurations...', status='wait')
    for s in SETTINGS['sensors']:
        if s not in SENSOR_DETAILS:
            c_print(f'{text_color.B_HLIGHT}{s}{text_color.RESET} missing from {text_color.B_HLIGHT}'
                    f'sensor details{text_color.RESET}. Skipping.', tab=1, status='warning')
            continue
        if s != 'disk_mounted':
            if SETTINGS['sensors'][s] == False:
                continue
            elif s in sensor_dict:
                c_print(f'Multiple {text_color.B_HLIGHT}{s}{text_color.RESET} in settings.yaml {text_color.B_HLIGHT}'
                        f'{SENSOR_JSON}{text_color.RESET}. Ignoring duplicate. Remove from config to stop this message.', tab=1, status='warning')
                continue
            else:
                try:
                    SENSOR_DETAILS[s]['name']=s
                    sensor_dict[s] = SensorObject(SENSOR_DETAILS[s])
                except Exception as e:
                    c_print(f'Unable add {text_color.B_HLIGHT}{s}{text_color.RESET} and has been removed '
                            f'from this session: {text_color.B_FAIL}{e}', tab=1, status='fail')
        else: # This isn't the neatest way, it'll do for now
            if SETTINGS['sensors'][s] is not None:
                drives = SETTINGS['sensors'][s]
                for d in drives:
                    drive_details = SENSOR_DETAILS[s]
                    if d in sensor_dict:
                        c_print(f'Multiple {text_color.B_HLIGHT}{d}{text_color.RESET} in settings.yaml {text_color.B_HLIGHT}'
                                f'{SENSOR_JSON}{text_color.RESET}. Ignoring duplicate. Remove from config to stop this message.', tab=1, status='warning')
                        continue
                    else:
                        try:
                            drive_details['name'] = f'disk_{d.replace(" ","_").lower()}'
                            sensor_dict[drive_details['name']] = SensorObject(drive_details, path=SETTINGS['sensors'][s][d])
                        except Exception as e:
                            c_print(f'Unable add {text_color.B_HLIGHT}{d}{text_color.RESET} and has been removed '
                                    f'from this session: {text_color.B_FAIL}{e}', tab=1, status='fail')

    c_print(f'Imported {text_color.B_HLIGHT}{len(sensor_dict)}{text_color.RESET} sensor details.', tab=1, status='ok')
    # Initialise static sensors and remove ones that fail to generate a value
    c_print(f'Initialising {text_color.B_HLIGHT}static{text_color.RESET} sensors...', tab=1, status='wait')
    failed_sensors = VALUE_GENERATOR.build_statics(sensor_dict)
    if len(failed_sensors) > 0:
        for f in failed_sensors:
            sensor_dict.pop(f)
        c_print(f'{text_color.B_HLIGHT}{len(failed_sensors)}{text_color.RESET} static sensors have been removed from this session. '
        f'Please check your config!', tab=2, status='warning')
    c_print(f'Static sensors built!', tab=2, status='ok')
    # Perform sensor value check on all sensor objects and remove ones that fail to generate a value
    c_print(f'Checking output of each sensor...', tab=1, status='wait')
    failed_sensors = {}
    for s in sensor_dict:
        if (value := VALUE_GENERATOR.value(sensor_dict[s])) is not None:
            c_print(f'{text_color.B_HLIGHT}{s}{text_color.RESET} returned: {text_color.B_HLIGHT}{value}', tab=2, status='ok')
        else:
            failed_sensors[s] = False
    if len(failed_sensors) > 0:
        for f in failed_sensors:
            #print(f'{f.details}')
            sensor_dict.pop(f)
        c_print(f'{text_color.B_HLIGHT}{len(failed_sensors)}{text_color.RESET} sensors have been removed from this session. '
        f'Please check your config!', tab=1, status='warning')
    # Return the new sensor list
    c_print(f'{text_color.B_HLIGHT}{len(sensor_dict)}{text_color.RESET} sensors have been commited to the session.', tab=1, status='ok')
    return sensor_dict


# Performed once the client has connected to the broker
def publish_sensor_configs(mqttClient):
    c_print('Publishing sensor configurations...', tab=1, status='wait')
    payload_size = 0
    for s in SENSOR_DICT:
        try:
            mqttClient.publish(topic=SENSOR_DICT[s].config.topic, payload=SENSOR_DICT[s].config.payload, qos=SENSOR_DICT[s].config.qos, retain=SENSOR_DICT[s].config.retain)
            payload_size += 1
            #print(f'{SENSOR_DICT[s].config.payload}')
        except Exception as e:
            c_print(f'Could not publish {text_color.B_HLIGHT}{SENSOR_DICT[s].details["name"]}{text_color.RESET} sensor configuration: '
                    f'{text_color.B_FAIL}{e}', tab=2, status='warning')
    mqttClient.publish(f'sys-qtt/sensor/{SensorObject.device_name}/availability', 'online', retain=True)
    c_print(f'{text_color.B_HLIGHT}{payload_size}{text_color.RESET} sensor config{"s" if payload_size != 1 else ""} '
            f'and {text_color.B_HLIGHT}online{text_color.RESET} status to broker.', tab=2, status='ok')


# Create a new client object
def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=SETTINGS['client_id'])
    # Add MQTT connection callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    # Set the client will and authentication
    client.will_set(f'sys-qtt/sensor/{SensorObject.device_name}/availability', 'offline', retain=True)
    client.username_pw_set(SETTINGS['broker_user'], SETTINGS['broker_pass'])
    return client

# Building the scheduler job for posting updates
def create_scheduled_job():
    try:
        # Start the update job
        c_print(f'Adding {text_color.B_HLIGHT}sensor update{text_color.RESET} job on '
                f'{text_color.B_HLIGHT}{SETTINGS["update_interval"]}{text_color.RESET} second schedule...', status='wait')
        job = schedule.every(SETTINGS["update_interval"]).seconds.do(update_sensors)
        c_print(f'{text_color.B_HLIGHT}{schedule.get_jobs()}', tab=1, status='ok')
        return job
    except Exception as e:
        c_print(f'Unable to add job: {text_color.B_FAIL}{e}', tab=1, status='fail')
        sys.exit()
        

### TODO - ADD RETRY NUMBER IN SETTINGS.YAML
def connect_to_broker():
    """Initiates connection with MQTT server """
    while True:
        try:
            c_print(f'Attempting to reach MQTT broker at {text_color.B_HLIGHT}{SETTINGS["broker_host"]}{text_color.RESET} on port '
                f'{text_color.B_HLIGHT}{SETTINGS["broker_port"]}{text_color.RESET}...', status='wait')
            MQTT_CLIENT.connect(SETTINGS['broker_host'], SETTINGS['broker_port'])
            c_print(f'{text_color.B_OK}MQTT broker responded.', tab=1, status='ok')
            break
        except ConnectionRefusedError as e:
            c_print(f'MQTT broker is down or unreachable: {text_color.B_FAIL}{e}', tab=1, status='fail')
        except OSError as e:
            c_print(f'Network I/O error. Is the network down? {text_color.B_FAIL}{e}', tab=1, status='fail')
        except Exception as e:
            c_print(f'Terminating connection attempt: {text_color.B_FAIL}{e}', tab=1, status='fail')
        c_print(f'Trying again in {text_color.B_HLIGHT}{SETTINGS["retry_time"]}{text_color.RESET} seconds...', tab=1, status='wait')
        time.sleep(SETTINGS["retry_time"])
    try:
        publish_sensor_configs(MQTT_CLIENT)
    except Exception as e:
        c_print(f'Unable to publish sensor config: {text_color.B_FAIL}{e}', tab=1, status='fail')
        raise ProgramKilled


# MQTT client callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        try:
            client.subscribe('hass/status')
            client.publish(f'sys-qtt/sensor/{SensorObject.device_name}/availability', 'online', retain=True)
            c_print(f'{text_color.B_OK}Success!', tab=1, status='ok')
            c_print(f'Updated {text_color.B_HLIGHT}{SensorObject.device_name}{text_color.RESET} client on broker with {text_color.B_HLIGHT}online'
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
        publish_sensor_configs(client)





if __name__ == '__main__':
    try:
        print()
        c_print(f'{text_color.B_NOTICE}Sys-QTT starting...')
        print()

        # Build global configurations
        SETTINGS = import_settings_yaml()
        SETTINGS = initialise_settings(SETTINGS)
        SensorObject.display_name = SETTINGS['device_name']
        SensorObject.device_name = SETTINGS['device_name'].replace(' ', '_').lower()
        SENSOR_DICT = import_sensors(SENSOR_DICT)
        MQTT_CLIENT = create_mqtt_client()
        c_print(f'{text_color.B_OK}Local configuration complete.', tab=1, status='ok')
        
        # Add handlers for gracefully exiting
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        # Initial connection to broker for pushing config
        connect_to_broker()
        # Start the MQTT loop to maintain connection
        c_print('Establishing MQTT connection loop...', status='wait')
        MQTT_CLIENT.loop_start()

        # Wait for connection before starting the scheduled update job
        while not connected:
            time.sleep(1)

        JOB = create_scheduled_job()

        print()
        string_end = ''.join(['-' for _ in range(len(SensorObject.display_name))])
        c_print('-------------------' + string_end, tab=1)
        c_print(f'{text_color.B_HLIGHT}Sys-QTT {text_color.RESET}running on {text_color.B_OK}{SensorObject.display_name}', tab=1)
        c_print('-------------------' + string_end, tab=1)
        print()

        time.sleep(1)

        # Publish inital sensor values
        update_sensors()

        # Program loop
        while True:
            try:
                sys.stdout.flush()
                schedule.run_pending()
                time.sleep(1)
            except ProgramKilled:
                c_print(f'\n{text_color.B_FAIL}Program killed. Cleaning up...')
                schedule.cancel_job(JOB)
                MQTT_CLIENT.loop_stop()
                if MQTT_CLIENT.is_connected():
                    MQTT_CLIENT.publish(f'sys-qtt/sensor/{SensorObject.device_name}/availability', 'offline', retain=True)
                    MQTT_CLIENT.disconnect()
                print()
                c_print(f'{text_color.B_HLIGHT}Shutdown complete...')
                print()
                sys.stdout.flush()
                break
    except Exception as e:
        print()
        c_print(f'{text_color.B_FAIL}Processed forced to exit: {e}')
        print()