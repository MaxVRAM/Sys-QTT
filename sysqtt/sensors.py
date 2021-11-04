#!/usr/bin/env python3

import time, psutil, socket
from psutil import net_io_counters as net_tx
from sysqtt.utils import quick_cat, quick_command, as_local, utc_from_ts, delta
from sysqtt.c_print import *

TX_FACTOR = 8 / 1024

class Tx(object):
    def __init__(self, dir) -> None:
        self.dir = dir
        self.values = { 'prev': 0, 'curr': 0, 'time': time.time(), 'diff': 0 }
    def update(self) -> float:
        self.values['curr'] = net_tx(0)[self.dir]
        self.values = delta(self.values)
        return round(self.values['diff'] * TX_FACTOR, 2)

tx_up = Tx(0)
tx_down = Tx(0)

tx_up.update()

# Test for apt module for reporting update metric
APT_DISABLED = True
try:
    import apt
    APT_DISABLED = False
except ImportError:
    pass

def get_host_ip() -> str:
    """Return host device's local IP address"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except socket.error:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            return '127.0.0.1'
    finally:
        sock.close()

def get_board_info(arg) -> str:
    """Return details about the host's motherboard. 'make' and 'model' are supprted arguments"""
    # Would prefer a neater method to obtain the host motherboard, but distros/systems seem to have their own paths
    _RASP_NAME_CONST = 'Raspberry Pi'
    _PATH_RPI = '/sys/firmware/devicetree/base/model'
    _PATH_OTHER = '/sys/devices/virtual/dmi/id/'
    # Raspberry Pi path first
    if (reading := quick_cat(_PATH_RPI)) is not None and (rasp_find := reading.rfind(_RASP_NAME_CONST)) > 0:
        if arg == 'make':
            return _RASP_NAME_CONST
        elif arg == 'model':
            return reading[reading[rasp_find + len(_RASP_NAME_CONST)]:].strip()
    # Otherwise look in standard Linux path
    if (reading := quick_cat(f'{_PATH_OTHER}/{arg}')) is not None:
        return reading
    else:
        return 'Unknown'

def get_updates() -> int:
    """Return the number of pending OS updates"""
    cache = apt.Cache()
    cache.open(None)
    cache.upgrade()
    return cache.get_changes().__len__()

def get_temp() -> float:
    """Return CPU temperature"""
    temp = 0
    ps_temp = psutil.sensors_temperatures()
    if 'cpu_thermal' in ps_temp:
        temp = ps_temp['cpu_thermal'][0].current
    elif 'coretemp' in ps_temp:
        temp = ps_temp['coretemp'][0].current
    elif 'k10temp' in ps_temp:
        temp = ps_temp['k10temp'][0].current
    return round(temp, 1)

class SensorValues(object):
    static_sensors = {}
    sensor_functions = {
        'board_manufacturer': lambda: get_board_info('board_vendor'),
        'board_model': lambda: get_board_info('board_name'),
        'cpu_arch': lambda: quick_command('lscpu', term='Architecture:'),
        'cpu_model': lambda: quick_command('lscpu', term='Model name:'),
        'cpu_threads': lambda: quick_command('lscpu', term='CPU(s):', ret_type=int),
        'cpu_cores': lambda: quick_command('lscpu', term='Core(s) per socket:', ret_type=int),
        'cpu_max_speed': lambda: quick_command('lscpu', term='CPU max MHz:', ret_type=int),
        'os_distro': lambda: quick_cat('/etc/os-release', term='PRETTY_NAME=').strip('"'),
        'last_boot': lambda: as_local(utc_from_ts(psutil.boot_time())).isoformat(),
        'cpu_speed': lambda: quick_command('lscpu', term='CPU MHz:', ret_type=int),
        'cpu_temp': lambda: get_temp(),
        'cpu_usage': lambda: psutil.cpu_percent(interval=None),
        'cpu_load_1m': lambda: psutil.getloadavg()[0],
        'cpu_load_5m': lambda: psutil.getloadavg()[1],
        'cpu_load_15m': lambda: psutil.getloadavg()[2],
        'memory_physical': lambda: psutil.virtual_memory().percent,
        'memory_swap': lambda: psutil.swap_memory().percent,
        'os_hostname': lambda: socket.gethostname(),
        'os_updates': lambda: get_updates(),
        'net_ip': lambda: get_host_ip(),
        'net_tx': lambda: tx_up.update(),
        'net_rx': lambda: tx_down.update(),
        'net_wifi_strength': lambda: ' '.join(quick_cat('/proc/net/wireless', term='wlan0:').split(' ')).split()[2],
        'net_wifi_ssid': lambda: quick_command('/usr/sbin/iwgetid', args=['-r']),
        'last_message': lambda: str(as_local(utc_from_ts(time.time())).isoformat()),
        'disk_filesystem': lambda: psutil.disk_usage('/').percent}

    def value(self, sensor):
        try:
            if sensor.details['name'] in SensorValues.static_sensors:
                return SensorValues.static_sensors[sensor.details['name']]()
            elif sensor.details['name'] in SensorValues.sensor_functions:
                return SensorValues.sensor_functions[sensor.details['name']]()
            elif sensor.details['mounted']:
                return psutil.disk_usage(sensor.details['path']).percent
            else:
                c_print(f'Unable to obtain {text_color.B_HLIGHT}{sensor.details["name"]}{text_color.RESET} value.', tab=2, status='fail')
                return None
        except (TypeError, AttributeError):
            c_print(f'{text_color.B_HLIGHT}{sensor.details["name"]}{text_color.RESET} function returned {text_color.B_HLIGHT}None{text_color.RESET}.', tab=2, status='fail')
            return None
        except Exception as e:
            c_print(f'Error while getting {text_color.B_HLIGHT}{sensor.details["name"]}{text_color.RESET} value: {text_color.B_FAIL}{e}', tab=2, status='fail')
            return None

    def build_statics(self, sensor_dict: dict) -> dict:
        """Build the static sensor values if they're in the supplied dictionary"""
        failed_sensors = []
        for s in sensor_dict:
            details = sensor_dict[s].details
            if details['static'] == True:
                try:
                    if details['name'] in SensorValues.sensor_functions:
                        SensorValues.static_sensors[details['name']] = SensorValues.sensor_functions[details['name']]
                    elif s.details['mounted']:
                        SensorValues.static_sensors[details['name']] = psutil.disk_usage(details['path']).percent
                except Exception as e:
                    c_print(f'Unable to build {text_color.B_HLIGHT}{details["name"]}{text_color.RESET} static value, removed from list: {text_color.B_FAIL}{e}', tab=1, status='fail')
                    failed_sensors.append(s)
        return failed_sensors