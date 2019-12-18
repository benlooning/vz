import requests, json, sys, threading, hashlib, yaml
from bs4 import BeautifulSoup
from threading import Thread

#open config
config = yaml.load(open('config/aha.yml'))

#viessmann
url_viessmann = 'https://api.viessmann-platform.io/operational-data/installations/143919/gateways/7571381739566206/devices/0/features/heating.sensors.temperature.outside'
payload_viessmann = ""
headers_viessmann = {}

#volkszaeler
vz_hostname = config['volkszaehler']['hostname']
outside_temp_uuid = "f36b5280-1c51-11ea-b435-edc5e683d6f8"
url_vz = 'http://' + vz_hostname + '/middleware/data/' + outside_temp_uuid + '.json?operation=add&value='
url_vz_data = 'http://' + vz_hostname + '/middleware/data/'
payload_vz = ""
headers_vz = ""

#fritzbox
password = config['fritzbox']['password']
user = config['fritzbox']['username']
sessionid = '0000000000000000'
fritzbox_url = 'http://' + config['fritzbox']['hostname']
path_avm_login = "/login_sid.lua"
path_avm_aha = "/webservices/homeautoswitch.lua"


#AVM
#not in use
def get_getswitch_list (session_id):
    try:
        resp = requests.get(fritzbox_url + path_avm_aha + "?switchcmd=getswitchlist" + "&sid=" + session_id)
        print (fritzbox_url + path_avm_aha + "?switchcmd=getswitchlist" + "&sid=" + session_id)
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()
        #soup = BeautifulSoup(resp.content, "lxml")
        #return soup.find('sid').string
        return resp.content
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)

def get_temperature (session_id, ain):
    try:
        resp = requests.get(fritzbox_url + path_avm_aha + "?ain=" + ain + "&switchcmd=gettemperature" + "&sid=" + session_id)
        #print (fritzbox_url + path_avm_aha + "?ain=" + ain + "&switchcmd=gettemperature" + "&sid=" + session_id)
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        temperature = str(float(soup.string)/10)
        print('(info): new temperature value from sensor {}'.format(ain) + ': {}'.format(temperature))
        return temperature
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)

def get_session_id (user, response):
    try:
        resp = requests.get(fritzbox_url + path_avm_login + "?username=" + user + "&response=" + response)
        #/login_sid.lua?username=' + this._box.user + '&response=' + resp;
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        return soup.find('sid').string
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)

def get_response(password, challenge):
    #response =  "1234567z" + password #get_challenge()
    response = (challenge + "-" + password).encode('utf-16le')
    #response = response.decode('iso-8859-1').encode('utf-16le') #.decode('iso-8859-1')
    response = challenge + "-" + (hashlib.md5(response).hexdigest())#.lower())
    return response

def get_challenge():
    try:
        resp = requests.get(fritzbox_url + path_avm_login)
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "lxml")
        #print (soup.find('challenge').string)
        return soup.find('challenge').string
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)

# Viessmann
def get_outside_temp():
    try:
        resp = requests.get(url_viessmann, data=payload_viessmann, headers=headers_viessmann)
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()
            #print('GET /features/ {}'.format(resp.status_code))
        print (resp.json()['properties']['value']['value'])
        post_outside_temp(str(resp.json()['properties']['value']['value']))
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)
    get_outside_temp_t = threading.Timer(60.0, get_outside_temp)
    get_outside_temp_t.start()

#volkszaehler
def post_vz_value(uuid, value):
    try:
        resp = requests.post(url_vz_data + uuid + ".json?operation=add&value=" + value, data=payload_vz, headers=headers_vz)
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()
            #print('GET /features/ {}'.format(resp.status_code))
        print ('(info): value for channel {}'.format(uuid) + ' sucessfully added') #: {}'.format(resp.json()))
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)

#old but still used for Viessmann
def post_outside_temp(outside_temp):
    try:
        resp = requests.post(url_vz + outside_temp, data=payload_vz, headers=headers_vz)
        if resp.status_code != 200:
            # This means something went wrong.
            resp.raise_for_status()
            #print('GET /features/ {}'.format(resp.status_code))
        print (resp.json())
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print (e)
        #sys.exit(1)

def process_aha_sensor_value(session_id, ain, uuid):
    post_vz_value(uuid, get_temperature(session_id, ain))

def process_aha_values():
    global sessionid, aha_sensors, config
    #loop through aha_sensors
    for sensor_id in config['ahasensors']:
        Thread(target=process_aha_sensor_value, args=(sessionid, config['ahasensors'][sensor_id]['ain'], config['ahasensors'][sensor_id]['uuid'])).start()
    process_aha_values_t = threading.Timer(60.0, process_aha_values) #, (session_id, ain))
    process_aha_values_t.start()

# function that starts thread to create / renew aha sessionid
def aha_session():
    global sessionid, user, password
    if sessionid == "0000000000000000":
        sessionid = get_session_id(user, get_response(password,get_challenge()))
        print('(warning): sessionid invalid, new sessionid: {}'.format(sessionid))
    aha_session_t = threading.Timer(60.0, aha_session) #, (session_id, ain))
    aha_session_t.start()
    print('(info): sessionid valid, next validation in 60 seconds')

#set initial session id
aha_session()

#loop through aha_sensors
process_aha_values()
