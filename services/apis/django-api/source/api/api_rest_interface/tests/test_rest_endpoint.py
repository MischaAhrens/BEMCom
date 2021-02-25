"""
Here tests for the functionality provided by the REST endpoint, that is
functionality provided by the REST Api that a client must request. These
tests here are end to end. Additional details, like e.g. field checking are
covered in the tests of the serializers.
"""
import os
import json
import time
from unittest import TestCase

import pytest
from rest_framework.test import APIClient
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType

from api_main.connector_mqtt_integration import ConnectorMQTTIntegration
from api_main.tests.helpers import connector_factory, datapoint_factory
from api_main.tests.fake_mqtt import FakeMQTTBroker, FakeMQTTClient
from api_main.models.datapoint import DatapointValue, DatapointSchedule
from api_main.models.datapoint import DatapointSetpoint
from ems_utils.timestamp import datetime_from_timestamp


@pytest.fixture(scope='class')
def rest_endpoint_setup(request, django_db_setup, django_db_blocker):
    """
    SetUp FakeMQTTBroker, ConnectorMQTTIntegration and APIClient for all
    tests targeting the API endpoints.

    This is significantly faster then using unittest's setUp and tearDown
    as those are executed for every test function, here only for the class
    as a whole.
    """
    # Allow access to the Test DB. See:
    # https://pytest-django.readthedocs.io/en/latest/database.html#django-db-blocker
    django_db_blocker.unblock()

    # This is not needed for the tests itself, but just to ensure that
    # adding datapoints and connectors succeeds.
    fake_broker = FakeMQTTBroker()
    fake_client_1 = FakeMQTTClient(fake_broker=fake_broker)
    fake_client_2 = FakeMQTTClient(fake_broker=fake_broker)
    cmi = ConnectorMQTTIntegration(
        mqtt_client=fake_client_1
    )

    # Setup MQTT client endpoints for test.
    mqtt_client = fake_client_2(userdata={})
    mqtt_client.connect('localhost', 1883)
    mqtt_client.loop_start()

    client = APIClient()
    user = User.objects.create_user(username='testuser', password='12345')
    test_connector = connector_factory("test_connector6")

    # Inject objects into test class.
    request.cls.test_connector = test_connector
    request.cls.mqtt_client = mqtt_client
    request.cls.client = client
    request.cls.user = user
    yield

    # Remove DB entries, as the restore command below does not seem to work.
    test_connector.delete()
    user.delete()

    # Close connections and objects.
    mqtt_client.disconnect()
    mqtt_client.loop_stop()
    cmi.disconnect()

    # Remove access to DB.
    django_db_blocker.block()
    django_db_blocker.restore()

@pytest.mark.usefixtures('rest_endpoint_setup')
class TestRESTEndpoint(TestCase):
    """
    Here all tests targeting for functionality triggered by the client.

    TODO: Add test to verify that only active datapoints are returned.
    TODO: Add permission checks for POST/DELETE/PUT endpoints, although this
          is not super crticial as all endpoints use the same permission
          setting/setup.
    """

    def setUp(self):
        """
        Reset the permissions and the permission cache.
        """
        self.user.user_permissions.clear()
        self.user = get_object_or_404(User, pk=self.user.id)
        self.client.force_authenticate(user=self.user)

    def test_get_datapoint_detail(self):
        """
        Request the data of one sensor datapoint from the REST API and
        check that the all expected fields are delivered.
        """
        dp = datapoint_factory(self.test_connector)
        dp.description = "A sensor datapoint for testing"
        dp.short_name = "test_sensor"
        dp.unit = "Test Unit"
        dp.allowed_values = '[1.0, 2.0]'
        dp.min_value = 1.0
        dp.max_value = 2.0
        dp.save()

        p = Permission.objects.get(codename="view_datapoint")
        self.user.user_permissions.add(p)
        request = self.client.get("/datapoint/%s/" % dp.id)
        expected_data = {
            "id": dp.id,
            "type": dp.type,
            "data_format": dp.data_format,
            "short_name": dp.short_name,
            "description": dp.description,
            "min_value": dp.min_value,
            "max_value": dp.max_value,
            "allowed_values": dp.allowed_values,
            "unit": dp.unit,
        }
        assert request.data == expected_data

    def test_get_datapoint_value_for_sensor(self):
        """
        Request the latest datapoint value msg and check that all expected
        fields are delivered.
        """
        expected_data = {
            "value": "last_value!",
            "timestamp": 1585092224000,
        }

        dp = datapoint_factory(self.test_connector)
        dp.save()
        dp_value = DatapointValue(
            datapoint = dp,
            value=expected_data["value"],
            timestamp=datetime_from_timestamp(expected_data["timestamp"]),
        )
        dp_value.save()

        p = Permission.objects.get(codename="view_datapointvalue")
        self.user.user_permissions.add(p)
        request = self.client.get(
            "/datapoint/%s/value/%s/" % (dp.id, expected_data["timestamp"])
        )

        assert request.data == expected_data

    def test_put_datapoint_value_detail_rejected_for_sensor(self):
        """
        Check that it is not possible to write sensor message from the client.

        This does not make sense, sensor messages should only be generated
        by the devices.
        """
        dp = datapoint_factory(self.test_connector)
        dp.save()

        p = Permission.objects.get(codename="add_datapointvalue")
        self.user.user_permissions.add(p)
        # Now put an update for the datapoint and check that the put was
        # denied as expected.
        update_msg = {
            "value": "last_value!",
            "timestamp": 1585092224000,
        }
        request = self.client.post(
            "/datapoint/%s/value/" % dp.id,
            update_msg,
            format='json'
        )
        # Exceptions when trying to create/update on sensor datapoints
        # trigger error code 400, in contrast to permission denied errors
        # if the user would't have permissions to access the data.
        assert request.status_code == 400

    def test_put_datapoint_value_detail_for_actuator(self):
        """
        Write (PUT) a value message, that should trigger that the corresponding
        message is sent to the message broker and after that also stored in the
        database, from which it should be readable as usual.

        This should by definition only be possible for actuators.
        """
        dp = datapoint_factory(self.test_connector, type="actuator")
        dp.save()

        p1 = Permission.objects.get(codename="add_datapointvalue")
        p2 = Permission.objects.get(codename="view_datapointvalue")
        self.user.user_permissions.set([p1, p2])

        # Subscribe to the MQTT topic of the datapoint so we can check if the
        # expected message was sent.
        def on_message(client, userdata, msg):
            """
            Store the received message so we can test it's correctness later.
            """
            client.userdata[msg.topic] = json.loads(msg.payload)

        dp_mqtt_value_topic = dp.get_mqtt_topics()["value"]
        self.mqtt_client.subscribe(dp_mqtt_value_topic)
        self.mqtt_client.on_message = on_message

        # Now put an update for the datapoint and check that the put was
        # successful.
        expected_msg = {
            "value": "updated_value!",
            "timestamp": 1585092224000,
        }
        request = self.client.post(
            "/datapoint/%s/value/" % dp.id,
            expected_msg,
            format='json'
        )
        assert request.status_code == 201

        # Check if the message has been sent. This might happen in async, so
        # we may have to wait a little. If this code fails, the fault likely
        # resides in the mqtt_integration.
        waited_seconds = 0
        while dp_mqtt_value_topic not in self.mqtt_client.userdata:
            time.sleep(0.005)
            waited_seconds += 0.005

            if waited_seconds >= 3:
                raise RuntimeError(
                    "Expected datapoint value message has not been published "
                    "on broker."
                )

        # Now that we know the message has been published on the broker,
        # verify it holds the expected information.
        assert self.mqtt_client.userdata[dp_mqtt_value_topic] == expected_msg

        # After the MQTT message has now arrived the updated value should now
        # be available on the REST interface. As above this might happen async,
        # hence we might give the message a bit time to arrive.
        waited_seconds = 0
        while True:
            dp.refresh_from_db()
            if dp.last_value == expected_msg["value"]:
                break

            time.sleep(0.005)
            waited_seconds += 0.005
            if waited_seconds >= 3:
                raise RuntimeError(
                    "Expected datapoint value message has not reached the DB."
                )

        request = self.client.get(
            "/datapoint/%s/value/%s/" % (dp.id, expected_msg["timestamp"])
        )
        assert request.data == expected_msg

    def test_put_datapoint_schedule_detail_rejected_for_sensor(self):
        """
        Check that a schedule detail cannot be written for a sensor, as
        this kind of message does only exist for actuators.
        """
        dp = datapoint_factory(self.test_connector)

        p = Permission.objects.get(codename="add_datapointschedule")
        self.user.user_permissions.add(p)

        update_msg = {
            "schedule":
                [
                    {
                        'from_timestamp': None,
                        'to_timestamp': 1564489613491,
                        'value': "21"
                    },
                    {
                        'from_timestamp': 1564489613491,
                        'to_timestamp': None,
                        'value': None
                    }
                ]
        }
        request = self.client.post(
            "/datapoint/%s/schedule/" % dp.id,
            update_msg,
            format='json'
        )

        assert request.status_code == 400

    def test_get_datapoint_schedule_detail_for_actuator(self):
        """
        Check that the schedule of an actuator is returend as expected.
        """
        expected_data = {
            "schedule": [
                {
                    'from_timestamp': None,
                    'to_timestamp': 1564489613491,
                    'value': "21"
                },
                {
                    'from_timestamp': 1564489613491,
                    'to_timestamp': None,
                    'value': None
                }
            ],
            "timestamp": 1564489613491,
        }
        dp = datapoint_factory(self.test_connector, type="actuator")
        dp.description = "A actuator datapoint for schedule testing."
        dp.save()

        dp_schedule = DatapointSchedule(
            datapoint = dp,
            schedule=expected_data["schedule"],
            timestamp=datetime_from_timestamp(expected_data["timestamp"]),
        )
        dp_schedule.save()

        p = Permission.objects.get(codename="view_datapointschedule")
        self.user.user_permissions.add(p)

        request = self.client.get(
            "/datapoint/%s/schedule/%s/" % (dp.id, expected_data["timestamp"])
        )

        assert request.data == expected_data

    def test_put_datapoint_schedule_detail_actuator(self):
        """
        Write (PUT) a schedule message, that should trigger that the
        corresponding message is sent to the message broker and after that also
        stored in the database, from which it should be readable as usual.

        This should by definition only be possible for actuators.
        """
        dp = datapoint_factory(self.test_connector, type="actuator")
        dp.save()

        p1 = Permission.objects.get(codename="add_datapointschedule")
        p2 = Permission.objects.get(codename="view_datapointschedule")
        self.user.user_permissions.set([p1, p2])

        # Subscribe to the MQTT topic of the datapoint so we can check if the
        # expected message was sent.
        def on_message(client, userdata, msg):
            """
            Store the received message so we can test it's correctness later.
            """
            client.userdata[msg.topic] = json.loads(msg.payload)

        dp_mqtt_schedule_topic = dp.get_mqtt_topics()["schedule"]
        self.mqtt_client.subscribe(dp_mqtt_schedule_topic)
        self.mqtt_client.on_message = on_message

        # Now put an update for the datapoint and check that the put was
        # successful.
        expected_msg = {
            "schedule":
                [
                    {
                        'from_timestamp': None,
                        'to_timestamp': 1564489613491,
                        'value': "21"
                    },
                    {
                        'from_timestamp': 1564489613491,
                        'to_timestamp': None,
                        'value': None
                    }
                ],
            "timestamp": 1585092224000,
        }
        request = self.client.post(
            "/datapoint/%s/schedule/" % dp.id,
            expected_msg,
            format='json'
        )
        assert request.status_code == 201

        # Check if the message has been sent. This might happen in async, so
        # we may have to wait a little. If this code fails, the fault likely
        # resides in the mqtt_integration.
        waited_seconds = 0
        while dp_mqtt_schedule_topic not in self.mqtt_client.userdata:
            time.sleep(0.005)
            waited_seconds += 0.005

            if waited_seconds >= 3:
                raise RuntimeError(
                    "Expected datapoint schedule message has not been "
                    "published on broker."
                )

        # Now that we know the message has been published on the broker,
        # verify it holds the expected information.
        received_msg = self.mqtt_client.userdata[dp_mqtt_schedule_topic]
        assert received_msg == expected_msg

        # After the MQTT message has now arrived the updated value should now
        # be available on the REST interface. As above this might happen async,
        # hence we might give the message a bit time to arrive.
        waited_seconds = 0
        while True:
            dp.refresh_from_db()
            if dp.last_schedule_timestamp is not None:
                break

            time.sleep(0.005)
            waited_seconds += 0.005
            if waited_seconds >= 3:
                raise RuntimeError(
                    "Expected datapoint schedule message has not reached the "
                    "DB."
                )

        request = self.client.get(
            "/datapoint/%s/schedule/%s/" % (dp.id, expected_msg["timestamp"])
        )
        assert request.data == expected_msg

    def test_put_datapoint_setpoint_detail_rejected_for_sensor(self):
        """
        Check that a setpoint detail cannot be written for a sensor, as
        this kind of message does only exist for actuators.
        """
        dp = datapoint_factory(self.test_connector)

        p = Permission.objects.get(codename="add_datapointsetpoint")
        self.user.user_permissions.add(p)

        update_msg = {
            "setpoint":
                [
                    {
                        'from_timestamp': None,
                        'to_timestamp': 1564489613491,
                        'preferred_value': "21",
                    },
                ]
        }
        request = self.client.post(
            "/datapoint/%s/setpoint/" % dp.id,
            update_msg,
            format='json'
        )

        assert request.status_code == 400

    def test_get_datapoint_setpoint_detail_for_actuator(self):
        """
        Check that the setpoint of an actuator is returend as expected.
        """
        expected_data = {
            "setpoint": [
                {
                    'from_timestamp': None,
                    'to_timestamp': 1564489613491,
                    'preferred_value': "21",
                },
                {
                    'from_timestamp': 1564489613491,
                    'to_timestamp': None,
                    'preferred_value': None,
                }
            ],
            "timestamp": 1564489613491,
        }
        dp = datapoint_factory(self.test_connector, type="actuator")
        dp.description = "A actuator datapoint for setpoint testing."
        dp.save()

        dp_setpoint = DatapointSetpoint(
            datapoint = dp,
            setpoint=expected_data["setpoint"],
            timestamp=datetime_from_timestamp(expected_data["timestamp"]),
        )
        dp_setpoint.save()

        p = Permission.objects.get(codename="view_datapointsetpoint")
        self.user.user_permissions.add(p)

        request = self.client.get(
            "/datapoint/%s/setpoint/%s/" % (dp.id, expected_data["timestamp"])
        )

        assert request.data == expected_data

    def test_put_datapoint_setpoint_detail_for_actuator(self):
        """
        Write (PUT) a setpoint message, that should trigger that the
        corresponding message is sent to the message broker and after that also
        stored in the database, from which it should be readable as usual.

        This should by definition only be possible for actuators.
        """
        dp = datapoint_factory(self.test_connector, type="actuator")
        dp.save()

        p1 = Permission.objects.get(codename="add_datapointsetpoint")
        p2 = Permission.objects.get(codename="view_datapointsetpoint")
        self.user.user_permissions.set([p1, p2])

        # Subscribe to the MQTT topic of the datapoint so we can check if the
        # expected message was sent.
        def on_message(client, userdata, msg):
            """
            Store the received message so we can test it's correctness later.
            """
            client.userdata[msg.topic] = json.loads(msg.payload)

        dp_mqtt_setpoint_topic = dp.get_mqtt_topics()["setpoint"]
        self.mqtt_client.subscribe(dp_mqtt_setpoint_topic)
        self.mqtt_client.on_message = on_message

        # Now put an update for the datapoint and check that the put was
        # successful.
        expected_msg = {
            "setpoint":
                [
                    {
                        'from_timestamp': None,
                        'to_timestamp': 1564489613491,
                        'preferred_value': "21",
                    },
                ],
            "timestamp": 1585092224000,
        }
        request = self.client.post(
            "/datapoint/%s/setpoint/" % dp.id,
            expected_msg,
            format='json'
        )
        assert request.status_code == 201

        # Check if the message has been sent. This might happen in async, so
        # we may have to wait a little. If this code fails, the fault likely
        # resides in the mqtt_integration.
        waited_seconds = 0
        while dp_mqtt_setpoint_topic not in self.mqtt_client.userdata:
            time.sleep(0.005)
            waited_seconds += 0.005

            if waited_seconds >= 3:
                raise RuntimeError(
                    "Expected datapoint setpoint message has not been "
                    "published on broker."
                )

        # Now that we know the message has been published on the broker,
        # verify it holds the expected information.
        received_msg = self.mqtt_client.userdata[dp_mqtt_setpoint_topic]
        assert received_msg == expected_msg

        # After the MQTT message has now arrived the updated value should now
        # be available on the REST interface. As above this might happen async,
        # hence we might give the message a bit time to arrive.
        waited_seconds = 0
        while True:
            dp.refresh_from_db()
            if dp.last_setpoint_timestamp is not None:
                break

            time.sleep(0.005)
            waited_seconds += 0.005
            if waited_seconds >= 3:
                raise RuntimeError(
                    "Expected datapoint setpoint message has not reached the "
                    "DB."
                )
        request = self.client.get(
            "/datapoint/%s/setpoint/%s/" % (dp.id, expected_msg["timestamp"])
        )
        assert request.data == expected_msg

    def test_retrieve_datapoint_forbidden_without_permissions(self):
        dp = datapoint_factory(self.test_connector)
        dp.save()

        request = self.client.get("/datapoint/%s/" % dp.id)

        assert request.status_code == 403

    def test_retrieve_datapoint_allowed_with_permissions(self):
        dp = datapoint_factory(self.test_connector)
        dp.save()

        p = Permission.objects.get(codename="view_datapoint")
        self.user.user_permissions.add(p)
        request = self.client.get("/datapoint/%s/" % dp.id)

        assert request.status_code == 200

    def test_retrieve_datapoint_msgs_forbidden_without_permissions(self):
        dp = datapoint_factory(self.test_connector)
        dp.save()

        for msg_type in ["value", "setpoint", "schedule"]:
            request = self.client.get("/datapoint/%s/%s/" % (dp.id, msg_type))
            assert request.status_code == 403

    def test_retrieve_datapoint_value_allowed_with_permissions(self):
        """
        It is not easily possible to put this into a single method due to
        permission caching. See:
        https://docs.djangoproject.com/en/3.1/topics/auth/default/#permission-caching
        """
        dp = datapoint_factory(self.test_connector)
        dp.save()

        msg_type = "value"
        p = Permission.objects.get(codename="view_datapoint%s" % msg_type)
        self.user.user_permissions.add(p)

        self.user = User.objects.get(id=self.user.id)
        request = self.client.get("/datapoint/%s/%s/" % (dp.id, msg_type))
        assert request.status_code == 200

    def test_retrieve_datapoint_setpoint_allowed_with_permissions(self):
        """
        It is not easily possible to put this into a single method due to
        permission caching. See:
        https://docs.djangoproject.com/en/3.1/topics/auth/default/#permission-caching
        """
        dp = datapoint_factory(self.test_connector)
        dp.save()

        msg_type = "setpoint"
        p = Permission.objects.get(codename="view_datapoint%s" % msg_type)
        self.user.user_permissions.add(p)

        self.user = User.objects.get(id=self.user.id)
        request = self.client.get("/datapoint/%s/%s/" % (dp.id, msg_type))
        assert request.status_code == 200

    def test_retrieve_datapoint_schedule_allowed_with_permissions(self):
        """
        It is not easily possible to put this into a single method due to
        permission caching. See:
        https://docs.djangoproject.com/en/3.1/topics/auth/default/#permission-caching
        """
        dp = datapoint_factory(self.test_connector)
        dp.save()

        msg_type = "setpoint"
        p = Permission.objects.get(codename="view_datapoint%s" % msg_type)
        self.user.user_permissions.add(p)

        self.user = User.objects.get(id=self.user.id)
        request = self.client.get("/datapoint/%s/%s/" % (dp.id, msg_type))
        assert request.status_code == 200