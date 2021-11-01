#!/usr/bin/env python3

import sys, time, yaml, signal, pathlib, argparse, schedule
import paho.mqtt.client as mqtt
from os import path
from sysqtt.sensors import * 


poll_interval = 60
connection_retry = 10
mqtt_client = None
device_name = None
settings_dict = {}
sensors_dict = {}
drives_dict = {}
external_drives = []

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
    c_print('Sending sensor payload...', status='wait')
    payload_size = 0
    failed_size = 0
    payload_str = f'{{'
    for sensor, attr in sensor_objects.items():
        if program_killed:
            break
        try:
            # Skip sensors that have been disabled or are missing
            if sensor in external_drives or (settings_dict['sensors'][sensor] is not None and settings_dict['sensors'][sensor] == True):
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
    payload_size = 0
    for sensor, attr in sensor_objects.items():
        try:
            if sensor in external_drives or settings_dict['sensors'][sensor]:
                mqttClient.publish(
                    topic=f'homeassistant/{attr["sensor_type"]}/{device_name}/{sensor}/config',
                    payload = (f'{{'
                            + (f'"device_class":"{attr["class"]}",' if 'class' in attr else '')
                            + f'"name":"{deviceNameDisplay} {attr["name"]}",'
                            + f'"state_topic":"sys-qtt/sensor/{device_name}/state",'
                            + (f'"unit_of_measurement":"{attr["unit"]}",' if 'unit' in attr else '')
                            + f'"value_template":"{{{{value_json.{sensor}}}}}",'
                            + f'"unique_id":"{device_name}_sensor_{sensor}",'
                            + f'"availability_topic":"sys-qtt/sensor/{device_name}/availability",'
                            + f'"device":{{"identifiers":["{device_name}_sensor"],'
                            + f'"name":"{deviceNameDisplay} Sensors","model":"{system_board["model"]}", "manufacturer":"{system_board["make"]}"}}'
                            + (f',"icon":"mdi:{attr["icon"]}"' if 'icon' in attr else '')
                            + f'}}'
                            ),
                    qos=1,
                    retain=True,
                )
                payload_size += 1
                c_print(f'{sensor}: {text_color.B_HLIGHT}{attr["function"]()}', tab=2, status='ok')
        except Exception as e:
            c_print(f'Could not process {text_color.B_HLIGHT}{sensor}{text_color.RESET} sensor configuration: {text_color.B_HLIGHT}{e}', tab=2, status='warning')
        except ProgramKilled:
            pass
    mqttClient.publish(f'sys-qtt/sensor/{device_name}/availability', 'online', retain=True)
    c_print(f'{text_color.B_HLIGHT}{payload_size}{text_color.RESET} sensor config{"s" if payload_size > 1 else ""} sent to MQTT broker.', tab=1, status='ok')

def _parser():
    default_settings_path = str(pathlib.Path(__file__).parent.resolve()) + '/settings.yaml'
    """Generate argument parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings', help='path to the settings file', default=default_settings_path)
    return parser

def set_defaults(settings):
    missing_sensors = []
    set_default_timezone(pytz.timezone(settings['timezone']))
    
    # Missing non-essential settings
    global poll_interval
    if 'update_interval' in settings:
        poll_interval = settings['update_interval']
    else:
        c_print(f'{text_color.B_HLIGHT}update_interval{text_color.RESET} not defined in settings file. '
        f'Setting to default value of {text_color.B_HLIGHT}{poll_interval}{text_color.RESET} seconds.', tab=1, status='warning')

    global connection_retry
    if 'connection_retry' in settings['mqtt']:
        connection_retry = settings['mqtt']['connection_retry']
    else:
        c_print(f'{text_color.B_HLIGHT}connection_retry{text_color.RESET} not defined in mqtt settings. '
        f'Setting to default value of {text_color.B_HLIGHT}{connection_retry}{text_color.RESET} seconds.', tab=1, status='warning')

    if 'port' not in settings['mqtt']:
        c_print(f'{text_color.B_HLIGHT}port{text_color.RESET} not defined in settings file. '
        f'Setting to default value of {text_color.B_HLIGHT}1883{text_color.RESET}.', tab=1, status='warning')
        settings['mqtt']['port'] = 1883

    # Validate sensor entries
    if 'sensors' not in settings or settings['sensors'] is None:
        c_print(f'{text_color.B_FAIL}No sensors defined in settings file!', tab=1, status='warning')
        # Add all sensors to default-add list and define sensor config as an empty dictionary
        missing_sensors = sensor_objects
        settings['sensors'] = {}
    else:
        # Add individual sensors if they are missing from the config
        for sensor in sensor_objects:
            if sensor not in settings['sensors'] or type(settings['sensors'][sensor]) is not bool:
                missing_sensors.append(sensor)
    # Print missing sensor
    if len(missing_sensors) > 0:
        sensors_to_add = ' '.join(missing_sensors)
        c_print(f'{text_color.B_HLIGHT}{len(missing_sensors)}{text_color.RESET} sensor(s) not defined as true/false in settings file. Added them to the session by default:', tab=1, status='warning')
        c_print(f'{text_color.B_HLIGHT}{sensors_to_add}', tab=2)
        for sensor in missing_sensors:
            settings['sensors'][sensor] = True

    # Validate drive entries
    if 'external_drives' not in settings['sensors'] or settings['sensors']['external_drives'] is None:
        settings['sensors']['external_drives'] = {}
    else:
        for drive in settings['sensors']['external_drives']:
            if drive is None or len(drive) == 0:
                c_print(f'{text_color.B_HLIGHT}{drive}{text_color.RESET} needs to be a valid path. Ignoring entry.', tab=2)
    return settings

def check_settings(settings):
    # Abort if required settings missing
    settings_list = ['mqtt', 'timezone', 'devicename', 'client_id', 'sensors']
    mqtt_list = ['hostname', 'user', 'password']
    for s in settings_list:
        if s not in settings:
            c_print(f'{text_color.B_HLIGHT}{s}{text_color.RESET} not defined in settings file. Please check the documentation.', tab=1, status='fail')
            raise ProgramKilled
        elif s == 'mqtt':
            for m in mqtt_list:
                if m not in settings['mqtt']:
                    c_print(f'{text_color.B_HLIGHT}{m}{text_color.RESET} not defined in MQTT connection settings. Please check the documentation.', tab=1, status='fail')
                    raise ProgramKilled

    # Warnings for missing or incompatible modules
    if 'power_status' in settings['sensors'] and settings['sensors']['power_status'] and rpi_power_disabled:
        c_print(f'{text_color.B_HLIGHT}power_status{text_color.RESET} sensor only valid on Raspberry Pi hosts, removing from session. Set sensor as "false" to suppress warning.', tab=1, status='warning')
        settings['sensors']['power_status'] = False
    if 'updates' in settings['sensors'] and apt_disabled:
        c_print(f'Unable to import {text_color.B_HLIGHT}apt{text_color.RESET} module. removing from session.', tab=1, status='warning')
        settings['sensors']['updates'] = False

def add_drives():
    drives_dict = settings_dict['sensors']['external_drives']
    if drives_dict is not None and len(drives_dict) != 0:
        for drive in drives_dict:
            if drive is not None and drives_dict[drive] is not None:
                try:
                    usage = get_disk_usage(drives_dict[drive])
                    if usage:
                        sensor_objects[f'disk_use_{drive.lower()}'] = external_drive_base(drive, drives_dict[drive])
                        # Add drive to list with formatted name, for when checking sensors against settings items
                        external_drives.append(f'disk_use_{drive.lower()}')
                except Exception as e:
                    c_print(f'Error while attempting to get usage from drive entry {text_color.B_HLIGHT}{drive}{text_color.RESET} with path {text_color.B_HLIGHT}{drives_dict[drive]}{text_color.RESET}. Check settings file.', tab=1, status='warning')

            else:
                # Skip drives not found. Could be worth sending "not mounted" as the value if users want to track mount status.
                c_print(f'Drive {text_color.B_HLIGHT}{drive}{text_color.RESET} is empty. Check settings file.', tab=1, status='warning')

def connect_to_broker():
    while True:
        try:
            c_print(f'Attempting to reach MQTT broker at {text_color.B_HLIGHT}{settings_dict["mqtt"]["hostname"]}{text_color.RESET} on port '
                f'{text_color.B_HLIGHT}{settings_dict["mqtt"]["port"]}{text_color.RESET}...', status='wait')
            mqtt_client.connect(settings_dict['mqtt']['hostname'], settings_dict['mqtt']['port'])
            c_print(f'{text_color.B_OK}MQTT broker responded.', tab=1, status='ok')
            break
        except ConnectionRefusedError as e:
            c_print(f'MQTT broker is down or unreachable: {text_color.B_FAIL}{e}', tab=1, status='fail')
        except OSError as e:
            c_print(f'Network I/O error. Is the network down? {text_color.B_FAIL}{e}', tab=1, status='fail')
        except Exception as e:
            c_print(f'Terminating connection attempt: {e}', tab=1, status='fail')
        c_print(f'Trying again in {text_color.B_HLIGHT}{connection_retry}{text_color.RESET} seconds...', tab=1, status='wait')
        time.sleep(connection_retry)
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
            c_print(f'Updated {text_color.B_HLIGHT}{device_name}{text_color.RESET} client on broker with {text_color.B_HLIGHT}online{text_color.RESET} status.', tab=1, status='info')
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
        c_print(f'{text_color.B_NOTICE}System Sensors starting...')
        print()
        # Find settings.yaml
        try:
            args = _parser().parse_args()
            settings_file = args.settings
            with open(settings_file) as f:
                settings_dict = yaml.safe_load(f)
        except Exception as e:
            c_print(f'{text_color.B_HLIGHT}Could not find settings file. Please check the documentation: {e}', status='fail')
            print()
            sys.exit()


        c_print('Importing settings...', status='wait')
        # Make settings file keys all lowercase
        settings_dict = {k.lower(): v for k,v in settings_dict.items()}
        # Prep settings with defaults if keys missing
        settings_dict = set_defaults(settings_dict)
        # Check for settings that will prevent the script from communicating with MQTT broker or break the script
        check_settings(settings_dict)
        # Build list of external drives
        add_drives()

        device_name = settings_dict['devicename'].replace(' ', '_').lower()
        deviceNameDisplay = settings_dict['devicename']

        mqtt_client = mqtt.Client(client_id=settings_dict['client_id'])

        # MQTT connection callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_message = on_message

        # set the client's availibilty will and user
        mqtt_client.will_set(f'sys-qtt/sensor/{device_name}/availability', 'offline', retain=True)
        if 'user' in settings_dict['mqtt']:
            mqtt_client.username_pw_set(
                settings_dict['mqtt']['user'], settings_dict['mqtt']['password']
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
            c_print(f'Adding {text_color.B_HLIGHT}sensor update{text_color.RESET} job on {text_color.B_HLIGHT}{poll_interval}{text_color.RESET} second schedule...', status='wait')
            job = schedule.every(poll_interval).seconds.do(update_sensors)
            c_print(f'{text_color.B_HLIGHT}{schedule.get_jobs()}', tab=1, status='ok')
        except Exception as e:
            c_print(f'Unable to add job: {text_color.B_FAIL}{e}', tab=1, status='fail')
            sys.exit()

        print()
        c_print(f'{text_color.B_HLIGHT}Sys-QTT running on {text_color.B_OK}{deviceNameDisplay}', status='ok')
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