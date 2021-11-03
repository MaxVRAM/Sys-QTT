#!/usr/bin/env python3

import time, pytz, psutil, socket, platform, subprocess
from datetime import datetime as dt, timedelta as td
from sysqtt.c_print import *
from sysqtt.sensor_object import SensorObject
from sysqtt.utils import quick_cat, quick_command, as_local, utc_from_ts

apt_disabled = True


tx_previous = psutil.net_io_counters()
time_previous = time.time() - 10 # Why minus 10?
_default_timezone = None
UTC = pytz.utc


# Test for apt module for reporting update metric
try:
    import apt
    apt_disabled = False
except ImportError:
    pass



def get_board_info(arg) -> str:
    _RASP_NAME_CONST = 'Raspberry Pi'
    _PATH_OTHER = '/sys/devices/virtual/dmi/id/'
    _PATH_RPI = '/sys/firmware/devicetree/base/model'
    """Return details about the host's motherboard. 'make' and 'model' are supprted arguments"""
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
    try: # ARM architecture check
        temp = psutil.sensors_temperatures()['cpu_thermal'][0].current
    except:
        try: # Try the first entry of coretemp
            temp = psutil.sensors_temperatures()['coretemp'][0].current
        except:
            try: # For some AMD chips (and average values)
                output = psutil.sensors_temperatures()['k10temp']
                for t in output:
                    temp += t.current
                temp = temp / len(output)
            except Exception as e:
                c_print(f'Could not establish CPU temperature reading: {text_color.B_FAIL}{e}', tab=1, status='warning')
                raise
    return round(temp, 1)


def get_disk_usage(path) -> float:
    try:
        disk_percentage = psutil.disk_usage(path).percent
        return disk_percentage
    except Exception as e:
        c_print(f'Could not get disk usage from {text_color.B_HLIGHT}{path}{text_color.RESET}: {text_color.B_FAIL}{e}', tab=1, status='warning')
        raise

def get_memory_usage() -> float:
    return psutil.virtual_memory().percent

def get_load(arg) -> float:
    return psutil.getloadavg()[arg]

def get_net_data(arg) -> float:
    # Define globals to update
    global tx_previous
    global time_previous
    # Get the current network stats
    net_data_current = psutil.net_io_counters()
    time_current = time.time()
    # What's this for                                                                               ??????
    if time_current == time_previous:
        time_current += 1
    # Convert
    net_data = (net_data_current[0] - tx_previous[0]) / (time_current - time_previous) * 8 / 1024
    net_data = (net_data, (net_data_current[1] - tx_previous[1]) / (time_current - time_previous) * 8 / 1024)
    time_previous = time_current
    tx_previous = net_data_current
    net_data = ['%.2f' % net_data[0], '%.2f' % net_data[1]]
    return net_data[arg]

def get_wifi_strength() -> int:
    wifi_strength_value = subprocess.check_output(
                              [
                                  'bash',
                                  '-c',
                                  'cat /proc/net/wireless | grep wlan0: | awk \'{print int($4)}\'',
                              ]
                          ).decode('utf-8').rstrip()
    if not wifi_strength_value:
        wifi_strength_value = '0'
    return int(wifi_strength_value)

def get_wifi_ssid() -> str:
    ssid = 'UNKNOWN'
    try:
        ssid = subprocess.check_output(
                                  [
                                      'bash',
                                      '-c',
                                      '/usr/sbin/iwgetid -r',
                                  ]
                              ).decode('utf-8').rstrip()
    except Exception as e:
        c_print(f'Could not determine WiFi SSID: {text_color.B_FAIL}{e}', tab=1, status='warning')
    return ssid


def get_host_ip() -> str:
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


def get_host_arch() -> str:
    try:
        return platform.machine()
    except:
        return 'Unknown'

def external_disk_object(disk, disk_path) -> dict:
    return {
        'name': f'Disk {disk}',
        'unit': '%',
        'icon': 'harddisk',
        'function': lambda: get_disk_usage(f'{disk_path}')
        }

STATIC_SENSORS = {}

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
        'last_boot': lambda: str(as_local(utc_from_ts(psutil.boot_time())).isoformat()),
        'cpu_speed': lambda: quick_command("lscpu", "CPU MHz:", ret_type=int),
        'cpu_temp': lambda: get_temp(),
        'cpu_usage': lambda: float(psutil.cpu_percent(interval=None)),
        'cpu_load_1m': lambda: psutil.getloadavg()[0],
        'cpu_load_5m': lambda: psutil.getloadavg()[1],
        'cpu_load_15m': lambda: psutil.getloadavg()[2],
        'memory_physical': lambda: psutil.virtual_memory().percent,
        'memory_swap': lambda: psutil.swap_memory().percent,
        'os_hostname': lambda: socket.gethostname(),
        'os_updates': lambda: get_updates(),
        'net_ip': lambda: get_host_ip(),
        'net_wifi_strength': lambda: ' '.join(quick_cat('/proc/net/wireless', term='wlan0:').split(' ')).split()[2],
        'net_wifi_ssid': lambda: quick_command('/usr/sbin/iwgetid', args=['-r']),
        'net_up': lambda: get_net_data(0),
        'net_down': lambda: get_net_data(1),
        'last_message': lambda: str(as_local(utc_from_ts(time.time())).isoformat()),
        'disk_filesystem': lambda: psutil.disk_usage('/').percent
    }

    def value(sensor: object):
        try:
            if 
        except Exception as e:
            c_print(f'Could not get value for {text_color.B_HLIGHT}{sensor}{text_color.RESET}: {text_color.B_FAIL}{e}', tab=1, status='error')


    def __init__(active_sensor_objects: list) -> None:
        """Initialise the sensor values for all the sensors in the supplied active_sensor_object list"""
        for s in active_sensor_objects:
            try:
                if s.details.static == True:
                    if s.name in SensorValues.sensor_functions:
                        SensorObject.values[s.name] = SensorValues.static_sensors[s.name]
                    elif s.details.mounted_disk:
                        psutil.disk_usage().percent




sensor_objects = {
          'board_manufacturer':
                {'name': 'M/B Manufacturer',
                 'icon': 'domain',
                 'sensor_type': 'sensor',
                 'function': lambda: get_board_info("board_vendor")},
          'board_model':
                {'name': 'M/B Model',
                 'icon': 'package',
                 'sensor_type': 'sensor',
                 'function': lambda: get_board_info("board_name")},
          'cpu_arch':
                {'name': 'CPU Architecture',
                 'icon': 'chip',
                 'sensor_type': 'sensor',
                 'function': lambda: quick_command("lscpu", "Architecture:")},
          'cpu_model': 
                {'name':'CPU Model',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: quick_command("lscpu", "Model name:")},
          'cpu_threads': 
                {'name':'CPU Threads',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: quick_command("lscpu", "CPU(s):", ret_type=int)},
          'cpu_cores': 
                {'name':'CPU Cores',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: quick_command("lscpu", "Core(s) per socket:", ret_type=int)},
          'cpu_max_speed': 
                {'name':'CPU Max',
                 'unit': 'MHz',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: quick_command("lscpu", "CPU max MHz:", ret_type=int)},
          'cpu_speed':
                {'name':'CPU Speed',
                 'unit': 'MHz',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: quick_command("lscpu", "CPU MHz:", ret_type=int)},
          'cpu_temp': 
                {'name':'CPU Temperature',
                 'class': 'temperature',
                 'unit': '°C',
                 'icon': 'thermometer',
                 'sensor_type': 'sensor',
                 'function': get_temp},
          'cpu_usage':
                {'name':'CPU Usage',
                 'unit': '%',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': get_cpu_usage},
          'cpu_load_1m':
                {'name': 'Load 1m',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: get_load(0)},
          'cpu_load_5m':
                {'name': 'Load 5m',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: get_load(1)},
          'cpu_load_15m':
                {'name': 'Load 15m',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: get_load(2)},
          'memory_physical':
                {'name':'Memory Physical',
                 'unit': '%',
                 'icon': 'memory',
                 'sensor_type': 'sensor',
                 'function': get_memory_usage},
          'memory_swap':
                {'name':'Memory Swap',
                 'unit': '%',
                 'icon': 'harddisk',
                 'sensor_type': 'sensor',
                 'function': get_swap_usage},
          'os_hostname':
                {'name': 'OS Hostname',
                 'icon': 'card-account-details',
                 'sensor_type': 'sensor',
                 'function': get_hostname},
          'os_distro':
                {'name': 'OS Distro',
                 'icon': 'linux',
                 'sensor_type': 'sensor',
                 'function': get_host_os},
          'os_updates': 
                {'name':'OS Updates',
                 'icon': 'package-down',
                 'sensor_type': 'sensor',
                 'function': get_updates},
          'net_ip':
                {'name': 'Network IP',
                 'icon': 'ip',
                 'sensor_type': 'sensor',
                 'function': get_host_ip},
          'net_up':
                {'name': 'Network Up',
                 'unit': 'Kbps',
                 'icon': 'upload-network',
                 'sensor_type': 'sensor',
                 'function': lambda: get_net_data(0)},
          'net_down':
                {'name': 'Network Down',
                 'unit': 'Kbps',
                 'icon': 'download-network',
                 'sensor_type': 'sensor',
                 'function': lambda: get_net_data(1)},
          'net_wifi_strength': 
                {'name':'WiFi Strength',
                 'class': 'signal_strength',
                 'unit': 'dBm',
                 'icon': 'wifi-strength-3',
                 'sensor_type': 'sensor',
                 'function': get_wifi_strength},
          'net_wifi_ssid': 
                {'name':'WiFi SSID',
                 'class': 'signal_strength',
                 'icon': 'wifi',
                 'sensor_type': 'sensor',
                 'function': get_wifi_ssid},
          'last_boot':
                {'name': 'Last Boot',
                 'class': 'timestamp',
                 'icon': 'clock',
                 'sensor_type': 'sensor',
                 'function': get_last_boot},
          'last_message':
                {'name': 'Last Message',
                 'class': 'timestamp',
                 'icon': 'clock-check',
                 'sensor_type': 'sensor',
                 'function': get_last_message},
          'disk_filesystem':
                {'name':'Disk Filesystem',
                 'unit': '%',
                 'icon': 'micro-sd',
                 'sensor_type': 'sensor',
                 'function': lambda: get_disk_usage('/')},
            }