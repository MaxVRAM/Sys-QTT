
# Sys-QTT | System Metrics MQTT Client

Sys-QTT is a light-weight, Python-based system metrics client for monitoring networked devices. It periodically gathers a customisable selection of host machine metrics, and publishes the data to an MQTT broker/server of your choice.

Sys-QTT is based on Sennevds' [System Sensors](https://github.com/Sennevds/system_sensors) project, and has been developed primarily to use with Home Assistant, based on their [MQTT discovery documentation](https://www.home-assistant.io/docs/mqtt/discovery/).
It should work with other any other MQTT broker/configuration, however, the sensor configuration messages are specific to Home Assistant.

**If moving from System Sensors to Sys-QTT: The `settings.yaml` is incompatible between the two platforms. Please follow the instructions below to reeneter the settings from the supplied example directory.**


## Metrics List

The `settings.yaml` file provides a selection from the following metrics:

- **CPU**: model, temperature, number of threads and cores, usage %, and current & max clock-speed
- **Average Load**: 1min, 5min and 15min
- **Storage**: file-system and mounted volume drive usages
- **Memory**: physical memory usage, swap usage
- **Network**: tx/rx rate, local IP, WiFi signal strength and SSID
- **OS**: hostname, distro name, distro version and pending OS updates
- **Hardware**: system architecture, board make and model
- **Timestamps**: last boot, last message received

## Development Roadmap

- [x] Add board make and model sensors
- [x] Comprehensive logging for debug
- [x] Clean up the project file structure
- [x] Add more CPU details
- [x] Complete refactor of the sensors code-base
  - [x] Move sensor definitions to `sensor_details.json` file
  - [x] Reduce function calls by defining sensors as **static** or **dynamic**
  - [x] Move sensors to a run-time dictionary of sensor objects
  - [x] Re-organise scripts so clear their readibility
- [ ] Add ability to create custom sensor (instead of all being hard-coded):
  - [x] Build a set of bash script modules that can be called by custom sensors
  - [ ] Add fields in `sensor_details.json` for custom bash calls and string searches 
- [ ] Tidy Sys-QTT Home Assistant entities:
  - [ ] Move semi-permanent sensor values (make, model, max, etc.) to attributes(?)
  - [ ] Utilise Home Assistant v2021.11's [Entity Categories](https://www.home-assistant.io/blog/2021/11/03/release-202111/)
  - This will clean up the huge amount of sensors, especially with multiple Sys-QTT deployments
- [ ] Install/update script
- [ ] Web interface (yeah, I'm not a minimalist)
- [ ] Build custom HA integration for managing remote Sys-QTT nodes

## System Requirements

**Platform**: This has only be tested on, and will likely only run on, Linux systems.

- Python **3.8+**
- Several Python modules (installed via the supplied `requirements.txt` file)

This project assumes you have an MQTT broker already running. For example:
  - (Home Assistant) [Mosquitto broker integration](https://github.com/home-assistant/addons/blob/master/mosquitto/DOCS.md)
  - (Stand-alone) [Eclipse-Mosquitto](https://hub.docker.com/_/eclipse-mosquitto)

## Installation

The following steps will configure the host and perform a test-run of Sys-QTT:

1. Clone the repo:

  ```bash
  git clone https://github.com/MaxVRAM/Sys-QTT.git && cd Sys-QTT
  ```

2. Install the required modules:

  ```bash
  pip3 install -r requirements.txt
  ```

4. Ensure the `python3-apt` package is installed:

  ```bash
  sudo apt-get install python3-apt
  ```

5. Make a copy of the example setting file and update it with your MQTT broker details, client ID and client device name:

  ```bash
  cp examples/settings.yaml settings.yaml && nano settings.yaml
  ```

6. Test the script within your CLI session, any issues will be clearly logged:

  ```bash
  python3 sys-qtt.py --settings settings.yaml
  ```

### Output Example

<details><summary>Click here</summary>
<p>

```log
System Sensors starting...

[•] Importing settings...
    [✓] Local configuration complete.
[•] Attempting to reach MQTT broker at 192.168.20.5 on port 1883...
    [✓] MQTT broker responded.
    [•] Publishing sensor configurations...
        [✓] board_make: Micro-Star International Co., Ltd.
        [✓] board_model: MPG X570 GAMING PLUS (MS-7C37)
        [✓] temperature: 51.8
        [✓] cpu_make: AuthenticAMD
        [✓] cpu_model: AMD Ryzen 5 3600X 6-Core Processor
        [✓] cpu_threads: 12
        [✓] cpu_cores: 6
        [✓] cpu_max_speed: 4408.5928
        [✓] cpu_speed: 2200.000
        [✓] cpu_usage: 20.0
        [✓] load_1m: 1.29
        [✓] load_5m: 1.47
        [✓] load_15m: 1.58
        [✓] memory_use: 25.2
        [✓] swap_usage: 0.0
        [✓] hostname: maxvram-desktop
        [✓] ip: 192.168.70.20
        [✓] os: Ubuntu 20.04.3 LTS
        [✓] arch: x86_64
        [✓] updates: 0
        [✓] net_tx: 17.62
        [✓] net_rx: 0.00
        [✓] last_boot: 2021-11-01T10:21:05+11:00
        [✓] last_message: 2021-11-01T16:33:53.297987+11:00
        [✓] disk_use: 43.3
        [✓] disk_use_storage: 35.9
    [✓] 26 sensor configs sent to MQTT broker.
[•] Establishing MQTT connection loop...
    [✓] Success!
    [i] Updated desktop client on broker with online status.
[•] Adding sensor update job on 30 second schedule...
    [✓] [Every 30 seconds do update_sensors() (last run: [never], next run: 2021-11-01 16:35:47)]

[✓] Sys-QTT running on Desktop

[•] Sending sensor payload...
    [✓] 26 sensor updates sent to MQTT broker.
    [•] 30 seconds until next update...
```

</p>
</details>

## Starting Sys-QTT On Boot

If the installation and test went well, you can now add a run service for Sys-QTT to run in the background on boot:

1. Open and edit the example `sys-qtt.service` file, changing the user and exec file paths to reflect your configuration:

```bash
nano examples/sys-qtt.service
```

2. Copy the updated service file to your system service directory:

```bash
sudo cp examples/sys-qtt.service /etc/systemd/system
```

3. Enable and start the service:

```bash
sudo systemctl enable sys-qtt
sudo systemctl start sys-qtt
```

4. Check that the service started correctly:

```bash
sudo systemctl status sys-qtt
```

## Debug

The last few lines of the Sys-QTT log output can be viewed via the `systemd` status command:
```bash
sudo systemctl status sys-qtt
```
If this doesn't provide any insights into the issue, stop the systemd service, and run Sys-QTT manually in the CLI:
```bash
sudo systemctl stop sys-qtt
python3 ~/Sys-QTT/sys-qtt.py
```
Sys-QTT will then start in your CLI and display the log in full detail as it starts up.

Another option is to use [MQTT Explorer](http://mqtt-explorer.com/), which is an excellent tool for monitoring the activity of your MQTT data.
If the metrics aren't appearing in your Home Assistant listings, I recommend downloading and connecting MQTT Explorer to your broker.


## Home Assistant Example

I have used following custom plugins for lovelace:

- vertical-stack-in-card
- mini-graph-card
- bar-card

Config:

```yaml
- type: 'custom:vertical-stack-in-card'
    title: Deconz System Monitor
    cards:
      - type: horizontal-stack
        cards:
          - type: custom:mini-graph-card
            entities:
              - sensor.deconz_cpu_usage
            name: CPU
            line_color: '#2980b9'
            line_width: 2
            hours_to_show: 24
          - type: custom:mini-graph-card
            entities:
              - sensor.deconz_temperature
            name: Temp
            line_color: '#2980b9'
            line_width: 2
            hours_to_show: 24
      - type: custom:bar-card
        entity: sensor.deconz_disk_use
        title: HDD
        title_position: inside
        align: split
        show_icon: true
        color: '#00ba6a'
      - type: custom:bar-card
        entity: sensor.deconz_memory_use
        title: RAM
        title_position: inside
        align: split
        show_icon: true
      - type: entities
        entities:
          - sensor.deconz_last_boot
          - sensor.deconz_under_voltage
```

Example:

![alt text](images/example.png?raw=true "Example")
