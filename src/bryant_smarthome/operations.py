"""Only operation names, input types and selections observed in the app.

Selections are deliberately smaller than the generated mobile documents.
Input objects with incomplete schemas remain explicit caller-supplied JSON.
"""

MUTATIONS = {
    "associateDevice": ("AssociateDeviceInput", "deviceId"),
    "disassociateSystemLocation": ("DisassociateSystemLocationInput", "success message"),
    "updateConsumerDevice": ("UpdateConsumerDeviceInput", "success"),
    "sendCommand": ("DeviceCommandSetInput", "success"),
    "createLocation": ("CreateLocationInput", "locationId"),
    "updateLocation": ("UpdateLocationInput", "locationId"),
    "deleteLocation": ("DeleteLocationInput", "locationId success message"),
    "updateInfinityConfig": ("InfinityConfigInput", "etag"),
    "updateInfinityZoneConfig": ("InfinityZoneConfigInput", "etag"),
    "updateInfinityZoneActivity": ("InfinityZoneActivityInput", "etag"),
    "updateInfinityProgramDay": ("InfinityProgramDayInput", "etag"),
    "updateInfinityProfile": ("InfinityProfileInput", "name"),
    "updateInfinityNotificationPrefs": ("InfinityNotificationPrefsInput", "disconnectHours maxCount"),
    "updateEntryLevelSystem": ("EntryLevelSystemInput", "success"),
    "updateEntryLevelZone": ("EntryLevelZoneInput", "success"),
    "updateEntryLevelComfortProfile": ("EntryLevelComfortProfileInput", "success"),
    "createEntryLevelSchedule": ("CreateEntryLevelScheduleInput", "success"),
    "updateEntryLevelSchedule": ("UpdateEntryLevelScheduleInput", "success"),
    "removeEntryLevelSchedule": ("RemoveEntryLevelScheduleInput", "success"),
    "createEntryLevelScheduleBatch": ("CreateEntryLevelScheduleBatchInput", "success"),
    "updateEntryLevelDealerPreferences": ("EntryLevelDealerPreferencesInput", "success"),
    "updateEntryLevelPushNotificationPrefs": ("UpdateEntryLevelPushNotificationPrefsInput", "mute"),
    "resetEntryLevelPushNotificationReminders": ("ResetEntryLevelPushNotificationRemindersInput", "mute"),
}

HOMES = '''query getUserLocations($username: String!) {
  userLocations(username: $username) {
    locationId name street1 city state postal
    systems { profile { serial } }
    entryLevels { name serial connection { isConnected } }
    devices { deviceId type thingName name connectionStatus }
  }
}'''

USER = '''query getUser($userName: String!) {
  user(userName: $userName) {
    username identityId first last email
    locations { locationId name tempUnitFormat
      members { first last username isOwner }
      systems { profile { serial name model } }
    }
  }
}'''

SYSTEMS = '''query getInfinitySystems($userName: String!) {
  infinitySystems(userName: $userName) {
    profile { serial name firmware model idutype }
    status { isDisconnected mode vacatrunning oat }
    diagnosticInfo { support equipment { idu odu hum ven zone }
      activeDiagnostic { id status command }
    }
  }
}'''

SYSTEM = '''query getInfinitySystem($serial: String!) {
  profile: infinityProfile(serial: $serial) { serial name model firmware }
  status: infinityStatus(serial: $serial) {
    isDisconnected mode vacatrunning oat
    zones { id rt rh fan htsp clsp hold enabled currentActivity }
  }
  config: infinityConfig(serial: $serial) {
    etag mode cfgdead vacat vacstart vacend vacmint vacmaxt vacfan
    humidityVacation { humidifier rclg rclgovercool rhtg ventclg venthtg ventspdclg ventspdhtg }
    zones { id name enabled hold holdActivity otmr
      activities { id zoneId type fan previousFan htsp clsp }
      program { id day { id zoneId period { id zoneId dayId activity time enabled } } }
    }
  }
}'''

DEVICE = '''query getDeviceInfo($username: String!, $locationId: String!, $deviceId: String!) {
  deviceInfo(input: {username: $username, locationId: $locationId, deviceId: $deviceId}) {
    tempUnit connectionStatus points { name value } config { desired { name value } }
  }
}'''

ENTRY_SYSTEM = '''query getEntryLevelSystemData($serial: String!) {
  entryLevelSystem(serial: $serial) {
    serial name model firmware temp_unit_format timezone connection { isConnected }
    zones { index rt rh current_scene_name mode fan_mode
      clsp { current min } htsp { current max } schedule_enabled
      current_schedule_id hold_end_time hold_countdown set_point_delta
      schedule { scene_name day index zone_index start_time htsp clsp }
      comfort_profile { wake { htsp clsp } home { htsp clsp } away { htsp clsp } sleep { htsp clsp } }
    }
  }
}'''


def mutation(name, input_value):
    input_type, selection = MUTATIONS[name]
    return {
        "operationName": name,
        "query": f"mutation {name}($input: {input_type}!) {{ {name}(input: $input) {{ {selection} }} }}",
        "variables": {"input": input_value},
    }
