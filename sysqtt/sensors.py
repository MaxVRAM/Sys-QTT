#!/usr/bin/env python3

import time, pytz, psutil, socket, platform, subprocess
from datetime import datetime as dt, timedelta as td
from sysqtt.c_print import *
from sysqtt.utils import quick_cat, command_find




apt_disabled = True

hardware_path_other = '/sys/devices/virtual/dmi/id/'
hardware_path_raspi = '/sys/firmware/devicetree/base/model'

_os_data = {}
tx_previous = psutil.net_io_counters()
time_previous = time.time() - 10 # Why minus 10?
_default_timezone = None
_utc = pytz.utc

RASP_NAME_CONST = 'Raspberry Pi'

# Test for apt module for reporting update metric
try:
    import apt
    apt_disabled = False
except ImportError:
    pass



# Get OS information
with open('/etc/os-release') as f:
    for line in f.readlines():
        row = line.strip().split("=")
        _os_data[row[0]] = row[1].strip('"')


def get_board_info(arg) -> str:
    """Return details about the host's motherboard. 'make' and 'model' are supprted arguments"""
    # Raspberry Pi path first
    if (reading := quick_cat(hardware_path_raspi)) is not None and (rasp_find := reading.rfind(RASP_NAME_CONST)) > 0:
        if arg == 'make':
            return 'Raspberry Pi'
        elif arg == 'model':
            return reading[reading[rasp_find + len(RASP_NAME_CONST)]:].strip()
    # Otherwise look in standard Linux path
    if (reading := quick_cat(f'{hardware_path_other}/{arg}')) is not None:
        return reading
    else:
        return 'Unknown'


def set_default_timezone(timezone) -> None:
    global _default_timezone
    _default_timezone = timezone

def as_local(input_dt: dt) -> dt:
    """Convert a UTC datetime object to local time zone."""
    if input_dt.tzinfo is None:
        input_dt = _utc.localize(input_dt)
    if input_dt.tzinfo == _default_timezone:
        return input_dt
    return input_dt.astimezone(_default_timezone)

def utc_from_ts(timestamp: float) -> dt:
    """Return a UTC time from a timestamp."""
    return _utc.localize(dt.utcfromtimestamp(timestamp))

def get_last_boot() -> str:
    return str(as_local(utc_from_ts(psutil.boot_time())).isoformat())

def get_last_message() -> str:
    return str(as_local(utc_from_ts(time.time())).isoformat())

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

def get_clock_speed() -> int:
    clock_speed = int(psutil.cpu_freq().current)
    return clock_speed

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

def get_cpu_usage() -> float:
    return psutil.cpu_percent(interval=None)

def get_swap_usage() -> float:
    return psutil.swap_memory().percent

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

def get_hostname() -> str:
    return socket.gethostname()

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

def get_host_os() -> str:
    try:
        return _os_data['PRETTY_NAME']
    except:
        return 'Unknown'

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
        'sensor_type': 'sensor',
        'function': lambda: get_disk_usage(f'{disk_path}')
        }

sensor_objects = {
          'board_make':
                {'name': 'M/B Make',
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
                 'function': lambda: command_find("lscpu", "Architecture:")},
          'cpu_model': 
                {'name':'CPU Model',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "Model name:")},
          'cpu_threads': 
                {'name':'CPU Threads',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "CPU(s):", ret_type=int)},
          'cpu_cores': 
                {'name':'CPU Cores',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "Core(s) per socket:", ret_type=int)},
          'cpu_max_speed': 
                {'name':'CPU Max',
                 'unit': 'MHz',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "CPU max MHz:", ret_type=int)},
          'cpu_speed':
                {'name':'CPU Speed',
                 'unit': 'MHz',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "CPU MHz:", ret_type=int)},
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
          'load_1m':
                {'name': 'Load 1m',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: get_load(0)},
          'load_5m':
                {'name': 'Load 5m',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: get_load(1)},
          'load_15m':
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