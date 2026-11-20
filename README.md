# Zigma Spark-980 for Home Assistant

A custom Home Assistant integration for the Zigma Spark-980 robot vacuum. It talks to the robot's local web API, so daily control works without the manufacturer's cloud.

The robot must run the local control software from [bultza/zigma-spark-980-free](https://github.com/bultza/zigma-spark-980-free) (Zigma Free). This integration only works with that software. See that project's [Installation Manual](https://github.com/bultza/zigma-spark-980-free/blob/main/installer/README.md) for how to set it up on the robot.

## Features

- **Vacuum entity** with start, pause, resume and return to dock. The fan speed (1–3) is set in HA.
- **Sensors:** battery, working status, cleaned area, cleaning time, error state and Wi-Fi signal.
- **Schedules:** each robot schedule shows up as an on/off switch and a start time. You can change them from HA.
- **Named zones:** define rectangles on the map and get one "<name> saugen" button per zone.

## Requirements

- Home Assistant with support for custom integrations.
- A Zigma Spark-980 running Zigma Free, reachable from Home Assistant on your local network.
- The API token of the robot. It is the same token the Zigma Free web interface uses, and it changes when you change the web password.

## Installation

### Via the Home Assistant Marketplace (2026.11 and newer)

HACS is now part of Home Assistant as the Marketplace.

1. Open **Settings → Marketplace**. Accept the warning on the first visit. Connect GitHub if asked.
2. In the upper-right corner, select **Add from link**.
3. Enter `virido88/zigma-spark-980-free-homassistant` under **GitHub link** and select **Add**. If asked, pick **Type** Integration.
4. Open **Zigma Spark-980** in the list and select **Install**.

### Via HACS (Home Assistant before 2026.11)

1. In HACS, open **⋮ → Custom repositories**.
2. Add `https://github.com/virido88/zigma-spark-980-free-homassistant` with category **Integration**.
3. Install **Zigma Spark-980** and restart Home Assistant.

### Manually

1. Copy the folder `custom_components/zigma/` into the `custom_components/` folder of your Home Assistant configuration.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & services → Add integration** and search for **Zigma**.
2. Enter the robot's IP address or host name, the port (default `8765`) and the API token.
3. The integration checks the connection before it saves the entry.

## Zones

Zones are rectangles in map cells. The robot cleans only the rectangle you choose.

1. Open **Settings → Devices & services → Zigma → Configure → Add zone**.
2. Enter a name and the rectangle: X, Y, width and height. The minimum width and height are 2 cells.
3. Home Assistant creates a button "<name> saugen" for the zone.

Pressing the button sends the cleaning command to the robot. It works only when the robot is docked, in standby or paused. Otherwise Home Assistant shows an error.

To find the right coordinates, look at the map in the Zigma Free web interface.

## More features (0.2.0)

- **Map:** an image entity "Karte" shows the map, path, dock and no-go zones.
- **Schedules:** switch, time and fan power per schedule. Services `zigma.add_schedule`, `zigma.update_schedule` (weekdays, action, label) and `zigma.delete_schedule`.
- **Settings:** volume, name, time zone, NTP server, area unit, "over ridge" and "continue clean", plus a clock sync button.
- **History:** sensors for the last cleaning report, the number of runs, the last event (log in attributes) and software versions.
- **Services:** `zigma.clean_area` (any rectangle) and `zigma.set_no_go_zone` (add, update, delete).

Not offered on purpose: reboot, restore master, custom shell command, map delete/restore, SSH keys, access key and Telegram.

## Known limitations

- `zigma.set_no_go_zone` is experimental. The meaning of the `restriction` flags is guessed from the web UI. Test with care.
- The robot runs schedules only in their scheduled minute. There is no "run now" for schedules.
- Setting entities appear only if the robot reports them in `/api/settings`.
- The integration is an early version and has not been tested on every robot variant.

## Development

- Python package: `custom_components/zigma/`
- Translations: English and German (`translations/`)

## Credits

The robot control software and the investigation of the robot are the work of [bultza](https://github.com/bultza/zigma-spark-980-free).

## License

MIT, see [LICENSE](LICENSE).
