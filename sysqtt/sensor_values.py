import time, psutil, socket
from psutil import net_io_counters as net_tx
from sysqtt.utils import quick_cat, quick_command, as_local, utc_from_ts, delta
from sysqtt.c_print import *




# Network transfer persistence object for calculating network throughput delta
NETWORK_THROUGHPUT_FACTOR = 8 / 1024
class network_tracking(object):
    def __init__(self, dir) -> None:
        self.dir = dir
        self.values = None
    def update(self) -> float:
        if self.values is None:
            self.values = { 'prev': net_tx(0)[self.dir], 'curr': net_tx(0)[self.dir], 'time': time.time(), 'diff': 0 }
            return 0
        self.values['curr'] = net_tx(0)[self.dir]
        self.values = delta(self.values)
        return round(self.values['diff'] * NETWORK_THROUGHPUT_FACTOR, 2)

tx_up = network_tracking(0)
tx_down = network_tracking(1)

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
    """Return details about the host's motherboard. 'board_vendor' and 'board_name' are supprted arguments"""
    # Would prefer a neater method to obtain the host motherboard, but distros/systems seem to have their own paths
    _RASP_NAME_CONST = 'Raspberry Pi'
    _PATH_RPI = '/sys/firmware/devicetree/base/model'
    _PATH_OTHER = '/sys/devices/virtual/dmi/id/'
    # Raspberry Pi path first
    if (reading := quick_cat(_PATH_RPI)) is not None and (rasp_find := reading.rfind(_RASP_NAME_CONST)) >= 0:
        if arg == 'board_vendor':
            return _RASP_NAME_CONST
        elif arg == 'board_name':
            return quick_cat(_PATH_RPI, term=_RASP_NAME_CONST)
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


# ------------------------------------------------------------------
# MAIN SENSOR VALUE OBJECT - HOLDS CALLABLE SENSOR FUNCTIONS
# ------------------------------------------------------------------
class SensorValues(object):
    static_sensors = {}
    sensor_functions = {
        'board_make': lambda: get_board_info('board_vendor'),
        'board_model': lambda: get_board_info('board_name'),
        'cpu_arch': lambda: quick_command('lscpu', term='Architecture:'),
        'cpu_model': lambda: quick_command('lscpu', term='Model name:'),
        'cpu_threads': lambda: quick_command('lscpu', term='CPU(s):', ret_type=int),
        'cpu_cores': lambda: quick_command('lscpu', term='Core(s) per socket:', ret_type=int),
        'cpu_max': lambda: quick_command('lscpu', term='CPU max MHz:', ret_type=int) / 1000,
        'cpu_clock': lambda: round(psutil.cpu_freq().current / 1000, 2),
        'cpu_temp': lambda: get_temp(),
        'cpu_usage': lambda: psutil.cpu_percent(interval=None),
        'cpu_load_1m': lambda: psutil.getloadavg()[0],
        'cpu_load_5m': lambda: psutil.getloadavg()[1],
        'cpu_load_15m': lambda: psutil.getloadavg()[2],
        'memory_ram': lambda: psutil.virtual_memory().percent,
        'memory_swap': lambda: psutil.swap_memory().percent,
        'os_hostname': lambda: socket.gethostname(),
        'os_distro': lambda: quick_cat('/etc/os-release', term='PRETTY_NAME=').strip('"'),
        'os_updates': lambda: get_updates(),
        'net_ip': lambda: get_host_ip(),
        'net_tx': lambda: tx_up.update(),
        'net_rx': lambda: tx_down.update(),
        'wifi_strength': lambda: ' '.join(quick_cat('/proc/net/wireless', term='wlan0:').split(' ')).split()[2],
        'wifi_ssid': lambda: quick_command('/usr/sbin/iwgetid', args=['-r']),
        'last_boot': lambda: as_local(utc_from_ts(psutil.boot_time())).isoformat(),
        'last_message': lambda: str(as_local(utc_from_ts(time.time())).isoformat()),
        'disk_system': lambda: psutil.disk_usage('/').percent}

    # Called to return static or dynamic sensor values
    def value(self, sensor):
        try:
            # Mounted disk sensor functions are always called
            if 'path' in sensor.properties:
                return psutil.disk_usage(sensor.properties['path']).percent
            # Static sensors return values from outputs baked when Sys-QTT is first initialised 
            elif sensor.properties['name'] in SensorValues.static_sensors:
                return SensorValues.static_sensors[sensor.properties['name']]
            # And dynamic sensors call their respective lambda functions
            elif sensor.properties['name'] in SensorValues.sensor_functions:
                return SensorValues.sensor_functions[sensor.properties['name']]()
            else:
                c_print(f'Unable to find {col.B_HLT}{sensor.properties["name"]}'
                        f'{col.RESET} in the session sensor objects.', tab=2, status='fail')
                return None
        # None returns
        except (TypeError, AttributeError):
            c_print(f'{col.B_HLT}{sensor.properties["name"]}{col.RESET} function returned '
                    f'{col.B_HLT}None{col.RESET}.', tab=2, status='fail')
            return None
        # Missing functions in lambda expression
        except NameError as e:
            c_print(f'{col.B_HLT}{sensor.properties["name"]}{col.RESET} sensor '
                    f'function is missing: {col.B_FAIL}{e}', tab=2, status='fail')
            return None
        # General exception
        except Exception as e:
            c_print(f'Error while getting {col.B_HLT}{sensor.properties["name"]}{col.RESET} '
                    f'value: {col.B_FAIL}{e}', tab=2, status='fail')
            return None

    # Called when the application is first initialised to bake sensors defined as static
    def build_statics(self, sensor_dict: dict) -> dict:
        """Build the static sensor values if they're in the supplied dictionary"""
        failed_sensors = []
        for s in sensor_dict:
            properties = sensor_dict[s].properties
            if properties['static'] == True:
                try:
                    if properties['name'] in SensorValues.sensor_functions:
                        SensorValues.static_sensors[properties['name']] = SensorValues.sensor_functions[properties['name']]()
                    else:
                        c_print(f'Could not find function for {col.B_HLT}{properties["name"]}{col.RESET} '
                                f'static sensor. Removing from this session. Please remove from config.', tab=2, status='warning')
                        failed_sensors.append(s)
                except Exception as e:
                    c_print(f'Unable to build {col.B_HLT}{properties["name"]}{col.RESET} static value, '
                            f'removed from list: {col.B_FAIL}{e}', tab=1, status='fail')
                    failed_sensors.append(s)
        return failed_sensors