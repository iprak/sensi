# Summary

This integration allows displaying and controlling [Sensi](https://sensi.emerson.com/en-us) thermostat.

It was developed by reverse engineering the mobile app and work done by https://github.com/w1ll1am23/pysensi, so the integration could fail at some point.

On adding the Sensi integration, you should see one device and 3 entities. You will need credentials used in the Sensi mobile app.

![image](https://github.com/iprak/sensi/assets/6459774/68044f83-222a-469c-9738-cf2d365e79ec)


- Only single target temperature is supported; temperature range is not supported. You will have to set heat/cool mode yourself.
- Supported fan modes are: Auto, On and Circulate (10% duty cycle). Not all Sensi thermostats support circulation mode and the option will be unavailable in that case.
- Data is refreshed every 30 seconds.
- Some Thermostat display properties such as Display Humidity, Display Time and Continuous Backlight can also be controlled. Not all thermostats support Continuous Backlight feature and the option will be unavailable in that case.
- If the thermostat is Offline, the operations will have no effect.

Sample attributes on the climate entity:

- hvac_modes: auto, cool, heat, off
- min_temp: 45
- max_temp: 99
- fan_modes: auto, on
- current_temperature: 75
- temperature: 84
- current_humidity: 62
- fan_mode: auto
- offline: false
- wifi_connection_quality: 30
- hvac_action: null
- circulating_fan: off
- circulating_fan_cuty_cycle: 30
- attribution: Data provided by Sensi
- friendly_name: Living Room

# Issues

So far, simultaneous logins from mobile app and integration have not been probematic. But it has been noticed that sometimes changing thermostat properties does not take effect, this could be either due to something going on at Sensi backend or the thermostat temporarily going offline.

# Installation

- Download and copy all the files from `custom_components/sensi/` to `<config directory>/custom_components/sensi/`.
- Restart HomeAssistant.
- Create an account on the Sensi mobile app.
- Add the integration using the `Add Integration` button in Integrations page on your Home Assistant instance.

# Configuration

None

# Breaking Changes

## Revision 1.1.1
The battery level is now computed based on a formula. It is not perfect but should give some idea of the battery state. The battery voltage itself is now available as an attribute. You will see a warning like The unit of `sensor.sensi_36_6f_92_ff_fe_02_24_b7_battery (%) cannot be converted to the unit of previously compiled statistics (V).`

## Revision 1.1.0

The entity ids have changed to support multiple thermostats on the same account. Your previous entities would appear duplicate/disabled. You would want to remove the integration and add it back.
