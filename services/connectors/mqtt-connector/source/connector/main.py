#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"""
__version__ = "0.6.0"

import os
import ssl
import json
import logging
from tempfile import NamedTemporaryFile

from paho.mqtt.client import Client, connack_string
from dotenv import load_dotenv, find_dotenv
from pyconnector_template.pyconnector_template import SensorFlow as SFTemplate
from pyconnector_template.pyconnector_template import ActuatorFlow as AFTemplate
from pyconnector_template.pyconnector_template import Connector as CTemplate
from pyconnector_template.dispatch import DispatchOnce


logger = logging.getLogger("pyconnector")


class SensorFlow(SFTemplate):
    """
    Bundles all functionality to handle sensor messages.

    This is a template for a SensorFlow class, i.e. one that holds all
    functions that are necessary to handle messages from the device(s)
    towards the message broker. The methods could also be implemented
    into the Connector class, but are separated to support clarity.

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
        Initialized Mqtt client library with signature of paho MQTT.
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
        into the format expected by run_sensor_flow. If the device/gateway
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
            The message object containing the raw data. It must be
            JSON serializable (to allow sending the raw_message object as JSON
            object to the raw message DB). If the data received from the device
            or gateway cannot be packed to JSON directly (like e.g. for bytes)
            it must modified accordingly. Avoid manipulation of the data as much
            as possible, to prevent data losses when these operations fail.
            A simple solution may often be to cast the raw data to strings.
            Dict structures are fine, especially if created in this function,
            e.g. by iterating over many endpoints of one device.
            Should be formatted like this:
                msg = {
                    "payload": {
                        "raw_message": <raw data in JSON serializable form>
                    }
                }
            E.g.
                msg = {
                    "payload": {
                        "raw_message": "device_1:{sensor_1:2.12,sensor_2:3.12}"
                    }
                }
        """
        msg = {
            "payload": {
                "raw_message": {
                    "topic": raw_data.topic,
                    "payload": raw_data.payload.decode(),
                }
            }
        }
        return msg

    def parse_raw_msg(self, raw_msg):
        """
        Parses the values from the raw_message.

        This parses the raw_message into an object (in a JSON meaning, a
        dict in Python). The resulting object can be nested to allow
        representation of hierarchical data.

        Be aware: All keys in the output message should be strings. All values
        must be convertable to JSON.

        Parameters
        ----------
        raw_msg : dict.
            Raw msg with data from device/gateway. Should be formatted like:
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
            dicts structure. All keys should be strings. All value should be
            of type string, bool or numbers. Should be formatted like this:
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
                                "sensor_1": "test",
                                "sensor_2": 3.12,
                                "sensor_2": True,
                            }
                        },
                        "timestamp": 1573680749000
                    }
                }
        """
        mqtt_topic = raw_msg["payload"]["raw_message"]["topic"]
        mqtt_payload = raw_msg["payload"]["raw_message"]["payload"]
        timestamp = raw_msg["payload"]["timestamp"]

        if self.parse_sensor_msgs_as_json:
            try:
                mqtt_payload = json.loads(mqtt_payload)
            except json.decoder.JSONDecodeError:
                logger.warning(
                    "Could not parse mqtt_payload as JSON although REMOTE_MQTT_"
                    "BROKER_PARSE_JSON is set to TRUE. MQTT topic was: %s. "
                    "MQTT payload was: %s",
                    *(mqtt_topic, mqtt_payload)
                )

        msg = {
            "payload": {
                "parsed_message": {mqtt_topic: mqtt_payload},
                "timestamp": timestamp,
            }
        }
        return msg


class ActuatorFlow(AFTemplate):
    """
    Bundles all functionality to handle actuator messages.

    This is a template for a ActuatorFlow class, i.e. one that holds all
    functions that are necessary to handle messages from the message
    broker towards the devices/gateway. The methods could also be implemented
    into the Connector class, but are separated to support clarity.

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
        Note thereby that the keys "sensor" and "actuator"" must always be
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
    REMOTE_MQTT_BROKER_HOST : string
        The DNS name or IP address of the remote MQTT broker.
    REMOTE_MQTT_BROKER_PORT : int as string
        The port of the remote MQTT broker.
    REMOTE_MQTT_BROKER_USE_TLS : string
        If == "TRUE" (i.e. the string), will use TLS to encrypt the connection.
    REMOTE_MQTT_BROKER_CA_FILE : string
        A CA certificate (full chain) in pem format. If provided will use this
        CA certificate to verify that server certificate.
    REMOTE_MQTT_BROKER_USERNAME : string
        If not empty will try to login at the remote broker with this username.
    REMOTE_MQTT_BROKER_PASSWORD : string
        If not empty (and username not empty) will try to login at the remote
        broker with this password.
    REMOTE_MQTT_BROKER_TOPIC_MAPPING : json string.
        A json string defining which topics should be forwarded to which
        datapoints. See Readme.md for details.
    REMOTE_MQTT_BROKER_PARSE_JSON : string
        If == "TRUE" (i.e. the string), will try to parse the payload of the
        message received from the remote broker as JSON.

    Computed Attributes
    -------------------
    These attributes are created by init and are then dynamically used
    by the Connector.
    mqtt_client : class instance.
        Initialized MQTT client library with signature of paho mqtt.
    remote_mqtt_client : class instance.
        Similar to the one above but for the remote MQTT broker.
    parse_sensor_msgs_as_json : bool
        Corresponds to REMOTE_MQTT_BROKER_PARSE_JSON, see above.
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
        Note thereby that the keys "sensor" and "actuator"" must always be
        present, even if the child dicts are empty.
    """

    def __init__(self, *args, RemoteMqttClient=Client, **kwargs):
        """
        Init the inherited code from python_connector_template and add
        connector specific code, like parsing additional environment variables
        or specifying actuator datapoints.
        """
        # dotenv allows us to load env variables from .env files which is
        # convenient for developing. If you set override to True tests
        # may fail as the tests assume that the existing environ variables
        # have higher priority over ones defined in the .env file.
        load_dotenv(find_dotenv(), verbose=True, override=False)

        topic_mapping = self.parse_topic_mapping()

        self.parse_sensor_msgs_as_json = False
        if os.getenv("REMOTE_MQTT_BROKER_PARSE_JSON") == "TRUE":
            self.parse_sensor_msgs_as_json = True

        # Configure the dispatcher to start the connection to the
        # remote broker on connector startup. This is very similar to the
        # handling of the internal MQTT client in CTemplate.run
        self.remote_mqtt_client = self.create_remote_mqtt_client(
            topic_mapping=topic_mapping, RemoteMqttClient=RemoteMqttClient,
        )
        kwargs["DeviceDispatcher"] = DispatchOnce
        kwargs["device_dispatcher_kwargs"] = {
            "target_func": self.remote_mqtt_worker,
            "target_kwargs": {"mqtt_client": self.remote_mqtt_client},
        }

        # Sensor datapoints will be added to available_datapoints automatically
        # once they are first appear in run_sensor_flow method. It is thus not
        # necessary to specify them here. Actuator datapoints are parsed from
        # REMOTE_MQTT_BROKER_TOPIC_MAPPING
        actuator_datapoints = self.compute_actuator_datapoints(
            topic_mapping=topic_mapping,
        )
        kwargs["available_datapoints"] = {
            "sensor": {},
            "actuator": actuator_datapoints,
        }
        CTemplate.__init__(self, *args, **kwargs)

    def parse_topic_mapping(self):
        """
        Parses topic_mapping from REMOTE_MQTT_BROKER_TOPIC_MAPPING.

        Returns:
        ----------
        topic_mapping : dict
            The parsed content of REMOTE_MQTT_BROKER_TOPIC_MAPPING like this:
            topic_mapping = {
                "sensor_topics": <list of topic strings>
                "actuator_topics":
            }

        Raises:
        -------
        ValueError:
            If the REMOTE_MQTT_BROKER_TOPIC_MAPPING is not a valid JSON or
            does not contain the expected content.
        """
        try:
            topic_mapping = json.loads(os.getenv("REMOTE_MQTT_BROKER_TOPIC_MAPPING"))
        except json.decoder.JSONDecodeError:
            raise ValueError(
                "REMOTE_MQTT_BROKER_TOPIC_MAPPING is not a valid JSON string. "
                "REMOTE_MQTT_BROKER_TOPIC_MAPPING was: %s"
                % os.getenv("REMOTE_MQTT_BROKER_TOPIC_MAPPING")
            )

        # To prevent malfunction because of typos etc. we always expect
        # the sensor_topics and actuator_topics to be present.
        if "sensor_topics" not in topic_mapping:
            raise ValueError(
                "Expected key sensor_topics in REMOTE_MQTT_BROKER_TOPIC_"
                "MAPPING but got instead:\n%s" % json.dumps(topic_mapping, indent=4)
            )
        if "actuator_topics" not in topic_mapping:
            raise ValueError(
                "Expected key actuator_topics in REMOTE_MQTT_BROKER_TOPIC_"
                "MAPPING but got instead:\n%s" % json.dumps(topic_mapping, indent=4)
            )

        return topic_mapping

    @staticmethod
    def _handle_remote_mqtt_msg(client, userdata, msg):
        """
        Handle incoming mqtt message by calling the appropriate method.

        Arguments
        ---------
        client : client : class.
            Initialized Mqtt client library with signature of paho mqtt.
        userdata : dict.
            Must contain {"self": <connector class>}.
        msg : paho mqtt message class.
            The message to handle.
        """
        self = userdata["self"]
        logger.debug(
            "Handling incoming MQTT message from remote broker on topic: %s", msg.topic
        )
        if msg.retain == 0:
            self.run_sensor_flow(raw_data=msg)
        else:
            logger.debug("Skipping retained message for topic: %s", msg.topic)

    @staticmethod
    def on_remote_connect(client, userdata, flags, rc):
        """
        Check the connection is successful and subscribe to topics then.

        Raises:
        -------
        RuntimeError:
            If the connection failed.
        """
        if rc == 0:
            logger.info(
                "Connection to remote MQTT broker (%s:%s) successful",
                *(
                    os.getenv("REMOTE_MQTT_BROKER_HOST"),
                    os.getenv("REMOTE_MQTT_BROKER_PORT"),
                )
            )
            topic_mapping = userdata["topic_mapping"]
            # Subscribe to configured topics with QOS=2, we want to receive
            # all messages exactly once.
            for topic in topic_mapping["sensor_topics"]:
                logger.info("Subscribing to topic on remote broker: %s", topic)
                client.subscribe(topic, qos=2)

        else:
            # See here
            connack_string(rc)
            raise RuntimeError(
                "Connection to remote MQTT broker (%s:%s) failed. Error was: %s"
                % (
                    os.getenv("REMOTE_MQTT_BROKER_HOST"),
                    os.getenv("REMOTE_MQTT_BROKER_PORT"),
                    connack_string(rc),
                )
            )

    def create_remote_mqtt_client(self, topic_mapping, RemoteMqttClient):
        """
        Initiates the mqtt client for the remote broker.

        Apart from topic_mapping all settings are directly parsed from
        environment variables as these are used in no other part of the
        connector.

        Arguments:
        ----------
        topic_mapping : dict
            The parsed content of REMOTE_MQTT_BROKER_TOPIC_MAPPING
        RemoteMqttClient : class.
            Uninitialized MQTT client library with signature of paho mqtt.
            Defaults to paho.mqtt.client.Client. Providing other clients
            is mostly useful for testing.

        Used environment variables:
        ---------------------------
        REMOTE_MQTT_BROKER_HOST : string
            The DNS name or IP address of the remote MQTT broker.
        REMOTE_MQTT_BROKER_PORT : int as string
            The port of the remote MQTT broker.
        REMOTE_MQTT_BROKER_USE_TLS : string
            If == "TRUE" (i.e. the string), will use TLS to encrypt the
            connection.
        REMOTE_MQTT_BROKER_CA_FILE : string
            A CA certificate (full chain) in pem format. If provided will use
            this CA certificate to verify that server certificate.
        REMOTE_MQTT_BROKER_USERNAME : string
            If not empty will try to login at the remote broker with this
            username.
        REMOTE_MQTT_BROKER_PASSWORD : string
            If not empty (and username not empty) will try to login at the
            remote broker with this password.

        Returns:
        --------
        remote_mqtt_client : instance of MqttClient
            The instance of MqttClient configured according to the environment
            variables.
        """
        logger.info("Configuring remote MQTT connection.")
        userdata = {
            "self": self,
            "topic_mapping": topic_mapping,
        }
        remote_mqtt_client = RemoteMqttClient(userdata=userdata)
        remote_mqtt_client.on_message = self._handle_remote_mqtt_msg
        remote_mqtt_client.on_connect = self.on_remote_connect

        if os.getenv("REMOTE_MQTT_BROKER_USE_TLS") == "TRUE":
            logger.info("Using TLS to encrypt connection.")

            ca_file_fnp = None
            ca_content = os.getenv("REMOTE_MQTT_BROKER_CA_FILE")
            if ca_content:
                logger.info("Using CA file to check server certificate.")
                # Save the pem content to a file because paho mqtt expectes
                # a file path.
                with NamedTemporaryFile(mode="w", delete=False) as ca_file:
                    ca_file.write(ca_content)
                    ca_file.close()
                ca_file_fnp = ca_file.name
                # remote_mqtt_client.tls_set(ca_file.name, cert_reqs=ssl.CERT_NONE)
                # remote_mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            # This will not verify the server certificate if ca_file_fnp is
            # None. This is insecure but will work with self signed certs.
            remote_mqtt_client.tls_set(ca_file_fnp)

        username = os.getenv("REMOTE_MQTT_BROKER_USERNAME")
        if username:
            logger.info("Using username %s for remote broker.", username)
            password = os.getenv("REMOTE_MQTT_BROKER_PASSWORD")
            if password is not None:
                logger.info(
                    "Using password with length %s for remote broker", len(password)
                )
            remote_mqtt_client.username_pw_set(username, password)

        logger.info(
            "Connecting to remote MQTT broker (%s:%s).",
            *(
                os.getenv("REMOTE_MQTT_BROKER_HOST"),
                os.getenv("REMOTE_MQTT_BROKER_PORT"),
            )
        )
        remote_mqtt_client.connect(
            host=os.getenv("REMOTE_MQTT_BROKER_HOST"),
            port=int(os.getenv("REMOTE_MQTT_BROKER_PORT")),
        )
        return remote_mqtt_client

    def compute_actuator_datapoints(self, topic_mapping):
        """
        Computes the actuator part of the available_datapoints message based
        on the topic_mapping.

        Here we use the topics as unique key_in_connector fields, as these
        must be unique anyway and represent the datapoint the best.

        Arguments:
        ----------
        topic_mapping : dict
            The parsed content of REMOTE_MQTT_BROKER_TOPIC_MAPPING

        Returns:
        --------
        actuator_datapoints : dict
            See BEMCom message format.
        """
        actuator_datapoints = {}
        actuator_topics = topic_mapping["actuator_topics"]
        for topic in actuator_topics:
            example_value = actuator_topics[topic]["example_value"]
            actuator_datapoints[topic] = example_value
        return actuator_datapoints

    @staticmethod
    def remote_mqtt_worker(mqtt_client):
        """
        Similar to mqtt_worker in CTemplate.run
        """
        logger.debug("Starting client loop for remote MQTT client.")
        try:
            mqtt_client.loop_forever()
        finally:
            # Gracefully terminate connection once the main program exits.
            mqtt_client.disconnect()


if __name__ == "__main__":
    connector = Connector(version=__version__)
    connector.run()
