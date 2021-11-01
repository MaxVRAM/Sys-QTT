
# Sys-QTT

Sys-QTT is a light-weight, Python-based system metrics service for monitoring networked devices. It periodically gathers a customisable selection of host machine metrics, and publishes the data to an MQTT broker/server of your choice.

This was designed to use with Home Assistant, but can be used with any MQTT broker.

### (Nov 2021) Warning

As of November 2021, this fork of Sennevds/system_sensors is major under development.
Some commits may create breaking changes to existing installations.
I'll remove this notice once things are safe again.


## Metrics

The `settings.yaml` file provides a selection from the following metrics:

- **CPU**: make, model, temperature, number of threads and cores, usage, and current & max clock-speed
- **Average Load**: 1min, 5min and 15min
- **Storage**: system and mounted volume drive usages
- **Memory**: physical memory usage, swap usage
- **Network**: up/down throughput, local IP, WiFi signal strength and SSID
- **OS**: hostname, distro name, distro version and pending OS updates
- **Hardware**: system architecture, board make and model, power status (RPI only)
- **Timestamps**: last boot, last message received

## Roadmap

- [x] Add board make and model sensors
- [x] Comprehensive logging for debug
- [x] Clean up the project file structure
- [x] Add CPU make, model, threads, cores and max speed
- [ ] Install and update script

## Requirements

(note, this has only be tested on Linux systems)

- Python **3.8+**
- An MQTT broker. For example:
  - (Home Assistant) [Mosquitto broker integration](https://github.com/home-assistant/addons/blob/master/mosquitto/DOCS.md)
  - (Docker) [Eclipse-Mosquitto](https://hub.docker.com/_/eclipse-mosquitto)

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

## Usage

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

## Home Assistant

If you've followed the installation and setup guide for Home Assistant's [Mosquitto Broker](https://github.com/home-assistant/addons/blob/master/mosquitto/DOCS.md), your Sys-QTT metrics should already in your Home Assistant device and entity listings.

### Debug

[MQTT Explorer](http://mqtt-explorer.com/) is an excellent tool for monitoring the activity of your MQTT data.
If the metrics aren't appearing in your Home Assistant listings, I recommend downloading and connecting MQTT Explorer to your broker.

### Lovelace UI example

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
