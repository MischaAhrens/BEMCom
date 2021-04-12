#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"""
import os
import json
import logging

from dotenv import load_dotenv, find_dotenv
from pyconnector_template.pyconector_template import SensorFlow as SFTemplate
from pyconnector_template.pyconector_template import ActuatorFlow as AFTemplate
from pyconnector_template.pyconector_template import Connector as CTemplate
from pyconnector_template.dispatch import DispatchInInterval


logger = logging.getLogger("pyconnector")


class SensorFlow(SFTemplate):
    """
    Bundles all functionality to handle sensor messages.

    This is a template for a SensorFlow class, i.e. one that holds all
    functions that are necessary to handle messages from the device(s)
    towards the message broker. The methods could also be implemented
    into the Connector class, but are seperated to support clarity.

    Overload these functions
    ------------------------
    In order to transform this class into operational code you need
    to inherit from it and overload the following methods:
     - receive_raw_msg
     - parse_raw_msg

    Connector Methods
    -----------------
    The connector must provide the following methods to allow correct
    operation of the methods in this class:
     - _update_available_datapoints

    Connector Attributes
    --------------------
    The following attributes must be set up by the connector to
    allow these methods to run correctly:

    mqtt_client : class instance.
        Initialized Mqtt client library with signature of paho mqtt.
    SEND_RAW_MESSAGE_TO_DB : string
        if SEND_RAW_MESSAGE_TO_DB == "TRUE" will send raw message
        to designated DB via MQTT.
    MQTT_TOPIC_RAW_MESSAGE_TO_DB : string
        The topic which on which the raw messages will be published.
    datapoint_map : dict of dict.
        Mapping from datapoint key to topic. Is generated by the AdminUI.
        Looks e.e. like this:
            datapoint_map = {
                "sensor": {
                    "Channel__P__value__0": "example-connector/msgs/0001",
                    "Channel__P__unit__0": "example-connector/msgs/0002",
                },
                "actuator": {
                    "example-connector/msgs/0003": "Channel__P__setpoint__0",
                }
            }
        Note thereby that the keys "sensor" and "actuator"" must alaways be
        present, even if the child dicts are empty.
    """

    def receive_raw_msg(self, raw_data=None):
        """
        Functionality to receive a raw message from device.

        Poll the device/gateway for data and transforms this raw data
        into the format epxected by run_sensor_flow. If the device/gateway
        uses some protocol that pushes data, the raw data should be passed
        as the raw_data argument to the function.

        Parameters
        ----------
        raw_data : TYPE, optional
            Raw data of device/gateway if the device pushes and is not
            pulled for data. The default is None.

        Returns
        -------
        msg : dict
            The message object containing the raw unprocessed data.
            Should be formated like this:
                msg = {
                    "payload": {
                        "raw_message": <the raw data>
                    }
                }
            E.g.
                msg = {
                    "payload": {
                        "raw_message": "device_1:{sensor_1:2.12,sensor_2:3.12}"
                    }
                }
        """
        raise NotImplementedError("receive_raw_msg has not been implemented.")

    def parse_raw_msg(self, raw_msg):
        """
        Functionality to receive a raw message from device.

        Poll the device/gateway for data and transforms this raw data
        into the format epxected by run_sensor_flow. If the device/gateway
        uses some protocol that pushes data, the raw data should be passed
        as the raw_data argument to the function.

        Be aware: All keys in the output message should be strings. All values
        should be converted be strings, too.

        Parameters
        ----------
        raw_msg : dict.
            Raw msg with data from device/gateway. Should be formated like:
                msg = {
                    "payload": {
                        "raw_message": <the raw data>,
                        "timestamp": <milliseconds since epoch>
                    }
                }

        Returns
        -------
        msg : dict
            The message object containing the parsed data as python dicts from
            dicts strucuture.
            Should be formated like this:
                msg = {
                    "payload": {
                        "parsed_message": <the parsed data as object>,
                        "timestamp": <milliseconds since epoch>
                    }
                }
            E.g:
                msg = {
                    "payload": {
                        "parsed_message": {
                            "device_1": {
                                "sensor_1": "2.12",
                                "sensor_2": "3.12"
                            }
                        },
                        "timestamp": 1573680749000
                    }
                }
        """
        raise NotImplementedError("parse_raw_msg has not been implemented.")


class ActuatorFlow(AFTemplate):
    """
    Bundles all functionality to handle actuator messages.

    This is a template for a ActuatorFlow class, i.e. one that holds all
    functions that are necessary to handle messages from the message
    broker towards the devices/gateway. The methods could also be implemented
    into the Connector class, but are seperated to support clarity.

    Overload these functions
    ------------------------
    In order to transform this class into operational code you need
    to inherit from it and overload the following methods:
     - send_command

    Connector Attributes
    --------------------
    The following attributes must be set up by the connector to
    allow these methods to run correctly:

    datapoint_map : dict of dict.
        Mapping from datapoint key to topic. Is generated by the AdminUI.
        Looks e.e. like this:
            datapoint_map = {
                "sensor": {
                    "Channel__P__value__0": "example-connector/msgs/0001",
                    "Channel__P__unit__0": "example-connector/msgs/0002",
                },
                "actuator": {
                    "example-connector/msgs/0003": "Channel__P__setpoint__0",
                }
            }
        Note thereby that the keys "sensor" and "actuator"" must alaways be
        present, even if the child dicts are empty.
    """

    def send_command(self, datapoint_key, datapoint_value):
        """
        Send message to target device, via gateway if applicable.

        Parameters
        ----------
        datapoint_key : string.
            The internal key that is used by device/gateway to identify
            the datapoint.
        value : string.
            The value that should be sent to the datapoint.
        """
        raise NotImplementedError("send_command has not been implemented.")


class Connector(CTemplate, SensorFlow, ActuatorFlow):
    """
    The generic logic of the connector.

    It should not be necessary to overload any of these methods nor
    to call any of those apart from __init__() and run().

    Configuration Attributes
    ------------------------
    Confiugration will be populated from environment variables on init.
    CONNECTOR_NAME : string
        The name of the connector instance as seen by the AdminUI.
    MQTT_TOPIC_LOGS : string
        The topics used by the log handler to publish log messages on.
    MQTT_TOPIC_HEARTBEAT : string
        The topics used by the connector to publish heartbeats on.
    MQTT_TOPIC_AVAILABLE_DATAPOINTS : string
        The topic on which the available datapoints will be published.
    MQTT_TOPIC_DATAPOINT_MAP : string
        The topic the connector will listen on for datapoint maps
    SEND_RAW_MESSAGE_TO_DB : string
        if SEND_RAW_MESSAGE_TO_DB == "TRUE" will send raw message
        to designated DB via MQTT. This is a string and not a bool as
        environment variables are always strings.
    MQTT_TOPIC_RAW_MESSAGE_TO_DB : string
        The topic which on which the raw messages will be published.
    DEBUG : string
        if DEBUG == "TRUE" will log debug message to, elso loglevel is info.

    Computed Attributes
    -------------------
    These attriubutes are created by init and are then dynamically used
    by the Connector.
    mqtt_client : class instance.
        Initialized Mqtt client library with signature of paho mqtt.
    available_datapoints : dict of dict.
        Lists all datapoints known to the connector and is sent to the
        AdminUI. Actuator datapoints must be specified manually. Sensor
        datapoints are additionally automatically added once a value for
        a new datapoint is received. The object contains the connector
        internal key and a sample and value looks e.g. like this:
            available_datapoints = {
                "sensor": {
                    "Channel__P__value__0": 0.122,
                    "Channel__P__unit__0": "kW",
                },
                "actuator": {
                    "Channel__P__setpoint__0": 0.4,
                }
            }
    datapoint_map : dict of dict.
        Mapping from datapoint key to topic. Is generated by the AdminUI.
        Looks e.e. like this:
            datapoint_map = {
                "sensor": {
                    "Channel__P__value__0": "example-connector/msgs/0001",
                    "Channel__P__unit__0": "example-connector/msgs/0002",
                },
                "actuator": {
                    "example-connector/msgs/0003": "Channel__P__setpoint__0",
                }
            }
        Note thereby that the keys "sensor" and "actuator"" must alaways be
        present, even if the child dicts are empty.
    """

    def __init__(self, *args, **kwargs):
        """
        Init the inherited code from python_connector_template and add
        connector specific code, like parsing additional environment variables
        or specifying actuator datapoints.
        """
        # dotenv allows us to load env variables from .env files which is
        # convient for developing. If you set override to True tests
        # may fail as the tests assume that the existing environ variables
        # have higher priority over ones defined in the .env file.
        load_dotenv(find_dotenv(), verbose=True, override=False)

        # We need to specify a dispatcher that triggers the connection with
        # the device or gateway. Here we want to poll the device with the
        # interval set in the POLL_SECONDS environment variable.
        # At each poll we want to execute the full run_sensor_flow
        # As this contains all the expected logic the connector should do
        # with sensor data.
        kwargs["DeviceDispatcher"] = DispatchInInterval
        kwargs["device_dispatcher_kwargs"] = {
            "call_interval": float(os.getenv("POLL_SECONDS")),
            "target_func": self.run_sensor_flow,
        }

        # Sensor datapoints will be added to available_datapoints automatically
        # once they are first appear in run_sensor_flow method. It is thus not
        # necessary to specify them here. actuator datapoints in contrast must
        # be specified here.
        kwargs["available_datapoints"] = {
            "sensor": {},
            "actuator": {}
        }
        CTemplate.__init__(self, *args, **kwargs)

        self.custom_env_var = os.getenv("CUSTOM_ENV_VARR") or "default_value"


if __name__ == "__main__":
    connector = Connector()
    connector.run()
