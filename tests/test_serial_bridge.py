"""V-PR100 시리얼 브리지 회귀 테스트."""

import unittest
from unittest.mock import patch

from serial_bridge import (
    BinaryRadarParser,
    BridgeConfig,
    DEFAULT_PUBLISH_INTERVAL,
    LatestMessageBuffer,
    RadarInputParser,
    RadarParser,
    adjust_presence_score,
    resolve_serial_port,
)


class RadarParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = RadarParser(
            BridgeConfig(
                room=401,
                location="거실A",
                presence_threshold=1000,
                presence_off_threshold=700,
                confirmation_count=2,
                absence_timeout=5,
                motion_hold=2,
            )
        )

    def test_reassembles_fragmented_presence_line(self) -> None:
        self.assertEqual(
            self.parser.feed(b"<info> app: Presence score: 23", now=10),
            [],
        )
        messages = self.parser.feed(b"38, Distance: 600\r\n", now=10)
        self.assertEqual(len(messages), 1)
        self.assertFalse(messages[0]["status"])
        messages = self.parser.feed(
            b"<info> app: Presence score: 2100, Distance: 620\n",
            now=10.1,
        )
        self.assertTrue(messages[0]["status"])
        self.assertEqual(messages[0]["presence_score"], 2100)
        self.assertEqual(messages[0]["distance_mm"], 620)
        self.assertEqual(messages[0]["distance_m"], 0.62)

    def test_motion_does_not_create_presence(self) -> None:
        message = self.parser.feed(b"<info> app: Motion\n", now=10)[0]
        self.assertFalse(message["status"])
        self.assertTrue(message["motion"])

    def test_applies_offset_only_below_score_limit(self) -> None:
        parser = RadarParser(
            BridgeConfig(
                room=401,
                location="거실A",
                presence_threshold=1000,
                presence_off_threshold=700,
                confirmation_count=2,
                absence_timeout=5,
                motion_hold=2,
                presence_score_offset=500,
                presence_score_offset_limit=3300,
                presence_score_high_offset=500,
            )
        )
        first = parser.feed(
            b"<info> app: Presence score: 2600, Distance: 300\n",
            now=10,
        )[0]
        self.assertEqual(first["presence_score"], 2100)
        high = parser.feed(
            b"<info> app: Presence score: 3300, Distance: 300\n",
            now=10.1,
        )[0]
        self.assertEqual(high["presence_score"], 3800)

    def test_confirmed_presence_times_out(self) -> None:
        self.parser.feed(
            b"<info> app: Presence score: 1800, Distance: 1000\n",
            now=10,
        )
        self.parser.feed(
            b"<info> app: Presence score: 1750, Distance: 1020\n",
            now=10.1,
        )
        self.assertIsNone(self.parser.timeout_message(now=15))
        timeout = self.parser.timeout_message(now=15.1)
        self.assertIsNotNone(timeout)
        self.assertFalse(timeout["status"])
        self.assertFalse(timeout["motion"])
        self.assertEqual(timeout["reason"], "timeout")

    def test_explicit_absence_clears_distance(self) -> None:
        self.parser.feed(
            b"<info> app: Presence score: 1800, Distance: 1200\n",
            now=10,
        )
        message = self.parser.feed(b"<info> app: No Presence\n", now=11)[0]
        self.assertFalse(message["status"])
        self.assertEqual(message["presence_score"], 0)
        self.assertIsNone(message["distance_mm"])

    def test_unrecognized_log_is_ignored(self) -> None:
        self.assertEqual(self.parser.feed(b"<info> app: Boot complete\n"), [])

    def test_hysteresis_ignores_small_score_dip(self) -> None:
        self.parser.feed(
            b"<info> app: Presence score: 1800, Distance: 1000\n",
            now=10,
        )
        self.parser.feed(
            b"<info> app: Presence score: 1750, Distance: 1000\n",
            now=10.1,
        )
        message = self.parser.feed(
            b"<info> app: Presence score: 800, Distance: 1000\n",
            now=10.2,
        )[0]
        self.assertTrue(message["status"])
        message = self.parser.feed(
            b"<info> app: Presence score: 600, Distance: 1000\n",
            now=10.3,
        )[0]
        self.assertFalse(message["status"])

class LatestMessageBufferTest(unittest.TestCase):
    def test_default_publish_interval_is_two_hundred_milliseconds(self) -> None:
        self.assertEqual(DEFAULT_PUBLISH_INTERVAL, 0.2)

    def test_publishes_only_latest_message_every_half_second(self) -> None:
        publisher = LatestMessageBuffer(interval=0.5, now=10)
        publisher.push([{"value": 1}])
        self.assertEqual(publisher.pop_due(now=10), {"value": 1})
        publisher.push([{"value": 2}, {"value": 3}])
        self.assertIsNone(publisher.pop_due(now=10.49))
        self.assertEqual(publisher.pop_due(now=10.5), {"value": 3})


class BinaryRadarParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BridgeConfig(
            room=401,
            location="거실A",
            presence_threshold=1000,
            presence_off_threshold=700,
            confirmation_count=2,
            absence_timeout=5,
            motion_hold=2,
        )

    def test_reassembles_official_presence_packet(self) -> None:
        parser = BinaryRadarParser(self.config)
        self.assertEqual(parser.feed(bytes.fromhex("02 01 01 00")), [])
        messages = parser.feed(bytes.fromhex("00 04 A2 03"))
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0]["status"])
        self.assertEqual(messages[0]["presence_score"], 1186)
        self.assertEqual(messages[0]["module_id"], 1)
        self.assertIsNone(messages[0]["distance_mm"])

    def test_applies_configured_score_offset_and_clamps_at_zero(self) -> None:
        adjusted_config = BridgeConfig(
            room=401,
            location="거실A",
            presence_threshold=1000,
            presence_off_threshold=700,
            confirmation_count=2,
            absence_timeout=5,
            motion_hold=2,
            presence_score_offset=500,
            presence_score_offset_limit=3300,
            presence_score_high_offset=500,
        )
        parser = BinaryRadarParser(adjusted_config)
        messages = parser.feed(
            bytes.fromhex(
                "02 02 01 00 00 0A 28 00 00 01 2C 03 "
                "02 02 00 00 00 01 2C 00 00 00 00 03"
            )
        )
        self.assertEqual(
            [message["presence_score"] for message in messages],
            [2100, 0],
        )

    def test_resynchronizes_after_noise_and_parses_absence(self) -> None:
        parser = BinaryRadarParser(self.config)
        messages = parser.feed(
            bytes.fromhex("99 AA 02 01 FF 00 00 00 00 03 02 01 00 00 00 00 00 03")
        )
        self.assertEqual(len(messages), 1)
        self.assertFalse(messages[0]["status"])
        self.assertEqual(messages[0]["presence_score"], 0)
        self.assertEqual(messages[0]["reason"], "serial_absence")

    def test_reassembles_distance_packet_from_real_sensor(self) -> None:
        parser = BinaryRadarParser(self.config)
        self.assertEqual(parser.feed(bytes.fromhex("02 02 01 00 00 0B")), [])
        messages = parser.feed(bytes.fromhex("61 00 00 03 48 03"))
        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0]["status"])
        self.assertEqual(messages[0]["module_id"], 2)
        self.assertEqual(messages[0]["presence_score"], 2913)
        self.assertEqual(messages[0]["distance_mm"], 840)
        self.assertEqual(messages[0]["distance_m"], 0.84)

    def test_distance_value_containing_stx_byte_does_not_break_framing(self) -> None:
        parser = BinaryRadarParser(self.config)
        messages = parser.feed(
            bytes.fromhex(
                "02 02 01 00 00 09 A8 00 00 02 58 03 "
                "02 02 01 00 00 09 A0 00 00 02 D0 03"
            )
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(
            [message["distance_mm"] for message in messages], [600, 720]
        )

    def test_auto_detects_binary_and_text_protocols(self) -> None:
        binary = RadarInputParser(self.config, "auto")
        binary_messages = binary.feed(
            bytes.fromhex("02 02 01 00 00 12 5B 03")
        )
        self.assertEqual(binary.selected_protocol, "binary")
        self.assertEqual(binary_messages[0]["presence_score"], 4699)

        text = RadarInputParser(self.config, "auto")
        text_messages = text.feed(
            b"<info> app: Presence score: 2000, Distance: 720\n"
        )
        self.assertEqual(text.selected_protocol, "text")
        self.assertEqual(text_messages[0]["distance_mm"], 720)


class SerialPortResolutionTest(unittest.TestCase):
    class Port:
        def __init__(self, device: str, description: str) -> None:
            self.device = device
            self.description = description
            self.vid = None
            self.pid = None

    def test_explicit_port_is_preserved(self) -> None:
        self.assertEqual(resolve_serial_port("/dev/cu.custom"), "/dev/cu.custom")

    @patch("serial_bridge.serial.tools.list_ports.comports")
    def test_pl2303_port_is_selected_automatically(self, comports) -> None:
        comports.return_value = [
            self.Port("/dev/cu.usbmodem1101", "XIAO ESP32S3"),
            self.Port("/dev/cu.PL2303G-USBtoUART10", "USB-Serial Controller"),
        ]
        self.assertEqual(
            resolve_serial_port(None), "/dev/cu.PL2303G-USBtoUART10"
        )

    @patch("serial_bridge.serial.tools.list_ports.comports")
    def test_linux_ttyusb_port_is_selected_automatically(self, comports) -> None:
        comports.return_value = [
            self.Port("/dev/ttyACM0", "XIAO ESP32S3"),
            self.Port("/dev/ttyUSB0", "USB-Serial Controller"),
        ]
        self.assertEqual(resolve_serial_port(None), "/dev/ttyUSB0")


class PresenceScoreAdjustmentTest(unittest.TestCase):
    def test_subtracts_offset_and_clamps_at_zero(self) -> None:
        self.assertEqual(adjust_presence_score(2600, 500), 2100)
        self.assertEqual(adjust_presence_score(300, 500), 0)

    def test_preserves_scores_at_or_above_limit(self) -> None:
        self.assertEqual(adjust_presence_score(3299, 500, 3300), 2799)
        self.assertEqual(adjust_presence_score(3300, 500, 3300, 500), 3800)
        self.assertEqual(adjust_presence_score(4200, 500, 3300, 500), 4700)


if __name__ == "__main__":
    unittest.main()
