# Summary

This integration allows displaying and controlling [Sensi](https://sensi.emerson.com/en-us) thermostat.

It was developed by reverse engineering the mobile app and work done by https://github.com/w1ll1am23/pysensi, so the integration could fail at some point.

On adding the Sensi integration, you should see one device and 3 entities. You will need credentials used in the Sensi mobile app.

- Only single target temperature is supported; temperature range is not supported. You will have to set heat/cool mode yourself.
- Suported fan modes are: Auto, On and Circulate (10% duty cycle)
- Data is refreshed every 30 seconds.

So far, simultaneous loging from mobile app and integration does not seem to be probematic.

# Installation

- Download and copy all the files from `custom_components/sensi/` to `<config directory>/custom_components/sensi/`.
- Restart HomeAssistant.
- Create an account on the Sensi mobile app.
- Add the integration using the `Add Integration` button in Integrations page on your Home Assistant instance.

# Configuration

None
