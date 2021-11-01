#!/usr/bin/env python3

import time, pytz, psutil, socket, platform, subprocess
from datetime import datetime as dt, timedelta as td
from sysqtt.c_print import *
from sysqtt.utils import quick_cat, command_find

rpi_power_disabled = True
under_voltage = None
apt_disabled = True

system_board = {'make':'Unknown','model':'Unknown'}
hardware_path_other = '/sys/devices/virtual/dmi/id/'
hardware_path_raspi = '/sys/firmware/devicetree/base/model'

_os_data = {}
_previous_net_data = psutil.net_io_counters()
_previous_time = time.time() - 10
_default_timezone = None
_utc = pytz.utc

# Test for Raspberry PI power module
try:
    from rpi_bad_power import new_under_voltage
    if new_under_voltage() is not None:
        # Only enable if import works and function returns a value
        rpi_power_disabled = False
        under_voltage = new_under_voltage()
except ImportError:
    pass

# Test for APT module
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

def get_make() -> str:
    return system_board['make']
def get_model() -> str:
    return system_board['model']

# Check for hardware details in Raspberry Pi path
hw_output = quick_cat(hardware_path_raspi)
if hw_output != None and 'Raspberry Pi' in hw_output:
    system_board['make'] = 'Raspberry Pi'
    system_board['model'] = hw_output[hw_output.rfind(system_board['make'])+len(system_board['make']):].strip()
else:
    # Otherwise check for hardware details in standard linux path
    hw_output = quick_cat(f'{hardware_path_other}/board_vendor')
    if hw_output != None:
        system_board['make'] = hw_output.strip()
    hw_output = quick_cat(f'{hardware_path_other}/board_name')
    if hw_output != None:
        system_board['model'] = hw_output.strip()


def set_default_timezone(timezone) -> None:
    global _default_timezone
    _default_timezone = timezone

def as_local(dattim: dt) -> dt:
    global _default_timezone
    """Convert a UTC datetime object to local time zone."""
    if dattim.tzinfo == _default_timezone:
        return dattim
    if dattim.tzinfo is None:
        dattim = _utc.localize(dattim)

    return dattim.astimezone(_default_timezone)

def utc_from_timestamp(timestamp: float) -> dt:
    """Return a UTC time from a timestamp."""
    return _utc.localize(dt.utcfromtimestamp(timestamp))

def get_last_boot() -> str:
    return str(as_local(utc_from_timestamp(psutil.boot_time())).isoformat())

def get_last_message() -> str:
    return str(as_local(utc_from_timestamp(time.time())).isoformat())

def get_updates() -> int:
    cache = apt.Cache()
    cache.open(None)
    cache.upgrade()
    return cache.get_changes().__len__()

# Temperature method depending on system distro
def get_temp() -> float:
    temp = 'Unknown'
    # Utilising psutil for temp reading on ARM arch
    try:
        temp = psutil.sensors_temperatures()['cpu_thermal'][0].current
    except:
        try:
            # Assumes that first entry is the CPU package
            temp = psutil.sensors_temperatures()['coretemp'][0].current
        except:
            try:
                # Otherwise, attempts k10temp (for some AMD chips) and averages their values
                temp = 0
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
    global _previous_net_data
    global _previous_time
    current_net_data = psutil.net_io_counters()
    current_time = time.time()
    if current_time == _previous_time:
        current_time += 1
    net_data = (current_net_data[0] - _previous_net_data[0]) / (current_time - _previous_time) * 8 / 1024
    net_data = (net_data, (current_net_data[1] - _previous_net_data[1]) / (current_time - _previous_time) * 8 / 1024)
    _previous_time = current_time
    _previous_net_data = current_net_data
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
        c_print(f'Could not deterine WiFi SSID: {text_color.B_FAIL}{e}', tab=1, status='warning')
    return ssid

def get_rpi_power_status() -> str:
    return under_voltage.get()

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

def external_drive_base(drive, drive_path) -> dict:
    return {
        'name': f'Disk Use {drive}',
        'unit': '%',
        'icon': 'harddisk',
        'sensor_type': 'sensor',
        'function': lambda: get_disk_usage(f'{drive_path}')
        }
#command_find('lscpu', 'Model name:')
sensor_objects = {
          'board_make':
                {'name': 'System Make',
                 'icon': 'domain',
                 'sensor_type': 'sensor',
                 'function': get_make},
          'board_model':
                {'name': 'System Model',
                 'icon': 'package',
                 'sensor_type': 'sensor',
                 'function': get_model},
          'temperature': 
                {'name':'Temperature',
                 'class': 'temperature',
                 'unit': '°C',
                 'icon': 'thermometer',
                 'sensor_type': 'sensor',
                 'function': get_temp},
          'cpu_make': 
                {'name':'CPU Make',
                 'icon': 'domain',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "Vendor ID:")},
          'cpu_model': 
                {'name':'CPU Model',
                 'icon': 'package',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "Model name:")},
          'cpu_threads': 
                {'name':'CPU Threads',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "CPU(s):")},
          'cpu_cores': 
                {'name':'CPU Cores',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "Core(s) per socket:")},
          'cpu_max_speed': 
                {'name':'CPU Max',
                 'unit': 'MHz',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "CPU max MHz:")},
          'cpu_speed':
                {'name':'CPU Speed',
                 'unit': 'MHz',
                 'icon': 'cpu-64-bit',
                 'sensor_type': 'sensor',
                 'function': lambda: command_find("lscpu", "CPU MHz:")},
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
          'memory_use':
                {'name':'Memory Use',
                 'unit': '%',
                 'icon': 'memory',
                 'sensor_type': 'sensor',
                 'function': get_memory_usage},
          'swap_usage':
                {'name':'Swap Usage',
                 'unit': '%',
                 'icon': 'harddisk',
                 'sensor_type': 'sensor',
                 'function': get_swap_usage},
          'hostname':
                {'name': 'Hostname',
                 'icon': 'card-account-details',
                 'sensor_type': 'sensor',
                 'function': get_hostname},
          'ip':
                {'name': 'IP Address',
                 'icon': 'ip',
                 'sensor_type': 'sensor',
                 'function': get_host_ip},
          'os':
                {'name': 'System OS',
                 'icon': 'linux',
                 'sensor_type': 'sensor',
                 'function': get_host_os},
          'arch':
                {'name': 'Architecture',
                 'icon': 'chip',
                 'sensor_type': 'sensor',
                 'function': get_host_arch},
          'updates': 
                {'name':'Updates',
                 'icon': 'package-down',
                 'sensor_type': 'sensor',
                 'function': get_updates},
          'wifi_strength': 
                {'class': 'signal_strength',
                 'name':'WiFi Strength',
                 'unit': 'dBm',
                 'icon': 'wifi-strength-3',
                 'sensor_type': 'sensor',
                 'function': get_wifi_strength},
          'wifi_ssid': 
                {'class': 'signal_strength',
                 'name':'WiFi SSID',
                 'icon': 'wifi',
                 'sensor_type': 'sensor',
                 'function': get_wifi_ssid},
          'net_tx':
                {'name': 'Upload Throughput',
                 'unit': 'Kbps',
                 'icon': 'upload-network',
                 'sensor_type': 'sensor',
                 'function': lambda: get_net_data(0)},
          'net_rx':
                {'name': 'Download Throughput',
                 'unit': 'Kbps',
                 'icon': 'download-network',
                 'sensor_type': 'sensor',
                 'function': lambda: get_net_data(1)},
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
          'power_status':
                {'name': 'Power Status',
                 'class': 'problem',
                 'icon': 'power-plug',
                 'sensor_type': 'binary_sensor',
                 'function': get_rpi_power_status},
          'disk_use':
                {'name':'Disk Use',
                 'unit': '%',
                 'icon': 'micro-sd',
                 'sensor_type': 'sensor',
                 'function': lambda: get_disk_usage('/')},
            }