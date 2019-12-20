from django.contrib import admin
from django.utils.text import slugify
from .models import Connector, Device, ConnectorAvailableDatapoints, ConnectorHeartbeat, \
    ConnectorLogEntry, ConnectorDatapointMapper
from .utils import datetime_iso_format
from datetime import datetime, timezone

"""
Add actions to be performed on selected objects.
Below: example to change the heartbeat topic to "beat":
--------------------
    def change_mqtt_topic_heartbeat(modeladmin, request, queryset):
        queryset.update(mqtt_topic_heartbeat='beat')
        
    change_mqtt_topic_heartbeat.short_description = "Change MQTT topic for heartbeat"
--------------------
"""


class DatapointMappingInline(admin.TabularInline):
    model = ConnectorDatapointMapper
    extra = 0
    fields = ('datapoint_key_in_connector', 'mqtt_topic', 'datapoint_type', 'subscribed', )
    readonly_fields = ('datapoint_key_in_connector', 'mqtt_topic', 'datapoint_type', )
    ordering = ('subscribed', )
    verbose_name_plural = "Available datapoints subscription management"
    can_delete = False

    # Uncomment to only display unsubscribed datapoints
    # def get_queryset(self, request):
    #     queryset = super(DatapointMappingInline, self).get_queryset(request)
    #     return queryset.filter(subscribed=False)


@admin.register(Connector)
class ConnectorAdmin(admin.ModelAdmin):
    """
    List view customizations
    """
    # Attributes to be displayed
    list_display = ('name', 'date_added', 'alive', )

    # Ordering of objects
    ordering = ('-date_added',)

    # Filter
    # list_filter = ('attr', )

    # Search fields
    search_fields = ('name', )

    # Add action function defined above
    # actions = [change_mqtt_topic_heartbeat]

    """
    Add/Change object view customizations
    """
    # Fields to be displayed
    # fields = ('name',)

    # Fields to be hidden
    # exclude = ('name', )

    # Fieldsets allow grouping of fields with corresponding title & description
    # Doc: https://docs.djangoproject.com/en/3.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.fieldsets
    # fieldsets = (
    #     ('Datapoints', {
    #         'fields': ('available_datapoints', '')
    #     }),
    #     ('Field group 2 title', {
    #         'description': 'Further info for this group.',
    #         'classes': ('collapse', ),
    #         'fields': ()
    #     })
    # )

    inlines = ()

    @staticmethod
    def available_datapoints(obj):
        # datapoints = []
        # for dp in ConnectorAvailableDatapoints.objects.filter(connector=obj.id).last():
        #     if dp not in datapoints:
        #         datapoints.append(dp.__str__())
        #
        # if datapoints:
        #     return ", ".join(datapoints)  # return list as string
        datapoints = ConnectorAvailableDatapoints.objects.filter(connector=obj.id)
        keys = [dp.datapoint_key_in_connector for dp in datapoints]
        return len(keys)

    @staticmethod
    def last_heartbeat(obj, pretty=True):
        latest_hb_message = ConnectorHeartbeat.objects.filter(connector=obj.id).latest('last_heartbeat')
        last_hb = latest_hb_message.last_heartbeat
        if pretty:
            last_hb = datetime_iso_format(last_hb, hide_microsec=True)
        return last_hb

    @staticmethod
    def next_heartbeat(obj, pretty=True):
        latest_hb_message = ConnectorHeartbeat.objects.filter(connector=obj.id).latest('next_heartbeat')
        next_hb = latest_hb_message.next_heartbeat
        if pretty:
            next_hb = datetime_iso_format(next_hb, hide_microsec=True)
        return next_hb

    def alive(self, obj):
        current_time = datetime.now(timezone.utc)
        next_hb = ConnectorHeartbeat.objects.filter(connector=obj.id).latest('next_heartbeat').next_heartbeat
        return True if current_time <= next_hb else False
    alive.boolean = True

    """
    TODO: Managing mapping and subscription in connector change view
            - human-readable name instead of key?
            - Selection of topics I want to subscribe to (dropdown with human-readable names)
            - Set subscribed status of corresponding available datapoint to true
            - Saving of subscribed topics to connector object
    """
    @staticmethod
    def mqtt_message_topics(obj):
        key_topic_mappings = {}
        mappers = ConnectorDatapointMapper.objects.filter(connector=obj.id)
        for mapper in mappers:
            av_dp = ConnectorAvailableDatapoints.objects.filter(connector=obj.id, datapoint_key_in_connector=mapper.datapoint_key_in_connector)[0]
            key_topic_mappings[av_dp.datapoint_key_in_connector] = mapper.mqtt_topic
        return key_topic_mappings

    # Things that shall be displayed in add object view, but not change object view
    def add_view(self, request, form_url='', extra_context=None):
        self.fieldsets = (
            (None, {
                'description': '<h3>After entering the connector name, '
                               'click "Save and continue editing" to proceed with the connector integration.</h3>',
                'fields': ('name', )
            }),
            # ('MQTT topics', {
            #     'description': '<h3>Click "Save and continue editing" to prefill the MQTT topics '
            #                    'with <i>connector-name/topic</i>.</h3>',
            #     'classes': ('collapse',),
            #     'fields': [topic for topic in Connector.get_mqtt_topics(Connector()).keys()]
            # }),
        )
        return super(ConnectorAdmin, self).add_view(request)
    """
    TODO: Display datapoint mapping after the basic information
    """
    # Things that shall be displayed in change object view, but not add object view
    def change_view(self, request, object_id, form_url='', extra_context=None):
        self.inlines = [DatapointMappingInline]
        self.fieldsets = (
            ('Basic information', {
                'fields': ('name', 'date_added')
            }),

            ('Data', {
                'fields': (('alive', 'last_heartbeat', 'next_heartbeat'),)

            }),
            ('MQTT topics', {
                'fields': [topic for topic in Connector.get_mqtt_topics(Connector()).keys()]
            }),
        )
        self.readonly_fields = ('date_added', 'last_heartbeat', 'next_heartbeat', 'alive', )

        return super(ConnectorAdmin, self).change_view(request, object_id)


@admin.register(ConnectorAvailableDatapoints)
class ConnectorAvailableDatapointsAdmin(admin.ModelAdmin):
    list_display = ('id', 'connector', 'datapoint_type', 'datapoint_example_value',  'datapoint_key_in_connector', 'subscribed', )
    list_filter = ('subscribed', )#('datapoint_key_in_connector', 'connector', 'datapoint_type', 'datapoint_example_value', )

    @staticmethod
    def connector(obj):
        return obj.connector.name


@admin.register(ConnectorHeartbeat)
class ConnectorHeartbeatAdmin(admin.ModelAdmin):
    list_display = ('connector', 'last_hb_iso', 'next_hb_iso', )
    list_filter = ('connector', )

    @staticmethod
    def connector(obj):
        return obj.connector.name

    def last_hb_iso(self, obj):
        return obj.last_heartbeat.isoformat(sep=' ')
    last_hb_iso.admin_order_field = 'last_heartbeat'
    last_hb_iso.short_description = "Last heartbeat"

    def next_hb_iso(self, obj):
        return obj.next_heartbeat.isoformat(sep=' ')
    next_hb_iso.admin_order_field = 'next_heartbeat'
    next_hb_iso.short_description = "Next heartbeat"


@admin.register(ConnectorLogEntry)
class ConnectorLogsAdmin(admin.ModelAdmin):
    list_display = ('id', 'connector', 'timestamp_iso', 'msg', 'emitter', 'level')
    list_filter = ('connector', 'emitter', )

    @staticmethod
    def connector(obj):
        return obj.connector.name

    def timestamp_iso(self, obj):
        return obj.timestamp.isoformat(sep=' ')
    timestamp_iso.admin_order_field = 'timestamp'
    timestamp_iso.short_description = "Timestamp"


@admin.register(ConnectorDatapointMapper)
class ConnectorDatapointMapperAdmin(admin.ModelAdmin):
    list_display = ('id', 'connector', 'datapoint_key_in_connector', 'datapoint_type', 'mqtt_topic', )
    #list_filter = ('datapoint_key_in_connector', 'connector', 'datapoint_type', 'datapoint_example_value', )

    @staticmethod
    def connector(obj):
        return obj.connector.name


# Register your models here.
admin.site.register(Device)
