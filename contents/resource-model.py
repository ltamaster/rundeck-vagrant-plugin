import vagrant
import collections
import json
import re
import shlex
import os
import argparse
import logging
import sys
import virtualbox

log_level = 'DEBUG'

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

vbox = virtualbox.VirtualBox()


node_list = []
for vm in list:
    if(vm.state == "running"):
        node = {}
        path= vm.path
        v1 = vagrant.Vagrant(vm.path)

        vm_id_path = vm.path + "/.vagrant/machines/"+vm.name+"/virtualbox/id"

        f = open(vm_id_path, "r")
        id = f.read()
        f.close()

        m  = vbox.find_machine(id)

        log.debug("getting vm: %s" % vm.name)

        nodename = vm.name
        hostname = nodename

        net_list = {}

        net_info = m.enumerate_guest_properties("*")
        net_info_keys = net_info[0]
        net_info_values = net_info[1]

        default_settings = {
            'vagrant:vmname': m.name,
            'vagrant:ostype': m.os_type_id,
            'vagrant:UUID': m.hardware_uuid,
            'vagrant:path': path,
            'vagrant:LogFldr': m.log_folder,
            'vagrant:hardwareuuid': m.hardware_uuid,
            'vagrant:memory': m.memory_size,
            #'vagrant:chipset': m.chipset_type.,
            #'vagrant:firmware': m.firmware_type,
            'vagrant:cpus': m.cpu_count,
            'vagrant:VMState': str(m.state),
            'description': m.description

        }

        for index,key in enumerate(net_info_keys):
            value = net_info_values[index]
            match = re.match("\/VirtualBox\/GuestInfo\/Net\/(.*)\/V4\/IP", key)
            if match:
                ipmatch = re.match(ip_pattern, value)
                net = {"vagrant:" + key: value}
                net_list.update(net)

                if (ipmatch):
                    log.debug("IP matched: %s" % value)
                    hostname = value

            default_settings.update({'vagrant:'+key.replace("/VirtualBox/",""): value})

        # rundeck attributes
        node = default_settings

        node["osFamily"] = default_settings["vagrant:GuestInfo/OS/Product"]
        node["osType"] = default_settings["vagrant:ostype"]

        node["hostname"] = hostname
        node["nodename"] = nodename

        node["tags"] = "vagrant"

        if defaults:
            node.update(dict(token.split('=') for token in shlex.split(defaults)))

        node_list.append(node)

y = json.dumps(node_list)

print(y)


