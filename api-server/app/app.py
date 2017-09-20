from flask import Flask, jsonify, request, abort
from flask_cors import CORS, cross_origin
from network import UCSNet
from server import UCSServer
from session import UCSSession
from util import UCSUtil
from iso import IsoMaker
from db import YamlDB
from autoinstall import Builder

app = Flask(__name__)
CORS(app)

KUBAM_CFG="/kubam/kubam.yaml"
API_ROOT="/api/v1"

handle = ""

credentials = {
    'user': "",
    'password': "",
    'server': ""
}

@app.route('/')
def index():
    return jsonify({'status': 'ok'})


@app.route(API_ROOT + "/session", methods=['GET'])
def get_creds():
    c = credentials
    c["password"] = "REDACTED"
    return jsonify({'credentials': c})


# test with: curl -H "Content-Type: application/json" -X POST -d '{"credentials": {"user" : "admin", "password" : "cisco123", "server" : "172.28.225.163"}}' http://localhost/api/v1/credentials

@app.route(API_ROOT + "/session", methods=['POST'])
@cross_origin()
def create_creds():
    global handle
    if not request.json:
        return jsonify({'error': 'expected credentials hash'}), 400
   
    credentials['user'] = request.json['credentials']['user']
    credentials['password'] = request.json['credentials']['password']
    credentials['server'] = request.json['credentials']['server']
    h, err = UCSSession.login(credentials['user'], 
                              credentials['password'],
                              credentials['server'])
    if h == "":
        return jsonify({'error': err}), 401
    handle = h
    return jsonify({'login': "success"}), 201

@app.route(API_ROOT + "/session", methods=['DELETE', 'OPTIONS'])
def delete_session():
    if handle != "":
        UCSSession.logout(handle)
    return jsonify({'logout': "success"})

def not_logged_in():
    return jsonify({'error': 'not logged in to UCS'}), 401
    
# get the networks in the UCS. 
@app.route(API_ROOT + "/networks", methods=['GET'])
def get_networks():
    global handle
    if handle == "":
        return not_logged_in() 
    vlans = UCSNet.listVLANs(handle) 
    err, msg, net_settings = YamlDB.get_ucs_network(KUBAM_CFG)
    selected_vlan = ""
    if "vlan" in net_settings:
        selected_vlan = net_settings["vlan"]
       
    return jsonify({'vlans': [{"name": vlan.name, "id": vlan.id, "selected": (vlan.name == selected_vlan)}  for vlan in vlans]}), 200
                    

@app.route(API_ROOT + "/networks", methods=['POST'])
def select_vlan():
    global handle
    if handle == "":
        return not_logged_in() 
    if not request.json:
        return jsonify({'error': 'expected credentials hash'}), 400
    vlan = request.json['vlan']
    # Strip off the /fabric/net- portion.
    err, msg = YamlDB.update_ucs_network(KUBAM_CFG, {"vlan": vlan})
    if err != 0:
        return jsonify({'error': msg}), 500
    return jsonify({'status': 'ok'}), 201
        

@app.route(API_ROOT + "/servers", methods=['GET'])
def get_servers():
    global handle
    if handle == "":
        return not_logged_in() 
    servers = UCSServer.list_servers(handle) 
    return jsonify({'servers': servers}), 200

# list ISO images.
@app.route(API_ROOT + "/isos", methods=['GET'])
def get_isos():
    err, isos = IsoMaker.list_isos("/kubam")    
    if err != 0:
        return jsonify({'error': isos})
    return jsonify({'isos': isos}), 200

# DO NOT USE
# This API is only for extracting unknown ISOs.  We can put the iso as well as the directory name we want to extract to.  Use /isos/boot
# extract an ISO image. This probably isn't used as the /isos/boot does this for you as part of the 
# creation process. 
# curl -H "Content-Type: application/json" -X POST -d '{"iso" : "Vmware-ESXi-6.5.0-4564106-Custom-Cisco-6.5.0.2.iso", "os": "esxi6.5" }' http://localhost/api/v1/isos/extract
@app.route(API_ROOT + "/isos/extract", methods=['POST'])
def extract_iso():
    if not request.json:
        return jsonify({'error': 'expected iso hash'}), 400
    iso = request.json['iso']
    os = request.json['os']
    err, msg = IsoMaker.extract_iso("/kubam/" + iso, "/kubam/" + os) 
    if not err == 0:
        return jsonify({"error": msg}), 500
    return jsonify({"status": "ok"}), 201

# make the boot ISO image of an ISO
# curl -H "Content-Type: application/json" -X POST -d '{"iso" : "Vmware-ESXi-6.5.0-4564106-Custom-Cisco-6.5.0.2.iso" }' http://localhost/api/v1/isos/boot
# curl -H "Content-Type: application/json" -X POST -d '{"iso" : "CentOS-7-x86_64-Minimal-1611.iso" }' http://localhost/api/v1/isos/boot
@app.route(API_ROOT + "/isos/boot", methods=['POST'])
def mkboot_iso():
    if not request.json:
        return jsonify({'error': 'expected iso hash'}), 400
    iso = request.json['iso']
    err, msg = IsoMaker.mkboot_iso(iso)
    if not err == 0:
        return jsonify({"error": msg}), 500
    return jsonify({"status": "ok"}), 201
    

# Make the server images
@app.route(API_ROOT + "/servers/images", methods=['POST'])
def deploy_server_autoinstall_images():
    err, msg = Builder.deploy_server_images()
    if not err == 0:
        return jsonify({"error": msg})
    return jsonify({"status": "ok"}), 201

if __name__ == '__main__':
    app.run(debug=True)

