#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Place tests for the connector specific methods here.
"""
import os
import json
import unittest
from unittest.mock import MagicMock
import threading

import pytest

from ..main import Connector, __version__


class TestReceiveRawMsg(unittest.TestCase):
    pass


class TestParseRawMsg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charge_stations = {
            "test_1": "localhost",
            "test_2": "127.0.0.1",
        }
        os.environ["KEBA_P30_CHARGE_STATIONS"] = json.dumps(cls.charge_stations)

        # This is required to ensure the connector class can be created:
        os.environ["POLL_SECONDS"] = "10"
        os.environ["MQTT_BROKER_HOST"] = "locahost"
        os.environ["MQTT_BROKER_PORT"] = "1883"

    def test_raw_message_parses_to_dict_from_dict(self):
        """
        Verify that the incoming strings from KEBA are parsed to the expected
        full blown dict from dict strture.
        """
        test_raw_msg = {
            "payload": {
                "raw_message": {
                    "p30_aussen": {
                        "report 1": '{\n"ID": "1",\n"Product": "KC-P30-ES240022-E0R",\n"Serial": "17643683",\n"Firmware":"P30 v 3.9.10 (171113-103030)",\n"COM-module": 0,\n"Backend": 0,\n"timeQ": 2,\n"Sec": 67399365\n}\n',
                        "report 2": '{\n"ID": "2",\n"State": 1,\n"Error1": 0,\n"Error2": 0,\n"Plug": 0,\n"AuthON": 0,\n"Authreq": 0,\n"Enable sys": 0,\n"Enable user": 0,\n"Max curr": 0,\n"Max curr %": 1000,\n"Curr HW": 0,\n"Curr user": 16000,\n"Curr FS": 0,\n"Tmo FS": 0,\n"Curr timer": 0,\n"Tmo CT": 0,\n"Setenergy": 0,\n"Output": 0,\n"Input": 0,\n"Serial": "17643683",\n"Sec": 67399365\n}\n',
                        "report 3": '{\n"ID": "3",\n"U1": 0,\n"U2": 0,\n"U3": 0,\n"I1": 0,\n"I2": 0,\n"I3": 0,\n"P": 0,\n"PF": 0,\n"E pres": 330130,\n"E total": 4781461,\n"Serial": "17643683",\n"Sec": 67399365\n}\n',
                    }
                },
                "timestamp": 1628238571551,
            }
        }

        expected_parsed_msg = {
            "payload": {
                "parsed_message": {
                    "p30_aussen": {
                        "report 1": {
                            "ID": "1",
                            "Product": "KC-P30-ES240022-E0R",
                            "Serial": "17643683",
                            "Firmware": "P30 v 3.9.10 (171113-103030)",
                            "COM-module": 0,
                            "Backend": 0,
                            "timeQ": 2,
                            "Sec": 67399365,
                        },
                        "report 2": {
                            "ID": "2",
                            "State": 1,
                            "Error1": 0,
                            "Error2": 0,
                            "Plug": 0,
                            "AuthON": 0,
                            "Authreq": 0,
                            "Enable sys": 0,
                            "Enable user": 0,
                            "Max curr": 0,
                            "Max curr %": 1000,
                            "Curr HW": 0,
                            "Curr user": 16000,
                            "Curr FS": 0,
                            "Tmo FS": 0,
                            "Curr timer": 0,
                            "Tmo CT": 0,
                            "Setenergy": 0,
                            "Output": 0,
                            "Input": 0,
                            "Serial": "17643683",
                            "Sec": 67399365,
                        },
                        "report 3": {
                            "ID": "3",
                            "U1": 0,
                            "U2": 0,
                            "U3": 0,
                            "I1": 0,
                            "I2": 0,
                            "I3": 0,
                            "P": 0,
                            "PF": 0,
                            "E pres": 330130,
                            "E total": 4781461,
                            "Serial": "17643683",
                            "Sec": 67399365,
                        },
                    }
                },
                "timestamp": 1628238571551,
            }
        }

        connector = Connector(version=__version__)
        actual_parsed_msg = connector.parse_raw_msg(raw_msg=test_raw_msg)
        assert actual_parsed_msg == expected_parsed_msg


class TestSendCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charge_stations = {
            "test_1": "localhost",
            "test_2": "127.0.0.1",
        }
        os.environ["KEBA_P30_CHARGE_STATIONS"] = json.dumps(cls.charge_stations)

        # This is required to ensure the connector class can be created:
        os.environ["POLL_SECONDS"] = "10"
        os.environ["MQTT_BROKER_HOST"] = "locahost"
        os.environ["MQTT_BROKER_PORT"] = "1883"

    def test_valid_commands_are_send(self):
        """
        Verify that valid value messages addressing implemented datapoints
        are send on socket.
        """
        # All these message should be valid.
        test_value_msgs = [
            # datapoint_key, datapoint_value
            ["test_1__ena", "1"],
            ["test_1__curr", "36000"],
            ["test_1__setenergy", "100000"],
            ["test_1__display", "0 0 0 0 Test$Msg"],
        ]

        cn = Connector(version=__version__)
        for datapoint_key, datapoint_value in test_value_msgs:
            cn.keba_socket = MagicMock()
            cn.send_command(
                datapoint_key=datapoint_key, datapoint_value=datapoint_value
            )

            keba_command = datapoint_key.split("__")[-1]
            expected_send_to_args = (
                (keba_command + " " + datapoint_value).encode(),
                (self.charge_stations["test_1"], 7090),
            )
            assert cn.keba_socket.sendto.called
            actual_send_to_args = cn.keba_socket.sendto.mock_calls[-1].args
            assert actual_send_to_args == expected_send_to_args


class TestInit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charge_stations = {
            "test_1": "localhost",
            "test_2": "127.0.0.1",
        }
        os.environ["KEBA_P30_CHARGE_STATIONS"] = json.dumps(cls.charge_stations)

        # This is required to ensure the connector class can be created:
        os.environ["POLL_SECONDS"] = "10"
        os.environ["MQTT_BROKER_HOST"] = "locahost"
        os.environ["MQTT_BROKER_PORT"] = "1883"

    def test_locks_created(self):
        """
        We require one lock per configured charge station. Check that these
        are created as expected.
        """
        cn = Connector(version=__version__)
        for expceted_charge_station_name in self.charge_stations:
            assert expceted_charge_station_name in cn.keba_p30_locks
            actual_lock = cn.keba_p30_locks[expceted_charge_station_name]
            assert isinstance(actual_lock, type(threading.Lock()))

    def test_actuator_datapoints_included(self):
        """
        Verifies that the compute_actuator_datapoints method is called and the
        result is used by the connector.
        """
        expected_available_datapoints = {
            "sensor": {},
            "actuator": {"test": "0"},
        }
        # This MagicMock applies for the unintialized class and affects
        # all subsequent tests too. We must undo it afterwards.
        cad_backup = Connector.compute_actuator_datapoints
        Connector.compute_actuator_datapoints = MagicMock(
            return_value=expected_available_datapoints["actuator"]
        )

        cn = Connector(version=__version__)
        actual_available_datapoints = cn._initial_available_datapoints
        Connector.compute_actuator_datapoints = cad_backup
        assert actual_available_datapoints == expected_available_datapoints


class TestComputeActuatorDatapoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charge_stations = {
            "test_1": "localhost",
            "test_2": "127.0.0.1",
        }
        os.environ["KEBA_P30_CHARGE_STATIONS"] = json.dumps(cls.charge_stations)

        # This is required to ensure the connector class can be created:
        os.environ["POLL_SECONDS"] = "10"

    def test_actuator_datapoints_content_as_expected(self):
        """
        Verify that the expected values for the key_in_connector and
        example_value fields are returned.
        """
        cn = Connector(version=__version__)
        expected_actuator_datapoints = {
            "test_1__ena": "0",
            "test_1__curr": "63000",
            "test_1__setenergy": "100000",
            "test_1__display": "0 0 0 0 Hello$KEBA",
            "test_2__ena": "0",
            "test_2__curr": "63000",
            "test_2__setenergy": "100000",
            "test_2__display": "0 0 0 0 Hello$KEBA",
        }
        actual_actuator_datapoints = cn.compute_actuator_datapoints(
            self.charge_stations
        )
        assert actual_actuator_datapoints == expected_actuator_datapoints
