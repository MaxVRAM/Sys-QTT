# ------------------------------------------------------------------
#    _________                      ______________________________
#   /   _____/__.__. ______         \_____  \__    ___/\__    ___/
#   \_____  <   |  |/  ___/     _____/  / \  \|    |     |    |
#   /        \___  |\___ \ |Sys-QTT|/   \_/.  \    |     |    |
#  /_______  / ____/____  >"``      \_____\ \_/____|     |____|
#          \/\/         \/                 \__>      o
#                                       System Metrics MQTT Client
#
#              https://github.com/MaxVRAM/Sys-QTT
#
#    Sys-QTT is based on Sennevds 'System Sensors' project:
#          https://github.com/Sennevds/system_sensors
#
# ------------------------------------------------------------------


from os import path
import sys
import time
import yaml
import json
import signal
import pathlib
import argparse
import schedule
import paho.mqtt.client as mqtt

# Sys-QTT project modules
from sysqtt.c_print import col, c_print, c_title
from sysqtt.utils import set_timezone
from sysqtt.sensor_values import SensorValues
from sysqtt.sensor_object import SensorObject

MQTT_CLIENT = None

CONFIG_FILE = 'config.yaml'
CONFIG_PATH = f'{str(pathlib.Path(__file__).parent.resolve())}/{CONFIG_FILE}'
CONFIG = {}

PROPS_FILE = 'sensor_properties.json'
PROPS_PATH = f'{str(pathlib.Path(__file__).parent.resolve())}/sysqtt/{PROPS_FILE}'
PROPERTIES = {}
SENSOR_DICT = {}

VALUE_GENERATOR = SensorValues()

connected = False
program_killed = False


class ProgramKilled(Exception):
    '''Placeholder application exit exception'''
    pass


def signal_handler(signum, frame):
    '''Signal callback'''
    global program_killed
    program_killed = True
    raise ProgramKilled


def publish_sensor_values():
    '''Method responsible for pushing sensor values to MQTT broker'''
    if not connected or program_killed:
        return None
    c_print('Sending update sensor payload...', status='wait')
    payload_size = 0
    failed_size = 0
    # Payload construction
    payload_str = '{{'
    for s in SENSOR_DICT:
        try:
            payload_str += f'"{s}": "{VALUE_GENERATOR.value(SENSOR_DICT[s])}",'
            payload_size += 1
        except Exception as e:
            c_print(f'Error while adding {col.B_HLT}{s}{col.RESET} '
                    f'to update payload: {col.B_FAIL}{e}', tab=1, status='fail')
            failed_size += 1
    payload_str = payload_str[:-1]
    payload_str += '}}'

    # Report failed sensors
    if failed_size > 0:
        c_print(f'{col.B_HLT}{failed_size}{col.RESET} sensor '
                f'update{"s" if failed_size > 1 else ""} '
                f'unable to be sent.', tab=1, status='fail')

    # Now let's ship this sucker off!
    try:
        MQTT_CLIENT.publish(topic=f'sys-qtt/sensor/{SensorObject.device_name}/state',
                            payload=payload_str, qos=1, retain=False)
    except Exception as e:
        c_print(f'Unable to publish update payload: '
                f'{col.B_FAIL}{e}', tab=1, status='fail')

    c_print(f'{col.B_HLT}{payload_size}{col.RESET} sensor '
            f'update{"s" if payload_size > 1 else ""} '
            f'sent to MQTT broker.', tab=1, status='ok')
    c_print(f'{col.B_HLT}{CONFIG["general"]["update_interval"]}{col.RESET} '
            f'seconds until next update...', tab=1, status='wait')


# ------------------------------------------------------------------
# ARGUMENT PARSER
# ------------------------------------------------------------------
def _parser():
    """Generate argument parser"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='path to the config.yaml file',
                        default=CONFIG_PATH)
    return parser


# ------------------------------------------------------------------
# CHECK FOR CONFIG FILE AND IMPORT
# ------------------------------------------------------------------
def import_config_yaml():
    """Import config.yaml either via supplied argument, or check in default location"""
    c_print('Importing config.yaml...', status='wait')
    try:
        args = _parser().parse_args()
        config_file = args.config
        with open(config_file) as f:
            config_yaml = yaml.safe_load(f)
        c_print(f'Config file found: {CONFIG_PATH}', tab=1, status='ok')
        return config_yaml
    except Exception as e:
        c_print(f'{col.B_HLT}Could not find config.yaml file. '
                f'Please check the documentation: {e}', status='fail')
        print()
        sys.exit()


# ------------------------------------------------------------------
# INITIALISE CONFIG FILES AND SET DEFAULTS IF REQUIRED
# ------------------------------------------------------------------
def initialise_config(config_dict) -> dict:
    c_print('Processing config...', status='wait')
    _required_general = ['broker_host', 'broker_user', 'broker_pass',
                         'device_name', 'client_id', 'timezone']
    _default_config = {'broker_port': 1883, 'update_interval': 60,
                       'retry_time': 10, 'allowed_sensor_fails': 0}

    # Check for missing required configs
    if 'general' not in config_dict:
        c_print(f'{col.B_HLT}"general"{col.RESET} category not defined in config file. '
                f'Was it deleted by accident? Please recreate config.yaml '
                f'using /examples/config.yaml.', tab=1, status='fail')
        raise ProgramKilled
    if 'sensors' not in config_dict:
        c_print(f'{col.B_HLT}"sensors"{col.RESET} category not defined in config file. '
                f'Was it deleted by accident? Please recreate config.yaml '
                f'using /examples/config.yaml.', tab=1, status='fail')
        raise ProgramKilled
    if len(missing := [x for x in _required_general if x not
                       in config_dict['general']]) > 0:
        for m in missing:
            c_print(f'Required {col.B_HLT}{m}{col.RESET} not defined in config file.'
                    f'Please check the documentation.', tab=1, status='fail')
        raise ProgramKilled

    # Apply default configs if required
    for d in _default_config:
        if d not in config_dict['general']:
            c_print(f'{col.B_HLT}{d}{col.RESET} not defined in config file. '
                    f'Defaulting to {col.B_HLT}{_default_config[d]}'
                    f'{col.RESET}.', tab=1, status='ok')
            config_dict['general'][d] = _default_config[d]
    c_print('Config initialised.', tab=1, status='ok')
    set_timezone(config_dict['general']['timezone'])
    # Import sensor properties
    global PROPERTIES
    c_print('Importing sensor properties...', status='wait', tab=1)
    try:
        with open(PROPS_PATH, 'r') as infile:
            PROPERTIES = json.load(infile)
    except Exception as e:
        c_print(f'Could not load {col.B_HLT}{PROPS_PATH}{col.RESET}. Check if it exists. '
                f'If not, please download file again: {e}', tab=1, status='fail')
        raise ProgramKilled
    c_print('Sensor properties loaded.', tab=2, status='ok')

    # Validate imported sensor properties
    for s in PROPERTIES:
        sensor_prop = PROPERTIES[s]
        # Add any missing properties
        if 'icon' not in sensor_prop:
            c_print(f'Sensor {col.B_HLT}icon{col.RESET} not defined for {col.B_HLT}'
                    f'{sensor_prop}{col.RESET}. Defaulting to {col.B_HLT}'
                    f'help{col.RESET} icon. See {col.B_HLT}{PROPS_FILE} {col.RESET}'
                    f'to resolve.', tab=1, status='warning')
            sensor_prop['icon'] = 'help'
        if 'title' not in sensor_prop:
            c_print(f'Sensor {col.B_HLT}title{col.RESET} not defined for {col.B_HLT}'
                    f'{sensor_prop}{col.RESET}. Defaulting to {col.B_HLT}'
                    f'{sensor_prop["name"]}{col.RESET}. See {col.B_HLT}{PROPS_FILE}'
                    f'{col.RESET} to resolve.', tab=1, status='warning')
            sensor_prop['title'] = sensor_prop['name']

    c_print('Config loaded successfully.', tab=1, status='ok')
    return config_dict


# -------------------------------------------------------------
# COMBINE CONFIG.YAML AND SENSOR_DEFAULTS.JSON TO BUILD SENSORS
# -------------------------------------------------------------
def import_sensors(sensor_dict: dict) -> dict:
    # Main sensor config import
    c_print('Importing sensor configurations...', status='wait')
    for sensor in CONFIG['sensors']:
        if sensor not in PROPERTIES:
            c_print(f'{col.B_HLT}{sensor}{col.RESET} missing from {col.B_HLT}{PROPS_FILE}'
                    f'{col.RESET}. Skipping.', tab=1, status='warning')
            continue
        # Skip if unknown value provided
        if CONFIG['sensors'][sensor] not in \
                [False, 'off', True, 'on', 'dynamic', 'static']:
            c_print(f'Unknown value {col.B_HLT}{CONFIG["sensors"][sensor]} {col.RESET}'
                    f'for {col.B_HLT}{sensor}{col.RESET}. Allowed values: {col.B_HLT}'
                    f'"off", "on", "dynamic", "static"{col.RESET}. Please check '
                    f'{col.B_HLT}config.yaml{col.RESET}.', tab=1, status='warning')
            continue
        # Ignore sensors turned off
        if CONFIG['sensors'][sensor] in ['off', False]:
            continue
        # Filter duplicate entries
        if sensor in sensor_dict:
            c_print(f'Multiple {col.B_HLT}{sensor}{col.RESET} in {col.B_HLT}config.yaml'
                    f'{col.RESET}. Ignoring duplicate. Remove from config to silence '
                    f'this warning.', tab=1, status='warning')
            continue
        # Add valid sensor to use in this session
        try:
            PROPERTIES[sensor]['name'] = sensor
            PROPERTIES[sensor]['static'] = CONFIG['sensors'][sensor] == 'static'
            sensor_dict[sensor] = SensorObject(PROPERTIES[sensor])
        except Exception as e:
            c_print(f'Unable add {col.B_HLT}{sensor}{col.RESET}and has been removed '
                    f'from session: {col.B_FAIL}{e}', tab=1, status='fail')

    # Mounted disk sensor config import
    _mnt = 'disk_mounted'
    if _mnt in CONFIG and CONFIG[_mnt] is not None:
        for d in CONFIG[_mnt]:
            # Skip duplicate names
            if d in sensor_dict:
                c_print(f'Mounted disk {col.B_HLT}{d}{col.RESET} has the same name '
                        f'as another sensor. Remove from config or change its name '
                        f'to stop this message.', tab=1, status='warning')
                continue
            # Skip mounted disk sensor if no path provided
            if CONFIG[_mnt][d] is None:
                c_print(f'{col.B_HLT}{d}{col.RESET} mounted disk config entry '
                        f'is{col.B_HLT} missing a volume path{col.RESET}. Skipping. '
                        f'Check config.yaml.', tab=1, status='warning')
                continue
            # Skip mounted drive paths that do not resolve a valid directory
            if not path.isdir(CONFIG[_mnt][d]):
                c_print(f'{col.B_HLT}{d}{col.RESET} mounted disk path {col.B_HLT}'
                        f'{CONFIG[_mnt][d]}{col.RESET} is not a valid directory. '
                        f'Skipping. Check config.yaml.', tab=1, status='warning')
                continue
            # Add valid mounted disk sensor to use in this session
            try:
                drive_properties = PROPERTIES[_mnt]
                drive_properties['name'] = f'disk_{d.replace(" ","_").lower()}'
                drive_properties['title'] = f'Disk {d} Use'
                drive_properties['path'] = CONFIG[_mnt][d]
                drive_properties['static'] = False
                # Name mounted disk sensor internally with "disk_" prefix name
                sensor_dict[drive_properties['name']] = SensorObject(drive_properties)
            except Exception as e:
                c_print(f'Unable to add {col.B_HLT}{d}{col.RESET} mounted disk and '
                        f'has been removed from this session: '
                        f'{col.B_FAIL}{e}', tab=1, status='fail')

    c_print(f'Imported {col.B_HLT}{len(sensor_dict)}{col.RESET} '
            f'sensor properties.', tab=1, status='ok')

    # Initialise static sensors
    c_print(f'Initialising {col.B_HLT}static{col.RESET} sensors...', tab=1, status='wait')
    failed_sensors = VALUE_GENERATOR.build_statics(sensor_dict)
    if len(failed_sensors) > 0:
        for f in failed_sensors:
            sensor_dict.pop(f)
        c_print(f'{col.B_HLT}{len(failed_sensors)}{col.RESET} static sensors have been '
                f'removed from this session. Please check your config!',
                tab=2, status='warning')
    c_print('Static sensors built.', tab=2, status='ok')
    # Check all sensor object values and remove ones that fail to generate a value
    c_print('Checking output of each sensor...', tab=1, status='wait')
    failed_sensors = {}
    for sensor in sensor_dict:
        if (value := VALUE_GENERATOR.value(sensor_dict[sensor])) is not None:
            c_print(f'{col.B_HLT}{sensor}{col.RESET} returned: {col.B_HLT}{value} '
                    + (f'{sensor_dict[sensor].properties["unit"]}' if 'unit' in
                       sensor_dict[sensor].properties else ''), tab=2, status='ok')
        else:
            failed_sensors[sensor] = 'off'
    if len(failed_sensors) > 0:
        for f in failed_sensors:
            sensor_dict.pop(f)
        c_print(f'{col.B_HLT}{len(failed_sensors)}{col.RESET} sensors have been removed '
                f'from this session. Please check your config!', tab=1, status='warning')
    # Return the new sensor list
    c_print(f'{col.B_HLT}{len(sensor_dict)}{col.RESET} sensors have been committed to '
            f'the session.', tab=1, status='ok')
    return sensor_dict


# ------------------------------------
# PUBLISH SENSOR MQTT CONFIG TO BROKER
# ------------------------------------
def publish_sensor_configs(mqttClient):
    c_print('Publishing sensor configurations...', tab=1, status='wait')
    payload_size = 0
    for s in SENSOR_DICT:
        try:
            mqttClient.publish(topic=SENSOR_DICT[s].config.topic,
                               payload=SENSOR_DICT[s].config.payload,
                               qos=SENSOR_DICT[s].config.qos,
                               retain=SENSOR_DICT[s].config.retain)
            payload_size += 1
        except Exception as e:
            c_print(f'Could not publish {col.B_HLT}{SENSOR_DICT[s].properties["name"]}'
                    f'{col.RESET} sensor configuration: {col.B_FAIL}{e}',
                    tab=2, status='warning')
    mqttClient.publish(f'sys-qtt/sensor/{SensorObject.device_name}/availability',
                       'online', retain=True)
    c_print(f'{col.B_HLT}{payload_size}{col.RESET} sensor config'
            f'{"s" if payload_size != 1 else ""} and '
            f'{col.B_HLT}online{col.RESET} status to broker.', tab=2, status='ok')


# ---------------------------
# MQTT CLIENT OBJECT CREATION
# ---------------------------
def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=CONFIG['general']['client_id'])
    # Add MQTT connection callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    # Set the client will and authentication
    client.will_set(f'sys-qtt/sensor/{SensorObject.device_name}/availability',
                    'offline', retain=True)
    client.username_pw_set(CONFIG['general']['broker_user'],
                           CONFIG['general']['broker_pass'])
    return client


def create_scheduled_job():
    """Define and initialise the update job"""
    try:
        c_print(f'Adding {col.B_HLT}sensor update{col.RESET} job on {col.B_HLT}'
                f'{CONFIG["general"]["update_interval"]}{col.RESET} '
                f'second schedule...', status='wait')
        job = schedule.every(
            CONFIG["general"]["update_interval"]).seconds.do(publish_sensor_values)
        c_print(f'{col.B_HLT}{schedule.get_jobs()}', tab=1, status='ok')
        return job
    except Exception as e:
        c_print(f'Unable to add job: {col.B_FAIL}{e}', tab=1, status='fail')
        sys.exit()


def connect_to_broker():
    """Initiate connection with MQTT server"""
    while True:
        try:
            c_print(f'Attempting to reach MQTT broker at {col.B_HLT}'
                    f'{CONFIG["general"]["broker_host"]}{col.RESET} on port '
                    f'{col.B_HLT}{CONFIG["general"]["broker_port"]}'
                    f'{col.RESET}...', status='wait')
            MQTT_CLIENT.connect(CONFIG['general']['broker_host'],
                                CONFIG['general']['broker_port'])
            c_print(f'{col.B_OK}MQTT broker responded.', tab=1, status='ok')
            break
        except ConnectionRefusedError as e:
            c_print(f'MQTT broker is down or unreachable: '
                    f'{col.B_FAIL}{e}', tab=1, status='fail')
        except OSError as e:
            c_print(f'Network I/O error. Is the network down? '
                    f'{col.B_FAIL}{e}', tab=1, status='fail')
        except Exception as e:
            c_print(f'Terminating connection attempt: '
                    f'{col.B_FAIL}{e}', tab=1, status='fail')
        c_print(f'Trying again in {col.B_HLT}{CONFIG["general"]["retry_time"]}'
                f'{col.RESET} seconds...', tab=1, status='wait')
        time.sleep(CONFIG["general"]["retry_time"])
    try:
        publish_sensor_configs(MQTT_CLIENT)
    except Exception as e:
        c_print(f'Unable to publish sensor config: {col.B_FAIL}{e}', tab=1, status='fail')
        raise ProgramKilled


def on_connect(client, userdata, flags, rc):
    """MQTT broker connection callback"""
    if rc == 0:
        try:
            client.subscribe('hass/status')
            client.publish(f'sys-qtt/sensor/{SensorObject.device_name}/availability',
                           'online', retain=True)
            c_print(f'{col.B_OK}Success!', tab=1, status='ok')
            c_print(f'Updated {col.B_HLT}{SensorObject.device_name}'
                    f'{col.RESET} client on broker with {col.B_HLT}online{col.RESET} '
                    f'status.', tab=1, status='info')
            global connected
            connected = True
        except Exception as e:
            c_print(f'Unable to publish {col.B_HLT}online{col.RESET} status to broker: '
                    f'{col.B_FAIL}{e}', tab=1, status='fail')
    elif rc == 5:
        c_print('Authentication failed.', tab=1, status='fail')
        raise ProgramKilled
    else:
        c_print('Failed to connect.', tab=1, status='fail')


def on_disconnect(client, userdata, rc):
    """MQTT broker disconnection callback"""
    global connected
    connected = False
    print()
    c_print(f'{col.B_FAIL}Disconnected!', tab=1, status='fail')
    if rc != 0:
        c_print('Unexpected MQTT disconnection. '
                'Will attempt to re-establish connection.', tab=2, status='fail')
    else:
        c_print(f'RC value: {col.B_HLT}{rc}', tab=2, status='info')
    if not program_killed:
        print()
        connect_to_broker()


def on_message(client, userdata, message):
    """Receive MQTT message from broker callback"""
    c_print(f'Message received from broker: {col.B_HLT}'
            f'{message.payload.decode()}', status='info')
    if(message.payload.decode() == 'online'):
        publish_sensor_configs(client)


# ----------------
# MAIN APPLICATION
# ----------------
if __name__ == '__main__':
    try:
        # ----------------------
        # SYS-QTT INITIALISATION
        # ----------------------
        c_title('starting up...', '', 'OK')
        # Build global configurations
        CONFIG = import_config_yaml()
        CONFIG = initialise_config(CONFIG)
        SensorObject.display_name = CONFIG['general']['device_name']
        SensorObject.device_name = SensorObject.display_name.replace(' ', '_').lower()
        SENSOR_DICT = import_sensors(SENSOR_DICT)
        MQTT_CLIENT = create_mqtt_client()
        c_print(f'{col.B_OK}Local configuration complete.', tab=1, status='ok')
        # Add handlers for gracefully exiting
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        # Connect to broker and start connection loop
        connect_to_broker()
        c_print('Establishing MQTT connection loop...', status='wait')
        MQTT_CLIENT.loop_start()
        connection_wait_time = 1
        # Wait for broker connection. Increase pause up to 10 minutes.
        while not connected:
            time.sleep(connection_wait_time)
            connection_wait_time *= 2
            connection_wait_time = min(connection_wait_time, 600)
        JOB = create_scheduled_job()
        c_title('now running on:', SensorObject.display_name, 'B_OK')
        time.sleep(1)
        # Publish initial sensor values
        publish_sensor_values()

        # ----------------------------------
        # MQTT CLIENT/BROKER CONNECTION LOOP
        # ----------------------------------
        while True:
            try:
                sys.stdout.flush()
                schedule.run_pending()
                time.sleep(1)
            except ProgramKilled:
                print()
                c_print(f'{col.B_HLT}Program killed:', tab=1, status='warning')
                c_print('Cleaning up...', tab=2, status='wait')
                # Pull down the scheduler and close connection
                schedule.cancel_job(JOB)
                MQTT_CLIENT.loop_stop()
                if MQTT_CLIENT.is_connected():
                    MQTT_CLIENT.publish(f'sys-qtt/sensor/{SensorObject.device_name}'
                                        f'/availability', 'offline', retain=True)
                    MQTT_CLIENT.disconnect()
                c_title('has shutdown', 'successfully', 'B_OK')
                sys.stdout.flush()
                break
    except Exception as e:
        c_title('has shutdown from a', 'fatal error', 'B_FAIL')
        c_print(str(e), tab=1, status='fail')
        print()
