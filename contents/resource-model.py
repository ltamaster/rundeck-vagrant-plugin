import vagrant
import collections
import json
import re
import shlex
import os
import argparse
import logging
import sys

if os.environ.get('RD_CONFIG_DEBUG') == 'true':
    log_level = 'DEBUG'
else:
    log_level = 'ERROR'

logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, log_level),
    format='%(levelname)s: %(name)s: %(message)s'
)
log = logging.getLogger('container-model-source')


Machine = collections.namedtuple('Machine', ['id', 'name', 'provider', 'state', 'path'])


def global_status(vagrant):
    output = vagrant._run_vagrant_command(['global-status'])
    return _parse_global_status(output)


def vm_info(vagrant, name):
    output = vagrant._run_vagrant_command(['vbinfo',name])
    return json.loads(output)


def _parse_global_status(output):
    '''
    Parses the global status.
    '''
    machines = []
    output = list(map(lambda line: line.strip(), output.splitlines()))
    if '' not in output:
        return []
    for line in output[2:]:
        if line == '':
            break
        machines.append(line)

    machine_objects = []
    for machine in machines:
        machine_details = machine.split(' ')
        machine_details = list(filter(None, machine_details))
        machine_objects.append(Machine(id=machine_details[0], name=machine_details[1] , provider=machine_details[2], state=machine_details[3],
                                       path=machine_details[4]))

    return machine_objects

parser = argparse.ArgumentParser(
    description='Execute a command string in the container.'
)
parser.add_argument('defaults', help='key=value list')
parser.add_argument('ippattern', help='Ip pattern')

args = parser.parse_args()

ip_pattern = args.ippattern
defaults = args.defaults
log.debug('defaults: %s' % defaults)
log.debug('ip_pattern: %s' % ip_pattern)

list = global_status(vagrant.Vagrant())

node_list = []
for vm in list:
    if(vm.state == "running"):
        node = {}
        path= vm.path
        v1 = vagrant.Vagrant(vm.path)
        info = vm_info(v1, vm.name)

        log.debug("getting vm: %s" % vm.name)

        nodename = vm.name
        hostname = nodename

        net_list = []

        for k, v in info[vm.name]["guest_info"].items():

            match = re.match("\/VirtualBox\/GuestInfo\/Net\/(.*)\/V4\/IP",  k)
            if match:
                ipmatch = re.match(ip_pattern,v)

                net = {"vagrant:" + k , v}
                net_list.append(net)

                if(ipmatch):
                    log.debug("IP matched: %s" %v)
                    hostname = v

        default_settings = {
            'vagrant:OS/Product': info[vm.name]["guest_info"]["/VirtualBox/GuestInfo/OS/Product"],
            'vagrant:VersionExt': info[vm.name]["guest_info"]["/VirtualBox/GuestAdd/VersionExt"],
            'vagrant:OS/Release': info[vm.name]["guest_info"]["/VirtualBox/GuestInfo/OS/Release"],
            'vagrant:name': info[vm.name]["vm_info"]["name"],
            'vagrant:ostype': info[vm.name]["vm_info"]["ostype"],
            'vagrant:UUID': info[vm.name]["vm_info"]["UUID"],
            'vagrant:CfgFile': info[vm.name]["vm_info"]["CfgFile"],
            'vagrant:LogFldr': info[vm.name]["vm_info"]["LogFldr"],
            'vagrant:hardwareuuid': info[vm.name]["vm_info"]["hardwareuuid"],
            'vagrant:memory': info[vm.name]["vm_info"]["memory"],
            'vagrant:chipset': info[vm.name]["vm_info"]["chipset"],
            'vagrant:firmware': info[vm.name]["vm_info"]["firmware"],
            'vagrant:cpus': info[vm.name]["vm_info"]["cpus"],
            'vagrant:VMState': info[vm.name]["vm_info"]["VMState"],
            'vagrant:VMStateChangeTime': info[vm.name]["vm_info"]["VMStateChangeTime"],
            'vagrant:SATA-Controller': info[vm.name]["vm_info"]["SATA Controller-0-0"],
            'vagrant:SATA-ImageUUID': info[vm.name]["vm_info"]["SATA Controller-ImageUUID-0-0"],
            'vagrant:SharedFolderPath': info[vm.name]["vm_info"]["SharedFolderPathMachineMapping1"]
        }

        # rundeck attributes
        node =default_settings

        node["hostname"] = hostname
        node["nodename"] = nodename
        node["osFamily"] = default_settings["vagrant:OS/Product"]
        node["osType"] = default_settings["vagrant:ostype"]
        node.update(dict(net_list))

        node["tags"] = "vagrant"

        if defaults:
            node.update(dict(token.split('=') for token in shlex.split(defaults)))

        node_list.append(node)

y = json.dumps(node_list)

print(y)


