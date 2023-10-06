# Written by FACTS Engineering
# Copyright (c) 2023 FACTS Engineering, LLC
# Licensed under the MIT license.
"""
`AT24MAC_EEPROM`
================================================================================

AT24MACx02 EEPROM Library

Provides an interface to read and write from EEPROM memory
as well as retrieve the unique MAC Address and serial number

Compatible with AT24MAC402 and AT24MAC602 devices using I2C

* Author(s): Adam Cummick, Tristan Warder
"""

import time
from adafruit_bus_device.i2c_device import I2CDevice
from micropython import const

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/facts-engineering/CircuitPython_AT24MAC_EEPROM.git"

_EEPROM_LENGTH = const(256)  # bytes
_PAGE_SIZE = const(16)
_WRITE_TIME = 0.005

_EUI_LOCATION = b"\x9A"
_MAC_ADDR_LENGTH = const(6)

# Uncomment for AT24MAC602 with EUI64 8 byte MAC Address
# _EUI_LOCATION = b'\x98'
# _MAC_ADDR_LENGTH = const(8)

_SERIAL_NUMBER_LOCATION = b"\x80"
_SERIAL_NUMBER_LENGTH = const(16)


class AT24MAC:
    """Class to interface with EEPROM device"""

    def __init__(self, i2c, address_pins=0b100):
        self.eeprom_device = I2CDevice(i2c, 0x50 | address_pins, True)
        self.eui_device = I2CDevice(i2c, 0x58 | address_pins, True)
        self.mac = self.read_mac_address()
        self.serial_number = self.read_serial_number()

    def read_serial_number(self):
        """Reads the unique serial number for the Device"""
        serial_number = bytearray(_SERIAL_NUMBER_LENGTH)

        with self.eui_device as device:
            device.write_then_readinto(_SERIAL_NUMBER_LOCATION, serial_number)
            serial_number = int.from_bytes(serial_number, "big")

        return serial_number

    def read_mac_address(self):
        """Reads the 6 byte mac address from the
        AT24MAC402 device
        """
        mac_address = bytearray(_MAC_ADDR_LENGTH)

        with self.eui_device as device:
            device.write_then_readinto(_EUI_LOCATION, mac_address)

        return mac_address

    def __getitem__(self, address):
        if isinstance(address, int):
            return self._read(address)
        if isinstance(address, slice):
            if address.start is not None:
                start = address.start
                if (start < 0) or (start >= _EEPROM_LENGTH):
                    raise ValueError("Start Address goes beyond memory limit")
            else:
                start = 0
            if address.stop is not None:
                stop = address.stop
                if (stop < 0) or (stop >= _EEPROM_LENGTH):
                    raise ValueError("Stop Address goes beyond memory limit")
            else:
                stop = _EEPROM_LENGTH
            length = stop - start
            return self._read(start, length)

        raise ValueError("Item must be integer or slice")

    def __setitem__(self, address, data):
        if isinstance(address, int):
            self._write(address, data)
        elif isinstance(address, slice):
            if address.start is not None:
                start = address.start
                if (start < 0) or (start >= _EEPROM_LENGTH):
                    raise ValueError("Start Address goes beyond memory limit")
            else:
                start = 0
            if address.stop is not None:
                stop = address.stop
                if (stop < 0) or (stop >= _EEPROM_LENGTH):
                    raise ValueError("Stop Address goes beyond memory limit")
            else:
                stop = _EEPROM_LENGTH

            self._write(start, data)
        else:
            raise ValueError("Item must be integer or slice")

    def __len__(self):
        return _EEPROM_LENGTH

    def _read(self, data_address, length=1):
        """Reads data back from EEPROM at specified address
        length defaults to 1, but can be specified
        data is returned as bytearray
        """
        if (length + data_address) > _EEPROM_LENGTH:
            raise ValueError(
                f"Data address {data_address} and length {length} go beyond memory limit"
            )

        data_bytes = bytearray(length)
        data_address = data_address.to_bytes(1, "big")

        with self.eeprom_device as device:
            device.write_then_readinto(data_address, data_bytes)

        if length > 1:
            return data_bytes

        return data_bytes[0]

    def _write(self, data_address, data):
        """writes a byte or bytearray to device at specified address
        data length is determined by bytearray passed in. Data is compared to
        the current page before writing to preserve EEPROM life.
        When writing larger than 1 page, memory is only checked page by page
        """
        if not isinstance(data, (bytearray, bytes)):
            try:
                if 0x00 <= data <= 0xFF:
                    data = data.to_bytes(1, "big")
            except TypeError:
                data = bytearray(data)

        if (len(data) + data_address) > _EEPROM_LENGTH:
            raise ValueError(
                f"Data address {data_address} and length {len(data)} go beyond memory limit"
            )

        if len(data) > 1:
            total_pages = int(len(data) / _PAGE_SIZE)
            remaining_bytes = len(data) % _PAGE_SIZE
            offset = _PAGE_SIZE - (data_address % _PAGE_SIZE)
            if offset == 16:
                offset = 0
            remaining_bytes -= offset
        else:
            offset = 0
            total_pages = 0
            remaining_bytes = 1

        current_address = data_address
        if offset > 0:
            self._write_page(data_address, data[0:offset])
            current_address += offset
        if total_pages > 0:
            for i in range(offset, total_pages * _PAGE_SIZE, _PAGE_SIZE):
                this_page = data[i : i + _PAGE_SIZE]
                self._write_page(current_address, this_page)
                current_address += _PAGE_SIZE
        if remaining_bytes > 0:
            self._write_page(current_address, data[offset + total_pages * _PAGE_SIZE :])

    def _write_page(self, data_address, data):
        """Writes a single page to eeprom. Data is compared to current data
        before writing to extend EEPROM life. Delay cycle is included for write
        latency
        """

        if not self._does_data_match(data_address, data):
            data_address = data_address.to_bytes(1, "big")
            data_message = data_address + data

            with self.eeprom_device as device:
                device.write(data_message)
                time.sleep(_WRITE_TIME)

    def _does_data_match(self, data_address, data):
        """Compares data passed in with the data at the specified address"""

        current_values = self._read(data_address, len(data))
        if len(data) == 1:
            current_values = bytes([current_values])
        return current_values == data
