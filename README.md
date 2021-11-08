```
------------------------------------------------------------------
   _________                      ______________________________  
  /   _____/__.__. ______         \_____  \__    ___/\__    ___/  
  \_____  <   |  |/  ___/     _____/  / \  \|    |     |    |     
  /        \___  |\___ \ |Sys-QTT|/   \_/.  \    |     |    |     
 /_______  / ____/____  >"``      \_____\ \_/____|     |____|     
         \/\/         \/                 \__>      o              
                                      System Metrics MQTT Client  
------------------------------------------------------------------
```

Sys-QTT is a light-weight, Python-based system metrics client for monitoring networked devices. It periodically gathers a customisable selection of host machine metrics, and publishes the data to an MQTT broker/server of your choice.

Sys-QTT is based on Sennevds' [System Sensors](https://github.com/Sennevds/system_sensors) project, and has been developed primarily to use with Home Assistant, based on their [MQTT discovery documentation](https://www.home-assistant.io/docs/mqtt/discovery/).
It should work with other any other MQTT broker/configuration, however, the sensor configuration messages are specific to Home Assistant.

**The config/settings for this fork is not compatible with System Sensors. Please follow the instructions below to reeneter the settings from the supplied example directory.**


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

5. Make a copy of the example config file and update it with your MQTT broker details, client ID and client device name:

  ```bash
  cp examples/config.yaml settings.yaml && nano config.yaml
  ```

6. Test the script within your CLI session, any issues will be clearly logged:

  ```bash
  python3 sys-qtt.py --settings config.yaml
  ```

### Output Example

<details><summary>Click here</summary>
<p>

```log
❯ python3 sys-qtt.py

    -----------------------
    Sys-QTT starting up... 
    -----------------------

[•] Importing config.yaml...
    [✓] Config file found: /home/maxvram/Sys-QTT/config.yaml
[•] Processing config...
    [✓] Config initialised.
    [•] Importing sensor properties...
        [✓] Sensor properties loaded.
    [✓] Config loaded successfully.
[•] Importing sensor configurations...
    [✓] Imported 25 sensor properties.
    [•] Initialising static sensors...
        [✓] Static sensors built.
    [•] Checking output of each sensor...
        [✓] board_make returned: Intel Corporation 
        [✓] board_model returned: NUC8BEB 
        [✓] cpu_arch returned: x86_64 
        [✓] cpu_model returned: Intel(R) Core(TM) i5-8259U CPU @ 2.30GHz 
        [✓] cpu_threads returned: 8 
        [✓] cpu_cores returned: 4 
        [✓] cpu_max returned: 3.8 GHz
        [✓] cpu_clock returned: 2.3 GHz
        [✓] cpu_temp returned: 38.0 °C
        [✓] cpu_usage returned: 11.9 %
        [✓] cpu_load_1m returned: 1.73 
        [✓] cpu_load_5m returned: 1.09 
        [✓] cpu_load_15m returned: 1.02 
        [✓] memory_ram returned: 41.6 %
        [✓] memory_swap returned: 97.5 %
        [✓] os_hostname returned: NUC 
        [✓] os_distro returned: Ubuntu 20.04.3 LTS 
        [✓] os_updates returned: 0 
        [✓] net_ip returned: 192.168.20.5 
        [✓] net_tx returned: 0 Kbps
        [✓] net_rx returned: 0 Kbps
        [✓] last_boot returned: 2021-10-27T01:18:41+11:00 
        [✓] last_message returned: 2021-11-09T00:24:34.510696+11:00 
        [✓] disk_system returned: 28.3 %
        [✓] disk_storage returned: 0.3 %
    [✓] 25 sensors have been commited to the session.
    [✓] Local configuration complete.
[•] Attempting to reach MQTT broker at 192.168.20.5 on port 1883...
    [✓] MQTT broker responded.
    [•] Publishing sensor configurations...
        [✓] 25 sensor configs and online status to broker.
[•] Establishing MQTT connection loop...
    [✓] Success!
    [i] Updated nuc_i5 client on broker with online status.
[•] Adding sensor update job on 30 second schedule...
    [✓] [Every 30 seconds do publish_sensor_values() (last run: [never], next run: 2021-11-09 00:25:05)]

    ------------------------------
    Sys-QTT now running on: NUC i5
    ------------------------------

[•] Sending update sensor payload...
    [✓] 25 sensor updates sent to MQTT broker.
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
