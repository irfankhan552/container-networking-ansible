#!/usr/bin/python
#
# Retrieve information on an existing VPC.
#

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

import boto.vpc

def clear_all_permissions(conn, security_group):
    for rule in security_group.rules:
        for grant in rule.grants:
            conn.revoke_security_group(group_id=security_group.id, ip_protocol=rule.ip_protocol,
                                           from_port=rule.from_port, to_port=rule.to_port,
                                           src_security_group_group_id=grant.group_id,
                                           cidr_ip=grant.cidr_ip)

    for rule in security_group.rules_egress:
        for grant in rule.grants:
            conn.revoke_security_group_egress(security_group.id, rule.ip_protocol,
                                                  rule.from_port, rule.to_port,
                                                  grant.group_id, grant.cidr_ip)

def is_main_route_table(route_table):
    for association in route_table.associations:
        if association.main:
            return True

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        resource_tags=dict(type='dict', required=True)
    ))
    module = AnsibleModule(argument_spec=argument_spec)

    ec2_url, aws_access_key, aws_secret_key, region = get_ec2_creds(module)

    if not region:
        module.fail_json(msg="region must be specified")

    try:
        connection = boto.vpc.connect_to_region(
            region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key)
    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg=str(e))

    vpcs = connection.get_all_vpcs()
    vpcs_w_resources = filter(
        lambda x: x.tags == module.params.get('resource_tags'), vpcs)
    if len(vpcs_w_resources) != 1:
        if len(vpcs_w_resources) == 0:
            module.fail_json(msg="No vpc found")
        else:
            module.fail_json(msg="Multiple VPCs with specified resource_tags")

    vpc = vpcs_w_resources[0]
    
    try:
        # need an ec2 connection to delete SGs
        conn = boto.ec2.connect_to_region(
            region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key)
    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg=str(e))

    security_groups = [gp for gp in conn.get_all_security_groups() if gp.vpc_id == vpc.id]

    for security_group in security_groups:
        clear_all_permissions(conn, security_group)

    if len(security_groups) > 1:
        time.sleep(5)

    for security_group in security_groups:
        # default security group is deleted when the VPC is deleted
        if security_group.name != 'default':
            security_group.delete()

    for subnet in connection.get_all_subnets(filters = {'vpc-id': vpc.id}):
        connection.delete_subnet(subnet.id)

    for route_table in connection.get_all_route_tables(filters = {'vpc-id': vpc.id}):
        # main route table is deleted when the VPC is deleted
        if not is_main_route_table(route_table):
            connection.delete_route_table(route_table.id)

    for internet_gateway in connection.get_all_internet_gateways(filters={'attachment.vpc-id': vpc.id}):
        connection.detach_internet_gateway(internet_gateway.id, vpc.id)
        connection.delete_internet_gateway(internet_gateway.id)

    connection.delete_vpc(vpc.id)
    
    facts = {}
    module.exit_json(changed=False, ansible_facts=facts)

main()
