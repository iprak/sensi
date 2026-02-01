"""Tests for Sensi switch component."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.sensi.client import ActionResponse
from custom_components.sensi.const import CONFIG_AUX_HEATING, CONFIG_FAN_SUPPORT
from custom_components.sensi.data import OperatingMode
from custom_components.sensi.event import SettingEventName
from custom_components.sensi.switch import (
    SWITCH_TYPES,
    SensiAuxHeatSwitch,
    SensiCapabilityEntityDescription,
    SensiCapabilitySettingSwitch,
    SensiFanSupportSwitch,
    SensiHumidificationSwitch,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntries
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant


def create_humidity_description() -> SensiCapabilityEntityDescription:
    """Create SensiCapabilityEntityDescription."""
    return SensiCapabilityEntityDescription(
        key="display_humidity",
        setting=SettingEventName.DISPLAY_HUMIDITY,
        name="Display Humidity",
        icon="mdi:water-percent",
    )


async def test_setup_platform(
    hass: HomeAssistant,
    mock_entry,
    mock_coordinator,
    mock_device,
    mock_device_with_humidification,
) -> None:
    """Test platform setup."""

    mock_coordinator.get_devices = MagicMock(
        return_value=[mock_device, mock_device_with_humidification]
    )

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_entry, async_add_entities)

    assert async_add_entities.called

    # 6 = 4 from SWITCH_TYPES + SensiFanSupportSwitch + SensiAuxHeatSwitch
    # 7 = 4 from SWITCH_TYPES + SensiFanSupportSwitch + SensiAuxHeatSwitch + SensiHumidificationSwitch
    assert len(async_add_entities.call_args[0][0]) == 13


def test_capability_entity_description_creation() -> None:
    """Test creating a SensiCapabilityEntityDescription."""
    desc = create_humidity_description()
    assert desc.key == "display_humidity"
    assert desc.setting == SettingEventName.DISPLAY_HUMIDITY
    assert desc.name == "Display Humidity"
    assert desc.icon == "mdi:water-percent"
    assert desc.entity_category == EntityCategory.CONFIG


class TestSwitchTypes:
    """Test cases for SWITCH_TYPES configuration."""

    @pytest.mark.parametrize(
        ("key", "setting"),
        [
            ("display_humidity", SettingEventName.DISPLAY_HUMIDITY),
            ("continuous_backlight", SettingEventName.CONTINUOUS_BACKLIGHT),
            ("display_time", SettingEventName.DISPLAY_TIME),
            ("keypad_lockout", SettingEventName.KEYPAD_LOCKOUT),
        ],
    )
    def test_switch_type_exists(self, key, setting):
        """Test switch entity value type."""
        switches = [s for s in SWITCH_TYPES if s.key == key]
        assert len(switches) == 1
        assert switches[0].setting == setting

    def test_switch_types_with_icons(self) -> None:
        """Test that switches have appropriate icons."""
        icons_expected = {
            "display_humidity": "mdi:water-percent",
            "continuous_backlight": "mdi:wall-sconce-flat",
            "display_time": "mdi:clock",
            "keypad_lockout": "mdi:lock",
        }
        for key, expected_icon in icons_expected.items():
            switch = next(s for s in SWITCH_TYPES if s.key == key)
            assert switch.icon == expected_icon


class TestSensiCapabilitySettingSwitch:
    """Test cases for SensiCapabilitySettingSwitch."""

    def test_capability_setting_switch_initialization(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test SensiCapabilitySettingSwitch initialization."""

        description = create_humidity_description()

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        assert switch._device == mock_device
        assert switch.entity_description == description
        assert switch.coordinator == mock_coordinator

    def test_capability_setting_switch_is_on(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test is_on property returns correct state."""

        mock_device.state.display_humidity = True
        description = create_humidity_description()

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        assert switch.is_on is True

    def test_capability_setting_switch_is_off(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test is_on property when switch is off."""

        mock_device.state.display_humidity = False
        description = create_humidity_description()

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        assert switch.is_on is False

    def test_capability_setting_switch_display_time(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test display_time switch."""

        mock_device.state.display_time = True

        description = SensiCapabilityEntityDescription(
            key="display_time",
            setting=SettingEventName.DISPLAY_TIME,
            name="Display Time",
        )

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        assert switch.is_on is True

    def test_capability_setting_switch_keypad_lockout(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test keypad_lockout switch."""

        mock_device.state.keypad_lockout = False

        description = SensiCapabilityEntityDescription(
            key="keypad_lockout",
            setting=SettingEventName.KEYPAD_LOCKOUT,
            name="Keypad Lockout",
        )

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        assert switch.is_on is False

    def test_capability_setting_switch_continuous_backlight(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test continuous_backlight switch."""

        mock_device.state.continuous_backlight = True

        description = SensiCapabilityEntityDescription(
            key="continuous_backlight",
            setting=SettingEventName.CONTINUOUS_BACKLIGHT,
            name="Continuous Backlight",
        )

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        assert switch.is_on is True

    async def test_capability_setting_switch_continuous_backlight_update(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test update of continuous_backlight switch."""

        mock_device.state.continuous_backlight = True

        description = SensiCapabilityEntityDescription(
            key="continuous_backlight",
            setting=SettingEventName.CONTINUOUS_BACKLIGHT,
            name="Continuous Backlight",
        )

        switch = SensiCapabilitySettingSwitch(
            mock_device, description, mock_coordinator
        )

        with (
            patch.object(
                mock_coordinator.client, "_async_invoke_setter"
            ) as mock_async_set_bool_setting,
            patch.object(switch, "async_write_ha_state") as mock_async_write_ha_state,
        ):
            mock_async_set_bool_setting.return_value = ActionResponse(None, {})

            # First turn off and then back on
            await switch.async_turn_off()
            mock_async_write_ha_state.assert_called_once()
            assert switch.is_on is False

            mock_async_write_ha_state.reset_mock()
            await switch.async_turn_on()
            mock_async_write_ha_state.assert_called_once()
            assert switch.is_on is True


class TestSensiAuxHeatSwitch:
    """Test cases for SensiAuxHeatSwitch."""

    def test_aux_heat_switch_initialization(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test SensiAuxHeatSwitch initialization."""

        switch = SensiAuxHeatSwitch(mock_device, mock_coordinator)

        assert switch._device == mock_device
        assert switch.coordinator == mock_coordinator
        assert switch.entity_description.key == CONFIG_AUX_HEATING

    def test_aux_heat_switch_available_when_capable(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test available property when aux heating is capable."""

        mock_device.capabilities.operating_mode_settings.aux = True
        switch = SensiAuxHeatSwitch(mock_device, mock_coordinator)

        assert switch.available is True

    def test_aux_heat_switch_unavailable_when_not_capable(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test available property when aux heating is not capable."""

        mock_device.capabilities.operating_mode_settings.aux = False
        switch = SensiAuxHeatSwitch(mock_device, mock_coordinator)

        assert switch.available is False

    @pytest.mark.parametrize(
        ("operating_mode", "expected"),
        [
            (OperatingMode.HEAT, False),
            (OperatingMode.COOL, False),
            (OperatingMode.OFF, False),
            (OperatingMode.AUX, True),
        ],
    )
    def test_aux_heat_switch_is_off_when_heat_mode(
        self, mock_device, mock_coordinator, operating_mode, expected
    ) -> None:
        """Test is_on property when operating mode is HEAT (not AUX)."""

        mock_device.state.operating_mode = operating_mode
        switch = SensiAuxHeatSwitch(mock_device, mock_coordinator)

        assert switch.is_on == expected

    def test_aux_heat_switch_stores_previous_mode(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test that previous operating mode is stored."""

        mock_device.state.operating_mode = OperatingMode.HEAT
        switch = SensiAuxHeatSwitch(mock_device, mock_coordinator)

        assert switch._last_operating_mode_before_aux_heat == OperatingMode.HEAT


class TestSensiFanSupportSwitch:
    """Test cases for SensiFanSupportSwitch."""

    def test_fan_support_switch_initialization(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test SensiFanSupportSwitch initialization."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiFanSupportSwitch(mock_device, entry, mock_coordinator)

        assert switch._device == mock_device
        assert switch.coordinator == mock_coordinator
        assert switch.entity_description.key == CONFIG_FAN_SUPPORT

    def test_fan_support_switch_entity_category(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test that fan support switch has CONFIG category."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiFanSupportSwitch(mock_device, entry, mock_coordinator)

        assert switch.entity_description.entity_category == EntityCategory.CONFIG

    def test_fan_support_switch_icon(self, mock_device, mock_coordinator) -> None:
        """Test that fan support switch has correct icon."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiFanSupportSwitch(mock_device, entry, mock_coordinator)

        assert switch.entity_description.icon == "mdi:fan-off"

    async def test_fan_support_switch_update(
        self, mock_entry, mock_device, mock_coordinator
    ) -> None:
        """Test update of fan support switch."""

        hass = mock_coordinator.hass
        hass.config_entries = ConfigEntries(hass, {})
        switch = SensiFanSupportSwitch(mock_device, mock_entry, mock_coordinator)
        switch.hass = hass  # we are not creating the entire structure so let us directly define hass

        with (
            patch.object(hass.config_entries, "async_update_entry"),
            patch.object(switch, "async_write_ha_state") as mock_async_write_ha_state,
        ):
            # First turn off and then back on
            await switch.async_turn_off()
            mock_async_write_ha_state.assert_called_once()
            assert switch.is_on is False

            mock_async_write_ha_state.reset_mock()
            await switch.async_turn_on()
            mock_async_write_ha_state.assert_called_once()
            assert switch.is_on is True


class TestSensiHumidificationSwitch:
    """Test cases for SensiHumidificationSwitch."""

    def test_humidification_switch_initialization(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test SensiHumidificationSwitch initialization."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiHumidificationSwitch(mock_device, entry, mock_coordinator)

        assert switch._device == mock_device
        assert switch.coordinator == mock_coordinator

    def test_humidification_switch_is_on_when_enabled(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test is_on property when humidification is enabled."""

        mock_device.state.humidity_control.humidification.enabled = True

        entry = MagicMock()
        entry.options = {}
        switch = SensiHumidificationSwitch(mock_device, entry, mock_coordinator)

        assert switch.is_on is True

    def test_humidification_switch_is_off_when_disabled(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test is_on property when humidification is disabled."""

        mock_device.state.humidity_control.humidification.enabled = False

        entry = MagicMock()
        entry.options = {}
        switch = SensiHumidificationSwitch(mock_device, entry, mock_coordinator)

        assert switch.is_on is False

    def test_humidification_switch_entity_category(
        self, mock_device, mock_coordinator
    ) -> None:
        """Test that humidification switch has CONFIG category."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiHumidificationSwitch(mock_device, entry, mock_coordinator)

        assert switch.entity_description.entity_category == EntityCategory.CONFIG

    def test_humidification_switch_icon(self, mock_device, mock_coordinator) -> None:
        """Test that humidification switch has correct icon."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiHumidificationSwitch(mock_device, entry, mock_coordinator)

        assert switch.entity_description.icon == "mdi:air-humidifier"

    def test_humidification_switch_name(self, mock_device, mock_coordinator) -> None:
        """Test that humidification switch has correct name."""

        entry = MagicMock()
        entry.options = {}
        switch = SensiHumidificationSwitch(mock_device, entry, mock_coordinator)

        assert switch.entity_description.name == "Humidification"

    async def test_humidification_switch_update(
        self, mock_entry, mock_device_with_humidification, mock_coordinator
    ) -> None:
        """Test update of humidification switch."""

        switch = SensiHumidificationSwitch(
            mock_device_with_humidification, mock_entry, mock_coordinator
        )
        with (
            patch.object(
                mock_coordinator.client, "_async_invoke_setter"
            ) as mock_async_update_humidification,
            patch.object(switch, "async_write_ha_state") as mock_async_write_ha_state,
            patch.object(
                mock_coordinator, "async_update_listeners"
            ) as mock_async_update_listeners,
        ):
            mock_async_update_humidification.return_value = ActionResponse(None, {})

            # First turn off and then back on
            await switch.async_turn_off()
            mock_async_write_ha_state.assert_called_once()
            mock_async_update_listeners.assert_called_once()
            assert switch.is_on is False

            mock_async_write_ha_state.reset_mock()
            mock_async_update_listeners.reset_mock()

            await switch.async_turn_on()
            mock_async_write_ha_state.assert_called_once()
            mock_async_update_listeners.assert_called_once()
            assert switch.is_on is True
