# https://github.com/flrrth/pico-dht20

from machine import I2C
from utime import sleep_ms


class DHT20:
    """Class for the DHT20 Temperature and Humidity Sensor.

    The datasheet can be found at http://www.aosong.com/userfiles/files/media/Data%20Sheet%20DHT20%20%20A1.pdf
    """

    _ADDRESS = 0x38

    def __init__(self, i2c: I2C):
        self._i2c = i2c
        self._temperature = None
        self._humidity = None
        sleep_ms(100)

        if not self.is_ready:
            self._initialize()
            sleep_ms(100)

            if not self.is_ready:
                raise RuntimeError("Could not initialize the DHT20.")

    @property
    def is_ready(self) -> bool:
        """Check if the DHT20 is ready."""
        return self._i2c.readfrom(self._ADDRESS, 1)[0] & 0x18 == 0x18

    @property
    def temperature(self) -> float:
        """Last measured temperature in °C, or None before the first measure()."""
        return self._temperature

    @property
    def humidity(self) -> float:
        """Last measured relative humidity in %RH, or None before the first measure()."""
        return self._humidity

    def measure(self) -> dict:
        """Trigger a measurement and return the results as a dictionary.

        't': temperature (°C),
        't_adc': the 'raw' temperature as produced by the ADC,
        'rh': relative humidity (%RH),
        'rh_adc': the 'raw' relative humidity as produced by the ADC,
        'crc_ok': indicates if the data was received correctly
        """
        self._trigger_measurements()
        sleep_ms(80)

        data = self._read_measurements()
        retry = 3

        while not data[1]:
            if not retry:
                raise RuntimeError("Could not read measurements from the DHT20.")

            sleep_ms(10)
            data = self._read_measurements()
            retry -= 1

        buffer = data[0]
        s_rh = buffer[1] << 12 | buffer[2] << 4 | buffer[3] >> 4
        s_t = (buffer[3] << 16 | buffer[4] << 8 | buffer[5]) & 0xfffff
        self._humidity = (s_rh / 2 ** 20) * 100
        self._temperature = ((s_t / 2 ** 20) * 200) - 50
        crc_ok = self._crc_check(buffer[:6], buffer[6])

        return {
            't': self._temperature,
            't_adc': s_t,
            'rh': self._humidity,
            'rh_adc': s_rh,
            'crc_ok': crc_ok
        }

    def _initialize(self):
        buffer = bytearray(b'\x00\x00')
        self._i2c.writeto_mem(self._ADDRESS, 0x1B, buffer)
        self._i2c.writeto_mem(self._ADDRESS, 0x1C, buffer)
        self._i2c.writeto_mem(self._ADDRESS, 0x1E, buffer)

    def _trigger_measurements(self):
        self._i2c.writeto_mem(self._ADDRESS, 0xAC, bytearray(b'\x33\x00'))

    def _read_measurements(self):
        buffer = self._i2c.readfrom(self._ADDRESS, 7)
        return buffer, buffer[0] & 0x80 == 0

    def _crc_check(self, data: bytes, check_value: int) -> bool:
        """Verify CRC-8 (polynomial 0x31, initial value 0xFF) over data bytes."""
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc << 1) ^ 0x31 if crc & 0x80 else crc << 1
                crc &= 0xFF
        return crc == check_value
