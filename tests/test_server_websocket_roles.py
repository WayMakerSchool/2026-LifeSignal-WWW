"""센서와 대시보드 WebSocket 역할 분리 회귀 테스트."""

from __future__ import annotations

import unittest

import server


class FakeWebSocket:
    def __init__(self, *, closed: bool = False) -> None:
        self.closed = closed
        self.messages: list[str] = []

    async def send_str(self, message: str) -> None:
        self.messages.append(message)


class ServerWebSocketRoleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.original_connected = server.connected_clients
        self.original_dashboards = server.dashboard_clients
        self.original_latest = server.latest_sensor_states
        server.connected_clients = set()
        server.dashboard_clients = set()
        server.latest_sensor_states = {}

    def tearDown(self) -> None:
        server.connected_clients = self.original_connected
        server.dashboard_clients = self.original_dashboards
        server.latest_sensor_states = self.original_latest

    def test_recognizes_dashboard_subscription(self) -> None:
        self.assertTrue(
            server.is_dashboard_subscription(
                '{"type":"subscribe","role":"dashboard"}'
            )
        )
        self.assertFalse(
            server.is_dashboard_subscription(
                '{"type":"radar_data","sensor":"C4001"}'
            )
        )

    async def test_subscription_receives_latest_sensor_states(self) -> None:
        dashboard = FakeWebSocket()
        server.latest_sensor_states = {
            "vpr100:401:거실A": "vpr100-latest",
            "c4001:401:방A": "c4001-latest",
        }

        await server.subscribe_dashboard(dashboard)  # type: ignore[arg-type]

        self.assertIn(dashboard, server.dashboard_clients)
        self.assertEqual(
            dashboard.messages,
            ["vpr100-latest", "c4001-latest"],
        )

    async def test_processed_data_is_sent_only_to_dashboards(self) -> None:
        sensor_a = FakeWebSocket()
        sensor_b = FakeWebSocket()
        dashboard = FakeWebSocket()
        server.connected_clients.update(  # type: ignore[arg-type]
            {sensor_a, sensor_b, dashboard}
        )
        server.dashboard_clients.add(dashboard)  # type: ignore[arg-type]

        await server.broadcast_to_dashboards("processed")

        self.assertEqual(dashboard.messages, ["processed"])
        self.assertEqual(sensor_a.messages, [])
        self.assertEqual(sensor_b.messages, [])


if __name__ == "__main__":
    unittest.main()
