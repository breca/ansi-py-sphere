#!/usr/bin/env python


"""
Automate the installation of vSphere tools

This script will mount the linux.iso to the
provided VMs. It can be tied into Ansible so
the installation can also be scripted
"""

import atexit
from pyVim import connect
from pyVmomi import vmodl, vim
import getpass
import argparse
from os import system

# Terminal colors
cl_green = "\033[1;32;40m"
cl_red = "\033[1;31;40m"
cl_white = "\033[0;37;40m"
cl_reset = "\033[0;0m"

def conn():
    """Establish a connection and ensure it is shut when the script exits"""
    print(cl_white + "[Connecting to the vSphere server]" + cl_reset)
    try:
        # Create a session for the connection to the server
        session=connect.SmartConnect(host=esxi_host, user=username, pwd=pword, port=esxi_port)
        # Sever the connection/close the port when the script exits
        atexit.register(connect.Disconnect, session)

        # Locate all VMs and store in an array for later comparison to target vms
        content=session.RetrieveContent()
        
        # Main vSphere directory
        container=content.rootFolder

        # Object type for which to search -- Virtual Machines
        obj_type=[vim.VirtualMachine]

        # Recursive folder navigation
        recurse = True   # REVIEW: unless we're moving this to a config
                         # file we may as well just pass True to the next call

        # Variable to view the list of VMs with recursive lookup.
        container_view = content.viewManager.CreateContainerView(container, obj_type, recurse)

        # The VMs listed inside that view
        vms = container_view.view

        # This could also be have been obtained with "vms=session.RetrieveContent().viewManager.CreateContainerView
        # (session.content.rootFolder, [vim.VirtualMachine], True).view however, it is broken down into variables for
        # future re-use
  
    except vomdl.MethodFault as error:
        print(cl_red + "Caught vmodl fault : " + error.msg + cl_reset)
        exit(1)
    except Exception as error:
        print(cl_red + "Something bad happened : " + str(error) + cl_reset)
        exit(2)
    else:
        return vms


def vm_search(vms):
    """
    Search for the specified VMs
    vSphere initially provides output such as "vim.VirtualMachine:vm-1337".
    This will be referred to as the "VM ID" in the comments
    """

    # Create an empty dict to store VM names against VM IDs, create a dict for the matching VM IDs from the command line
    vm_dict = {}
    target_vms = {}
 
    # Store the list of virtual machine identifiers against their names
    for vm in vms:
        vm_named = vm.summary.config.name
        vm_dict[vm_named]=vm

    # Iterate through the vm_dict and comparenm to the vm_list -- the contents of the file provided from
    # the command line.
    # Store the VM IDs in target_vms as a dict so that the hostnames can be displayed later
    for virt in vm_list:
        virt = virt.rstrip('\n')
        target_vms[vm_dict.get(virt)]=virt

    # If nothing matches, report back and exit
    if target_vms is None:
        print(cl_red + "The specified Virtual Machines could not be found."
                       "Please verify that the list contains hostnames and not IP addresses" + cl_reset)
        exit(1)
    else:
        return target_vms

def tool_check(target_vms):
    """ Check that tools are present """
    # Variables here so that the install option won't try to mount the CD if the tools are already installed
    uninstalled_vms={}
    installed_vms={}

    # Host will be the key in the associative array. In this instance, the VM ID
    for host in target_vms:
        print(cl_white + "--------------------" + cl_reset)
        print("Host : " + target_vms.get(host))
        tools_ver=host.summary.guest.toolsStatus
        if tools_ver != "toolsNotInstalled":
            print("VMware-tools : " + cl_green + tools_ver + cl_reset)
            installed_vms[host]=host.summary.config.name
        else:
            print("VMware-tools : " + cl_red + tools_ver + cl_reset)
            uninstalled_vms[host]=host.summary.config.name
        print("")
    return installed_vms, uninstalled_vms

def tool_mount(uninstalled_vms):
    """ Mount the iso """
    failed_mounts = []
    successful_mounts = []
    not_mounted = []

    for host in uninstalled_vms:
        print(cl_white + "--------------------" + cl_reset)
        print("Mounting tools on ", uninstalled_vms.get(host), "....")

        try:
            host.MountToolsInstaller()
        except:
            # If there's an error, add the host to the array of not mounted things
            not_mounted.extend([host])
        finally:
            # If there's an error, provide some limited help!
            if host in not_mounted:
                if host.summary.runtime.powerState=="poweredOff":
                    print(cl_red + "Virtual Machine must be Powered On to mount the tools!" + cl_reset)
                else:
                    print(cl_red + "Encountered an error when mounting tools to ", uninstalled_vms.get(host),
                          ". Is vSphere tools already mounted?\n" + cl_reset)
                failed_mounts.extend([uninstalled_vms.get(host)])
            # If no error, report success!
            else:
                print(cl_green + "[Done]" + cl_reset)
                print("")
                successful_mounts.extend([uninstalled_vms.get(host)])
            return failed_mounts, successful_mounts, not_mounted

def main():
    system("clear")

    # CHANGE THESE TO MATCH YOUR ENVIRONMENT!!!
    esxi_host = "insert your vSphere hostname or ip here"
    esxi_port = "insert your vSphere port here, typically 443"

    # Parse arguments
    # REVIEW: This should probably be inside a function with exception handling
    parser = argparse.ArgumentParser(
        description="This script is used to determine the status of or install vSphere tools"
                    "on a given list of VMs")
    parser.add_argument('--install', dest='install_flag', default="True", metavar='--install', required=False,
                        help="Use this flag to specify installation/mounting of the tool image on parsed VMs. Otherwise"
                             "this script will default to querying the presence of tools.")
    parser.add_argument('--username', dest='username', metavar='user.name', type=str,
                        help="Username for authentication to Esxi host. This is intended for use only with Ansible."
                             "If not included, you will be prompted for your username")
    parser.add_argument('--password', dest='pword', metavar='ultr4_s3cr3t_p4$$w0rd', type=str,
                        help="Password for authentication to Esxi host. This is intended for use only with Ansible."
                             "If not included, you will be prompted for your password")
    parser.add_argument('vm_file', metavar='vm_list_file', type=str,
                        help="Filename that contains the list of VMs against"
                             " which to run this script")

    a = parser.parse_args()
    pword = a.pword
    username = a.username

    # Declaration to the user of chosen CLI argument
    if a.install_flag:
        print("This script will automate mounting the vSphere iso on machines listed in \"" + a.vm_file + "\".")
    else:
        print("This script will query the presence of tools in the hosts specified in \"" + a.vm_file + "\".")

    # Read the VM list. Store the contents into the variable vm_list
    vm_input = open(a.vm_file, 'r')
    vm_list = vm_input.readlines()
    vm_input.close()

    # For when creds are not provided in the cli from ansible
    if not username or not pword:
        print("\nIn order to connect to vSphere, please provide your authentication details.")
        username = raw_input(cl_white + "\nEnter your username\t")  # FIXME: This won't work in Python 3
        pword = getpass.getpass()
        print(cl_reset + "")

    # Establish the connection
    vms = conn()
    print(cl_green + "\n[Done] found " + str(len(vms)) + cl_reset)
    print(cl_white + "\n--------------------Locating VMs--------------------\n" + cl_reset)
    # Call searching function
    target_vms = vm_search(vms)
    print("\n" + cl_green + "[Done] found " + str(len(target_vms.values())) + cl_reset)
    # Query status to determine what to send to installer OR because user specified to only query
    print("Querying the status of the vSphere tools on the following virtual machines: ", target_vms.values(), "\n")
    uninstalled_vms, installed_vms = tool_check(target_vms)
    # Determine the course of action based off the install flag
    if a.install_flag:
        if installed_vms is not None:
            print("Ignoring ", installed_vms.values(), " as tools are already installed\n")
        print("Mounting the ISO to the following virtual machines: ", uninstalled_vms.values(), "\n")
        failed_mounts, successful_mounts, _ = tool_mount(uninstalled_vms)
        print(cl_white + "Summary: " + cl_reset)
        if failed_mount:
            print(cl_red + "Failed: ")
            print(failed_mounts)
            print(cl_reset)
        if successful_mounts:
            print(cl_green + "Succeeded: ")
            print(successful_mounts)
            print(cl_reset)


if __name__=="__main__":
    main()
