#!/usr/bin/python

import argparse
import collections
import urllib.request as urllib2
import json
import os
# The above imports are standard. Yaml is not, so we do it in main to
# kick out a useful error message if it is not found.


parser = argparse.ArgumentParser(
    description='Generate homeassistant mqtt configs for domoticz')

parser.add_argument(
    '--domoticz_host', dest='host', default='localhost:8080',
    help='The domoticz host to connect to. EG "192.168.1.5:8080"')

parser.add_argument(
    '--fahrenheit', '-f', dest='fahrenheit', default=True, action='store_true',
    help='If true, conversions to fahrenheit will be generated')

parser.add_argument(
    '--automation_dir', dest='automation_dir', default='automation',
    help='Destination dir for automation file')
parser.add_argument(
    '--automation_file', dest='automation_file',
    default='domoticz_automation.yaml',
    help='Which file to write the generated automation items to.')

parser.add_argument(
    '--climate_dir', dest='climate_dir', default='climate',
    help='Destination dir for climate file')
parser.add_argument(
    '--climate_file', dest='climate_file', default='domoticz_climate.yaml',
    help='Which file to write the generated climate items to.')

parser.add_argument(
    '--light_dir', dest='light_dir', default='light',
    help='Destination dir for light file')
parser.add_argument(
    '--light_file', dest='light_file', default='domoticz_light.yaml',
    help='Which file to write the generated light items to.')

parser.add_argument(
    '--binary_sensor_dir', dest='binary_sensor_dir', default='binary_sensor',
    help='Destination dir for binary sensor file')
parser.add_argument(
    '--binary_sensor_file', dest='binary_sensor_file', default='domoticz_binary_sensor.yaml',
    help='Which file to write the generated binary sensor items to.')

parser.add_argument(
    '--sensor_dir', dest='sensor_dir', default='sensor',
    help='Destination dir for sensor file')
parser.add_argument(
    '--sensor_file', dest='sensor_file', default='domoticz_sensor.yaml',
    help='Which file to write the generated sensor items to.')

parser.add_argument(
    '--group_dir', dest='group_dir', default='group',
    help='Destination dir for group file')
parser.add_argument(
    '--group_file', dest='group_file', default='domoticz_group.yaml',
    help='Which file to write the generated group items to.')

parser.add_argument(
    '--scene_dir', dest='scene_dir', default='scene',
    help='Destination dir for scene file')
parser.add_argument(
    '--scene_file', dest='scene_file', default='domoticz_scene.yaml',
    help='Which file to write the generated scene items to.')

parser.add_argument(
    '--lock_dir', dest='lock_dir', default='lock',
    help='Destination dir for lock file')
parser.add_argument(
    '--lock_file', dest='lock_file',  default='domoticz_lock.yaml',
    help='Which file to write the generated lock items to.')
parser.add_argument(
    '--power_dir', dest='power_dir', default='utility_meter',
    help='Destination dir for power utility meter conf')
parser.add_argument(
    '--power_file', dest='power_file', default='domoticz_power.yaml',
    help='Destination dir for power file')


parser.add_argument(
    '--ignore_types', dest='ignore_types',
    default='Hue', help='Filtered HardwareName types')
parser.add_argument(
    '--climate_naming_override', dest='climate_names',
    default='50:Downstairs Thermostat,40:Upstairs Thermostat', help='TODO')


MOTION_SENSORS = []
DOOR_SENSORS = []
TEMP_SENSORS = []
LIGHT_SWITCHES = []
CLIMATE_DEVS = []
LOCK_DEVS = []

GROUPED_SENSORS = {}


class UnsortableList(list):
  """Avoid sorting yaml items by subclassing list."""
  def sort(self, *args, **kwargs):
    pass


class UnsortableOrderedDict(collections.OrderedDict):
  """Ordered dict using the UnsortableList to avoid sorting yaml."""
  def items(self, *args, **kwargs):
    return UnsortableList(collections.OrderedDict.items(self, *args, **kwargs))


def GenLockAutomation(dev):
  data = UnsortableOrderedDict()
  data['alias'] = '{idx}_lock'.format(**dev)
  data['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
  data['condition'] = [{
      'condition': 'template',
      'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(**dev)}]
  data['action'] = [
      {'service': 'mqtt.publish',
       'data_template': {
           'topic': 'domoticz/out/{idx}/lock/status'.format(**dev),
           'payload_template': '{"state": {% if trigger.payload_json.nvalue == 1 %}"LOCK"{% else %}"UNLOCK"{% endif %} }'}
      }]
  return data


def GenLockConfigs(dev):
  data = UnsortableOrderedDict()
  data['name'] = '{Name}'.format(**dev)
  data['platform'] = 'mqtt'
  data['command_topic'] = 'domoticz/in'
  data['payload_lock'] = '{{"command": "switchlight", "idx": {idx}, "switchcmd": "On"}}'.format(**dev)
  data['payload_unlock'] = '{{"command": "switchlight", "idx": {idx}, "switchcmd": "Off"}}'.format(**dev)
  data['state_topic'] = 'domoticz/out/{idx}/lock/status'.format(**dev)
  data['state_locked'] = 'LOCK'
  data['state_unlocked'] = 'UNLOCK'
  data['value_template'] = '{{ value_json.state }}'
  return data


# TODO: patch homeassistant to allow for the data_template 'topic' to be a template
#       This would allow for the automation to be a single entry for all lights.
def GenLightAutomation(dev):
  data = UnsortableOrderedDict()
  data['alias'] = '{idx}_light'.format(**dev)
  # data['hide_entity'] = True
  data['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
  data['condition'] = {'condition': 'and', 'conditions': [
          {'condition': 'template',
           'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(**dev)},
          {'condition': 'template',
           'value_template': '{{ trigger.payload_json.nvalue in [0, 1] }}'}]}
  data['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
              'topic': 'domoticz/out/{idx}/light/status'.format(**dev),
              'payload_template' : '{ "state": {% if trigger.payload_json.nvalue == 0 %}"off"{% else %}"on"{% endif %} }'}
          }]
  return data


def GenDimmerAutomation(dev):
  data = UnsortableOrderedDict()
  data['alias'] = '{idx}_dimmer'.format(**dev)
  #data['hide_entity'] = True
  data['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
  data['condition'] = {'condition': 'and', 'conditions': [
          {'condition': 'template',
           'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(**dev)},
          {'condition': 'template',
           'value_template': '{{ trigger.payload_json.nvalue == 2 }}'}]}
  data['action']= [
          {'service': 'mqtt.publish', 'data_template':
              {'topic': 'domoticz/out/{idx}/light/status'.format(**dev),
               'payload_template': '{"state": "on", "brightness": {% with d_val=trigger.payload_json.svalue1|float * 2.55 %}{{ d_val|int }} {% endwith %} }'}}]
  return(data)


def GenLightConfigs(dev):
  d = dict(dev)
  LIGHT_SWITCHES.append(dev['Name'])
  is_dimmer = dev['SwitchType'] == 'Dimmer'
  d['dim_tmpl'] = ''
  d['command_on_template'] = '\'{"command": "switchlight", "switchcmd": "On"}\''
  if is_dimmer:
    d['dim_tmpl'] = "brightness_template: '{{ value_json.brightness }}'"
    d['command_on_template'] = """>
    {"command": "switchlight", "idx": """ + dev['idx'] + """,
    {%- if brightness is defined -%}
    "switchcmd": "Set Level", "level": {{ brightness // 2.55}}
    {%- else -%}
    "switchcmd": "On"
    {%- endif -%}
    }"""
  data = UnsortableOrderedDict()
  data['name'] = '{Name}'.format(**d)
  #data['hide_entity'] = True
  data['platform'] = 'mqtt'
  data['schema'] = 'template'
  data['command_topic'] = 'domoticz/in'
  data['state_topic'] = 'domoticz/out/{idx}/light/status'.format(**d)
  data['state_template'] = '{{ value_json.state }}'
  data['command_off_template'] = '{{"command": "switchlight", "idx": {idx}, "switchcmd": "Off"}}'.format(**d)
  if is_dimmer:
    data['command_on_template'] = ('{"command": "switchlight", "idx": ' + dev['idx'] +
        ', {%- if brightness is defined -%}"switchcmd": "Set Level", "level": '
        '{{ brightness // 2.55}}{%- else -%}"switchcmd": "On"{%- endif -%} }').encode('ascii', 'ignore')
    data['brightness_template'] = '{{ value_json.brightness|int }}'
  else:
    data['command_on_template'] = ('{"command": "switchlight", "switchcmd": "On", "idx": ' + dev['idx'] + '}').encode('ascii', 'ignore')
  return data


def GenBinarySensorAutomation(dev):
  data = UnsortableOrderedDict()
  data['alias'] = '{idx}_sensor'.format(**dev)
  #data['hide_entity'] = True
  data['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
  data['condition'] = [{
      'condition': 'template',
      'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(**dev)}]
  data['action'] = [{
      'service': 'mqtt.publish',
      'data_template': {
          'topic': 'domoticz/out/{idx}/sensor/status'.format(**dev),
          'payload_template': '{% if trigger.payload_json.nvalue == 1 %}ON{% else %}OFF{% endif %}'}}]
  return data


def GenBinarySensor(dev):
  d = dict(dev)
  s_type = {
      'Door Contact': 'opening',
      'Motion Sensor': 'motion',
      'Contact': 'opening',
  }
  if dev['SwitchType'] == 'Motion Sensor':
    MOTION_SENSORS.append(dev['Name'])
  else:
    DOOR_SENSORS.append(dev['Name'])
  d['d_type'] = "device_class: {}".format(s_type.get(dev['SwitchType'], 'None'))
  data = UnsortableOrderedDict()
  data['name'] = '{Name}'.format(**dev)
  data['platform'] = 'mqtt'
  data['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
  data['device_class'] = s_type.get(dev['SwitchType'], 'None')
  return data

def GenUtilitySensorAutomation(dev):
  d = dict(dev)
  data = UnsortableOrderedDict()
  data['alias'] = '{idx}_kwh_sensor'.format(**dev)
  data['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
  data['condition'] = [{
      'condition': 'template',
      'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(**dev)}]
  data['action'] = [{
      'service': 'mqtt.publish',
      'data_template': {
          'topic': 'domoticz/out/{idx}/sensor/status'.format(**dev),
          'payload_template': '{"kwh": {{ trigger.payload_json.svalue2|float / 1000 }}, "watts": {{ trigger.payload_json.svalue1 }} }'}}]
  return data


def GenPowerConfigs(dev):
  d = dict(dev)
  key = dev['Name'].replace(' ', '_')
  data = []
  kwh = UnsortableOrderedDict()
  kwh['name'] = '{Name}_kwh'.format(**dev)
  kwh['platform'] = 'mqtt'
  kwh['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
  kwh['unit_of_measurement'] = 'kwh'
  kwh['value_template'] = '{{ value_json.kwh }}'
  watts = UnsortableOrderedDict()
  watts['name'] = '{Name}_watts'.format(**dev)
  watts['platform'] = 'mqtt'
  watts['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
  watts['unit_of_measurement'] = 'watts'
  watts['value_template'] = '{{ value_json.watts }}'
  GROUPED_SENSORS[ConvertName(dev['Name'])] = [dev['Name'], kwh['name'], watts['name']]
  return [kwh, watts]


def GenUtilityMeterConfigs(dev):
  d = UnsortableOrderedDict()
  key = ConvertName(dev['Name'])
  grouped_sensors = []
  for duration in ['hourly', 'daily', 'weekly', 'monthly', 'quarterly']:
    sensor_key = '{}_{}_energy'.format(key, duration)
    d[sensor_key] = {
        'source': 'sensor.{}_kwh'.format(key),
        'cycle': duration}
    grouped_sensors.append(sensor_key)
  GROUPED_SENSORS[key + 'consumption'] = [dev['Name'] + ' Consumption'] + grouped_sensors
  return d


def GenTempSensorAutomation(dev, to_f=False):
  temp = 'trigger.payload_json.svalue1|float'
  if to_f:
    temp += ' * 1.8 + 32'
  payload_template = ""
  if dev['Type'] == "Temp + Humidity":
    payload_template = ('{"temperature": {{ ' + temp + ' }}, "humidity": {{ trigger.payload_json.svalue2 }} }')
  elif dev['Type'] == "Temp":
    payload_template = '{"temperature": {{ ' + temp + ' }} }'
  elif dev['Type'] == "Temp + Humidity + Baro":
    payload_template = '{"temperature": {{ ' + temp + ' }}, "humidity": {{ trigger.payload_json.svalue2 }}, "barometer": {{ trigger.payload_json.svalue4 }} }'
  elif dev['Type'] == "Wind":
    payload_template = '{"windspeed": {{ trigger.payload_json.svalue3 }}, "windgust": {{ trigger.payload_json.svalue4 }}, "windchill": {{ ' + temp.replace('svalue1', 'svalue6') + ' }}, "direction": "{{ trigger.payload_json.svalue2 }}" }'
  else:
    print('Not implemented: {}'.format(dev['Type']))
    return None
  data = UnsortableOrderedDict()
  data['alias'] = '{idx}_sensor'.format(**dev)
  #data['hide_entity'] = True
  data['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
  data['condition'] = [{
      'condition': 'template',
      'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(**dev)}]
  data['action'] = [{
      'service': 'mqtt.publish', 'data_template': {
          'topic': 'domoticz/out/{idx}/sensor/status'.format(**dev),
          'payload_template': payload_template}}]
  return data


def GenTempSensorList(dev, to_f=False):
  t_unit = 'F' if to_f else 'C'
  data = []
  key = dev['Name'].replace(' ', '_')
  if 'Temp' in dev['Type']:
    e = UnsortableOrderedDict()
    e['name'] = '{Name}_temperature'.format(**dev)
    e['platform'] = 'mqtt'
    e['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    e['unit_of_measurement'] = t_unit
    e['value_template'] = '{{ value_json.temperature }}'
    data.append(e)
    TEMP_SENSORS.append(e['name'])
  if 'Humidity' in dev['Type']:
    e = UnsortableOrderedDict()
    e['name'] = '{Name}_humidity'.format(**dev)
    e['platform'] = 'mqtt'
    e['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    e['unit_of_measurement'] = '%'
    e['value_template'] = '{{ value_json.humidity }}'
    data.append(e)
    TEMP_SENSORS.append(e['name'])
    GROUPED_SENSORS[key] = [
        dev['Name'], e['name'], dev['Name'] + '_temperature']
  if dev['Type'] == 'Temp + Humidity + Baro':
    e = UnsortableOrderedDict()
    e['name'] = '{Name}_barometer'.format(**dev)
    e['platform'] = 'mqtt'
    e['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    e['unit_of_measurement'] = 'hPa'
    e['value_template'] = '{{ value_json.barometer}}'
    data.append(e)
    TEMP_SENSORS.append(e['name'])
    GROUPED_SENSORS[key].append(e['name'])
  if dev['Type'] == "Wind":
    s = UnsortableOrderedDict()
    s['name'] = '{Name}_windspeed'.format(**dev)
    s['platform'] = 'mqtt'
    s['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    s['unit_of_measurement'] = 'speed'
    s['value_template'] = '{{ value_json.windspeed }}'
    data.append(s)
    g = UnsortableOrderedDict()
    g['name'] = '{Name}_windgust'.format(**dev)
    g['platform'] = 'mqtt'
    g['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    g['unit_of_measurement'] = 'gust'
    g['value_template'] = '{{ value_json.windgust }}'
    data.append(g)
    c = UnsortableOrderedDict()
    c['name'] = '{Name}_windchill'.format(**dev)
    c['platform'] = 'mqtt'
    c['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    c['unit_of_measurement'] = t_unit
    c['value_template'] = '{{ value_json.windchill }}'
    data.append(c)
    d = UnsortableOrderedDict()
    d['name'] = '{Name}_direction'.format(**dev)
    d['platform'] = 'mqtt'
    d['state_topic'] = 'domoticz/out/{idx}/sensor/status'.format(**dev)
    d['unit_of_measurement'] = 'dir'
    d['value_template'] = '{{ value_json.direction }}'
    data.append(d)
    TEMP_SENSORS.extend([s['name'], g['name'], c['name'], d['name']])
    GROUPED_SENSORS[key] = [
        dev['Name'], s['name'], g['name'], c['name'], d['name']]
  return data


def GenGroupedSensors():
  data = UnsortableOrderedDict()
  for name, items in GROUPED_SENSORS.items():
    name = ConvertName(name)
    data[name] = UnsortableOrderedDict()
    data[name]['name'] = items[0]
    data[name]['entities'] = [
        ConvertName('sensor.{}'.format(i)) for i in items[1:]]
  return data


def GenGroups():
  data = UnsortableOrderedDict()
  l = TEMP_SENSORS[:]
  l.extend(MOTION_SENSORS[:])
  l.extend(DOOR_SENSORS)
  for name, devs in GROUPED_SENSORS.items():
    for dev in devs:
      if dev in l:
        l.remove(dev)
  data['sensors'] = UnsortableOrderedDict()
  data['sensors']['name'] = 'Sensors'
  data['sensors']['entities'] = [
      'sensor.{}'.format(ConvertName(x)) for x in l]
  data['sensors']['entities'].extend([
      'group.{}'.format(ConvertName(x)) for x in GROUPED_SENSORS.keys()])
  data['lights'] = UnsortableOrderedDict()
  data['lights']['name'] = 'Lights'
  data['lights']['entities'] = [
      'light.{}'.format(ConvertName(x)) for x in LIGHT_SWITCHES]
  return data


def GetThermostats(host, to_f=False):
  # TODO: This method needs help, really complex and full of corner cases.
  tof = ''
  if to_f:
    tof += ' * 1.8 + 32'
  climate_data = []
  automation_data = []
  devs = GetDevices(host, None, None)
  thermostat_ids = []
  for d in devs['result']:
    if d['Type'] == 'Thermostat':
      t_id = d['ID'].lstrip('0')
      if 'ZWave' in d['HardwareType']:
        t_id = t_id[:2]
        thermostat_ids.append(t_id)
  thermostat_ids = set(thermostat_ids)
  thermostats = {}
  for t_id in thermostat_ids:
    t_devs = [x for x in devs['result'] if x['ID'].lstrip('0').startswith(t_id)]
    t_modes = t_modes_rev = f_modes = f_modes_rev = h_setpoint = c_setpoint = cur_temp = None
    tmode_idx = tstate_idx = fmode_idx = hset_idx = cset_idx = t_idx = None
    for dev in t_devs:
      if dev['SubType'] == 'Thermostat Mode':
        t_modes = {}
        t_modes_rev = {}
        tmode_idx = dev['idx']
        m = dev['Modes'].lower().split(';')
        i = 0
        while (i < len(m)):
          if i+1 == len(m): break
          if m[i+1] not in ['auto', 'off', 'cool', 'heat', 'dry', 'fan_only']:
            i += 2
            continue
          t_modes_rev[m[i]] = m[i+1].replace(' ', '_')  # map str(int) to logical name
          t_modes[m[i+1].replace(' ', '_')] = int(m[i])  # map logical name to int
          i += 2
      elif dev['SubType'] == 'Thermostat Fan Mode':
        f_modes = {}
        f_modes_rev = {}
        fmode_idx = dev['idx']
        m = dev['Modes'].lower().split(';')
        i = 0
        while (i < len(m)):
          if i+1 == len(m): break
          f_modes_rev[m[i]] = m[i+1]  # map str(int) to logical name
          f_modes[m[i+1]] = int(m[i])  # map logical name to int
          i += 2
      elif dev['SubType'] == 'SetPoint':
        # Guessing for heating vs cooling
        for t in ['heat', 'warm', 'fire', 'setpoint', 'target']:
          if t in dev['Name'].lower():
            if not 'econ' in dev['Name'].lower():
              hset_idx = dev['idx']
          else:
            pass  # my thermostat only has one setpoint, but domoticz has 2
      elif dev['Type'] == 'Temp':
        t_idx = dev['idx']
      elif dev['SubType'] == 'Thermostat Operating State':
        tstate_idx = dev['idx']
    climate = UnsortableOrderedDict()
    climate['platform'] = 'mqtt'
    if args.climate_names:
      overrides = {}
      for i in args.climate_names.split(','):
        k,v = i.split(':')
        overrides[k] = v
    if overrides.get(t_id):
      climate['name'] = overrides.get(t_id)
    else:
      climate['name'] = 'Thermostat'  # TODO how to get the right name here?
    climate['send_if_off'] = 'true'
    if t_idx:
      climate['current_temperature_topic'] = 'domoticz/out/climate/{idx}/temp'.format(idx=t_idx)
      a = UnsortableOrderedDict()
      a['alias'] = '{idx}_climate_temp'.format(idx=t_idx)
      #a['hide_entity'] = True
      a['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
      a['condition'] = [{
          'condition': 'template',
          'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(idx=t_idx)}]
      a['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
              'payload_template': '{{{{ trigger.payload_json.svalue1|float {} }}}}'.format(tof),
              'topic': 'domoticz/out/climate/{idx}/temp'.format(idx=t_idx)}}]

      automation_data.append(a)
    if hset_idx:
      climate['temperature_state_topic'] = 'domoticz/out/climate/{idx}/target'.format(idx=hset_idx)
      climate['temperature_command_topic'] = 'domoticz/in/climate/{idx}/set'.format(idx=hset_idx)
      climate['max_temp'] = '78'
      climate['min_temp'] = '52'
      a = UnsortableOrderedDict()
      b = UnsortableOrderedDict()
      a['alias'] = '{idx}_target_temp'.format(idx=hset_idx)
      #a['hide_entity'] = True
      a['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
      a['condition'] = [{
          'condition': 'template',
          'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(idx=hset_idx)}]
      a['action'] = [{'service': 'mqtt.publish', 'data_template': {
              'payload_template': (
                  '{% set max_temp = ' + climate['max_temp'] + ' %}'
                  '{% set ctof = trigger.payload_json.svalue1|float ' + tof + ' %}'
                  '{% if ctof > max_temp %}'
                      '{{ trigger.payload_json.svalue1|float }}'
                  '{% else %}'
                      '{{ ctof }}'
                  '{% endif %}'),

              'topic': 'domoticz/out/climate/{idx}/target'.format(idx=hset_idx)}
              }]
      b['alias'] = '{idx}_target_temp_set'.format(idx=hset_idx)
      #b['hide_entity'] = True
      b['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/in/climate/{idx}/set'.format(idx=hset_idx)}
      b['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
               # domoticz bug, don't convert back to C, since the thermostat actually expects F.
              'payload_template': '{{"idx": {idx}, "svalue": "{{{{ trigger.payload_json }}}}" }} '.format(idx=hset_idx),
              'topic': 'domoticz/in'}}]
      automation_data.extend([a, b])
    if tmode_idx:
      climate['mode_state_topic'] = 'domoticz/out/climate/{idx}/mode'.format(idx=tmode_idx)
      climate['mode_command_topic'] = 'domoticz/in/climate/{idx}/mode'.format(idx=tmode_idx)
      climate['modes'] = list(t_modes.keys())
      a = UnsortableOrderedDict()
      b = UnsortableOrderedDict()
      a['alias'] = '{idx}_state'.format(idx=tmode_idx)
      #a['hide_entity'] = True
      a['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
      a['condition'] = [{
          'condition': 'template',
          'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(idx=tmode_idx)}]
      a['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
              'payload_template': (
                  '{% with mode_map={' + ','.join(['"{k}": "{v}"'.format(k=k, v=v) for k,v in t_modes_rev.items()]) + '} %}'
                    '{{ mode_map[trigger.payload_json.nvalue|string] }}'
                  '{% endwith %}'),
              'topic': 'domoticz/out/climate/{idx}/mode'.format(idx=tmode_idx)}}]
      b['alias'] = '{idx}_state_set'.format(idx=tmode_idx)
      #b['hide_entity'] = True
      b['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/in/climate/{idx}/mode'.format(idx=tmode_idx)}
      b['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
              'payload_template': (
                  '{% with mode_map={' + ','.join(['"{k}": "{v}"'.format(k=k, v=v) for k,v in t_modes.items()]) + '} %}'
                    '{ "idx": ' + '{}'.format(tmode_idx) + ', "nvalue": {{ mode_map[trigger.payload] }} }'
                  '{% endwith %}'),
              'topic': 'domoticz/in'}}]
      automation_data.extend([a, b])
    if tstate_idx:
      climate['action_topic'] = 'domoticz/out/climate/{idx}/action'.format(idx=tstate_idx)
      a = UnsortableOrderedDict()
      b = UnsortableOrderedDict()
      a['alias'] = '{idx}_action'.format(idx=tstate_idx)
      #a['hide_entity'] = True
      a['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
      a['condition'] = [{
          'condition': 'template',
          'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(idx=tstate_idx)}]
      a['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
               'payload_template': (
                   '{% with mode_map={"0": "off", "1": "cooling", "2": "heating"} %}'
                     '{{ mode_map[trigger.payload_json.nvalue|string] }}'
                   '{% endwith %}'
                     ),
               'topic': 'domoticz/out/climate/{idx}/action'.format(idx=tstate_idx)}}]
      automation_data.extend([a])
    if fmode_idx:
      climate['fan_mode_state_topic'] = 'domoticz/out/climate/{idx}/mode'.format(idx=fmode_idx)
      climate['fan_mode_command_topic'] = 'domoticz/in/climate/{idx}/mode'.format(idx=fmode_idx)
      climate['fan_modes'] = list(f_modes.keys())
      a = UnsortableOrderedDict()
      b = UnsortableOrderedDict()
      a['alias'] = '{idx}_state'.format(idx=fmode_idx)
      #a['hide_entity'] = True
      a['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/out'}
      a['condition'] = [{
          'condition': 'template',
          'value_template': '{{{{ trigger.payload_json.idx == {idx} }}}}'.format(idx=fmode_idx)}]
      a['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
              'payload_template': (
                  '{% with mode_map={' + ','.join(['"{k}": "{v}"'.format(k=k, v=v) for k,v in f_modes_rev.items()]) + '} %}'
                    '{{ mode_map[trigger.payload_json.nvalue|string] }}'
                  '{% endwith %}'),
              'topic': 'domoticz/out/climate/{idx}/mode'.format(idx=fmode_idx)}}]
      b['alias'] = '{idx}_state_set'.format(idx=fmode_idx)
      #b['hide_entity'] = True
      b['trigger'] = {'platform': 'mqtt', 'topic': 'domoticz/in/climate/{idx}/mode'.format(idx=fmode_idx)}
      b['action'] = [
          {'service': 'mqtt.publish',
           'data_template': {
              'payload_template': (
                  '{% with mode_map={' + ','.join(['"{k}": "{v}"'.format(k=k, v=v) for k,v in f_modes.items()]) + '} %}'
                    '{ "idx": ' + '{}'.format(tmode_idx) + ', "nvalue": {{ mode_map[trigger.payload] }} }'
                  '{% endwith %}'),
              'topic': 'domoticz/in'}}]
      automation_data.extend([a, b])
    climate_data.append(climate)
  return {'automation': automation_data, 'climate': climate_data}

def GenAllDeviceQueryActions(devices):
  data = []
  for dev in devices['result']:
    d = UnsortableOrderedDict()
    d['service'] = 'mqtt.publish'
    d['data_template'] = {
        'topic': 'domoticz/in',
        'payload_template': '{{"command": "getdeviceinfo", "idx": {idx} }}'.format(**dev)}
    data.append(d)
  return data


def GenStartupAutomation(devices):
  data = UnsortableOrderedDict()
  data['alias'] = 'prime_domoticz_devices'
  #data['hide_entity'] = True
  data['trigger'] = {'platform': 'homeassistant', 'event': 'start'}
  data['action'] = GenAllDeviceQueryActions(devices)
  return data


def GetDevices(host, dev_filter, only_used=True):
  base_url = 'http://{host}/json.htm'.format(host=host)
  used = '&used=true' if only_used else ''
  dev_f = ''
  if dev_filter:
    dev_f = '&filter={dev_filter}'.format(dev_filter=dev_filter)
  req = urllib2.Request(
      '{base_url}?type=devices&order=Name{dev_f}{used}'.format(
          base_url=base_url, dev_f=dev_f, used=used))
  resp = urllib2.urlopen(req)
  data = resp.read().decode('ascii')
  data = json.loads(data)
  return data


def GetScenes():
  req = urllib2.Request('http://localhost:8080/json.htm?type=scenes')
  resp = rullib2.urlopen(req)
  data = resp.read()
  data = json.loads(data)
  return data


def MakeDirIfNotExists(dest):
  try:
    os.stat(dest)
  except OSError:
    os.mkdir(dest)


def DumpAndSpaceYaml(input_dict, delimitor_line):
  import yaml
  yaml.add_representer(
      UnsortableOrderedDict, yaml.representer.SafeRepresenter.represent_dict)
  output = yaml.dump(
      input_dict, default_flow_style=False, width=240).split('\n')
  retval = []
  for l in output:
    if delimitor_line in l:
      retval.append('')
    retval.append(l)
  return '\n'.join(retval)


def CheckForYamlPackage():
  try:
    import yaml
  except ImportError:
    print('yaml module not found, but it is required. This module is found in')
    print('most common repositories, EG for ubuntu run:')
    print('"apt-get install python-yaml"')
    exit(1)


def PrintDestinations(
    automation_path, binary_sensor_path, climate_path, group_path, light_path,
    lock_path, power_path, sensor_path, utility_path):
  print('Writing to the following files:')
  print('  automation    : {}'.format(automation_path))
  print('  binary sensor : {}'.format(binary_sensor_path))
  print('  climate       : {}'.format(climate_path))
  print('  group         : {}'.format(group_path))
  print('  light         : {}'.format(light_path))
  print('  lock          : {}'.format(lock_path))
  print('  power         : {}'.format(power_path))
  print('  sensor        : {}'.format(sensor_path))
  print('  utility       : {}'.format(utility_path))


def WriteFile(yaml_in, path, delimitor_line):
  MakeDirIfNotExists(os.path.dirname(path))
  with open(path, 'w') as f:
    f.truncate()
    f.write(DumpAndSpaceYaml(yaml_in, delimitor_line))


def ConvertName(name):
  return name.lower().replace(' ', '_').replace('\'', '')

def main():
  CheckForYamlPackage()
  global args
  args = parser.parse_args()
  to_f = args.fahrenheit
  automation_path = os.path.abspath(
      os.path.join(args.automation_dir, args.automation_file))
  binary_sensor_path = os.path.abspath(
      os.path.join(args.binary_sensor_dir, args.binary_sensor_file))
  climate_path = os.path.abspath(
      os.path.join(args.climate_dir, args.climate_file))
  group_path = os.path.abspath(os.path.join(args.group_dir, args.group_file))
  light_path = os.path.abspath(os.path.join(args.light_dir, args.light_file))
  lock_path = os.path.abspath(os.path.join(args.lock_dir, args.lock_file))
  power_path = os.path.abspath(os.path.join(args.sensor_dir, args.power_file))
  sensor_path = os.path.abspath(os.path.join(args.sensor_dir, args.sensor_file))
  utility_path = os.path.abspath(os.path.join(args.power_dir, args.power_file))
  PrintDestinations(
      automation_path,
      binary_sensor_path,
      climate_path,
      group_path,
      light_path,
      lock_path,
      power_path,
      sensor_path,
      utility_path)

  host = args.host
  automation_yaml_out = []
  sensors_yaml_out = []
  binary_sensors_yaml_out = []
  lights_yaml_out = []
  lock_yaml_out = []
  power_yaml_out = []
  utility_yaml_out = {}

  # Light/Binary sensor automation
  data = GetDevices(host=host, dev_filter='light')
  for dev in data['result']:
    if args.ignore_types:
      if dev['HardwareName'] in args.ignore_types.split(','):
        print('Skipping {} due to hardware type {}'.format(
            dev['Name'], dev['HardwareName']))
        continue
    if dev['SwitchType'] in ['Motion Sensor', 'Door Contact', 'Contact']:
      automation_yaml_out.append(GenBinarySensorAutomation(dev))
      binary_sensors_yaml_out.append(GenBinarySensor(dev))
    if dev['SwitchType'] in ['On/Off', 'Dimmer', 'Push On Button']:
      automation_yaml_out.append(GenLightAutomation(dev))
      lights_yaml_out.append(GenLightConfigs(dev))
    if dev['SwitchType'] == 'Dimmer':
      automation_yaml_out.append(GenDimmerAutomation(dev))
    if dev['SwitchType'] == 'Door Lock':
      automation_yaml_out.append(GenLockAutomation(dev))
      lock_yaml_out.append(GenLockConfigs(dev))

  # Temp/Humidity automation
  data = GetDevices(host=host, dev_filter='temp')
  for dev in data['result']:
    automation_yaml_out.append(GenTempSensorAutomation(dev, to_f=to_f))
    for s in GenTempSensorList(dev, to_f=to_f):
      sensors_yaml_out.append(s)

  # Power automation
  data = GetDevices(host=host, dev_filter='utility')
  for dev in data['result']:
    if dev.get('SubType', '') == 'kWh':
      automation_yaml_out.append(GenUtilitySensorAutomation(dev))
      for d in GenPowerConfigs(dev):
        power_yaml_out.append(d)
      utility_yaml_out.update(GenUtilityMeterConfigs(dev))


  # Thermostat automation
  t_data = GetThermostats(host=host, to_f=to_f)
  automation_yaml_out.extend(t_data['automation'])

  # Startup automation
  automation_yaml_out.append(GenStartupAutomation(
      GetDevices(host=host, dev_filter='all', only_used=False)))


  WriteFile(automation_yaml_out, automation_path, 'alias')
  WriteFile(lights_yaml_out, light_path, 'name')
  WriteFile(binary_sensors_yaml_out, binary_sensor_path, 'name')
  WriteFile(sensors_yaml_out, sensor_path, 'name')
  WriteFile(power_yaml_out, power_path, 'name')
  WriteFile(utility_yaml_out, utility_path, '____')
  WriteFile(t_data['climate'], climate_path, 'platform')
  WriteFile(lock_yaml_out, lock_path, 'name')
  group_yaml = GenGroupedSensors()
  for k, v in GenGroups().items():
    group_yaml[k] = v
  WriteFile(group_yaml, group_path, '____')

if __name__ == '__main__':
  main()

