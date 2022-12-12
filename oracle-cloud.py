from requests import get, put
from time import sleep
from oci import config, wait_until
from oci import identity, core
from argparse import ArgumentParser
from os import system

system('clear')
print("=" * 25 + "\n😃  Integration Setup 😃\n" + "=" * 25 + "\n")

BASE_API_URL = "https://vmkbqkse7k.execute-api.us-east-1.amazonaws.com"
DESC = {"description": "Created Automatically by bin2bin"}
TAGS = {"definedTags": {"bin2bin": {"created-by": "bin2bin"}}}


def repeat_until_success(function):
    for _ in range(60):
        try:
            return function()
        except:
            sleep(3)
    raise Exception("Error waiting")


# Parse Arguments
print("🌼  Parsing Arguments ...", end="\r")
parser = ArgumentParser()
parser.add_argument('--token', type=str, required=True)
args = parser.parse_args()
print("✅  Parsed Arguments ...")

# Fetch SSH keys of machine
print("🌼  Fetching SSH public keys ...", end="\r")
auth_headers = {"Authorization": "Bearer " + args.token}
response = get(f"{BASE_API_URL}/custom/integration_details", headers=auth_headers)
public_key = response.json()["public_key"]
print("✅  Fetched SSH public keys ...")

# Creating all OCI clients with machine config
print("🌼  Initiating OCI clients ...", end="\r")
oci_config = config.from_file()
identity_client = identity.IdentityClient(oci_config)
print("✅  Initiated OCI clients ...")

# Switch clients to home region
print("🌼  Switching to home region ...", end="\r")
regions = identity_client.list_region_subscriptions(oci_config.get("tenancy")).data
oci_config["region"] = [x.region_name for x in regions if x.is_home_region][0]
identity_client = identity.IdentityClient(oci_config)
compute_client = core.ComputeClient(oci_config)
network_client = core.VirtualNetworkClient(oci_config)
print("✅  Switched to home region ...")

# Skip Or Create Tag Namespace
print("🌼  Creating Tag Namespace ...", end="\r")
namespaces = identity_client.list_tag_namespaces(compartment_id=oci_config.get("tenancy")).data
namespaces = [namespace for namespace in namespaces if namespace.name == "bin2bin"]
namespace_payload = {"compartmentId": oci_config.get("tenancy"), "name": "bin2bin", **DESC}
namespace = namespaces.pop() if len(namespaces) else identity_client.create_tag_namespace(namespace_payload).data
repeat_until_success(lambda: wait_until(identity_client, identity_client.get_tag_namespace(namespace.id), 'lifecycle_state', 'ACTIVE'))
print("✅  Created Tag Namespace Successfully ...")

# Skip Or Create Tag Namespace Key
print("🌼  Creating Tag Namespace Key ...", end="\r")
namespace_tags = identity_client.list_tags(tag_namespace_id=namespace.id).data
namespace_tags = [namespace_tag for namespace_tag in namespace_tags if namespace_tag.name == "created-by"]
namespace_tag_payload = {"name": "created-by", **DESC}
namespace_tag = namespace_tags.pop() if len(namespace_tags) else identity_client.create_tag(namespace.id, namespace_tag_payload).data
repeat_until_success(lambda: wait_until(identity_client, identity_client.get_tag(namespace.id, "created-by"), 'lifecycle_state', 'ACTIVE'))
print("✅  Created Tag Namespace Key ...")

# Skip or Creating user
print("🌼  Creating User ...", end="\r")
users = identity_client.list_users(compartment_id=oci_config.get("tenancy"), name="bin2bin").data
user_payload = {"compartmentId": oci_config.get("tenancy"), "name": "bin2bin", **DESC, **TAGS}
user = users.pop() if len(users) else identity_client.create_user(user_payload).data
repeat_until_success(lambda: wait_until(identity_client, identity_client.get_user(user.id), 'lifecycle_state', 'ACTIVE'))
print("✅  Created User Successfully ...")

# Updating api key
print("🌼  Uploading API Key ...", end="\r")
api_keys = [key for key in identity_client.list_api_keys(user.id).data if key.key_value.strip() == public_key.strip()]
api_key = api_keys.pop() if len(api_keys) else identity_client.upload_api_key(user.id, {"key": public_key}).data
print("✅  Uploaded API Successfully ...")

# Skip or Creating Group
print("🌼  Creating Group ...", end="\r")
groups = identity_client.list_groups(compartment_id=oci_config.get("tenancy"), name="bin2bin").data
group_payload = {"compartmentId": oci_config.get("tenancy"), "name": "bin2bin",  **DESC, **TAGS}
group = groups.pop() if len(groups) else identity_client.create_group(group_payload).data
repeat_until_success(lambda: wait_until(identity_client, identity_client.get_group(group.id), 'lifecycle_state', 'ACTIVE'))
print("✅  Created Group Successfully ...")

# Skip or Creating Group
print("🌼  Adding User to Group ...", end="\r")
memberships = identity_client.list_user_group_memberships(compartment_id=oci_config.get("tenancy"), user_id=user.id, group_id=group.id).data
membership_payload = {"userId": user.id, "groupId": group.id}
membership = memberships.pop() if len(memberships) else identity_client.add_user_to_group(membership_payload).data
print("✅  Added User to Group Successfully ...")

# Skip or Creating bin2bin compartment
print("🌼  Creating Compartment ...", end="\r")
compartments = identity_client.list_compartments(compartment_id=oci_config.get("tenancy"), name="bin2bin").data
compartment_payload = {"compartmentId": oci_config.get("tenancy"), "name": "bin2bin",  **DESC, **TAGS}
compartment = compartments.pop() if len(compartments) else identity_client.create_compartment(compartment_payload).data
repeat_until_success(lambda: wait_until(identity_client, identity_client.get_compartment(compartment.id), 'lifecycle_state', 'ACTIVE'))
print("✅  Created Compartment ...")

# Skip or Creating bin2bin policy
print("🌼  Creating Policy ...", end="\r")
policy_payload = {
    "name": "bin2bin-access", "compartmentId": oci_config.get("tenancy"), **DESC, **TAGS,
    "statements": [
        f"Allow group id {group.id} to manage all-resources in compartment id {compartment.id}",
        f"Allow group id {group.id} to manage all-resources in tenancy where target.resource.tag.bin2bin.created-by = 'bin2bin'",
    ]}
policies = identity_client.list_policies(compartment_id=oci_config.get("tenancy"), name="bin2bin-access").data
policy = policies.pop() if len(policies) else identity_client.create_policy(policy_payload).data
repeat_until_success(lambda: wait_until(identity_client, identity_client.get_policy(policy.id), 'lifecycle_state', 'ACTIVE'))
print("✅  Created Policy ...")

# Skip or Create default vitual cloud network
print("🌼  Creating Virtual Cloud Network ...", end="\r")
vcns = network_client.list_vcns(compartment_id=compartment.id, display_name="default").data
vcn_payload = {"compartmentId": compartment.id, "cidrBlock": "10.0.0.0/16", "displayName": "default", **TAGS}
vcn = vcns.pop() if len(vcns) else network_client.create_vcn(vcn_payload).data
repeat_until_success(lambda: wait_until(network_client, network_client.get_vcn(vcn.id), 'lifecycle_state', 'AVAILABLE'))
print("✅  Created Virtual Cloud Network ...")

# Skip or Create default security rules for virtual machine
print("🌼  Creating Security Rules ...", end="\r")
egress_security_rules = [
    {'isStateless': False, 'protocol': 'all', 'destination': '0.0.0.0/0', 'destinationType': 'CIDR_BLOCK'}]
ingress_security_rules = [
    {'isStateless': False, 'protocol': '6', 'source': '0.0.0.0/0', 'sourceType': 'CIDR_BLOCK', 'tcpOptions': {'destinationPortRange': {'max': 22, 'min': 22}}},
    {'isStateless': False, 'protocol': '17', 'source': '0.0.0.0/0', 'sourceType': 'CIDR_BLOCK', 'udpOptions': {'destinationPortRange': {'max': 51820, 'min': 51820}}}]
security_list_payload = {"egressSecurityRules": egress_security_rules, "compartmentId": compartment.id, "vcnId": vcn.id, "displayName": "default", "ingressSecurityRules": ingress_security_rules, **TAGS}
security_lists = network_client.list_security_lists(compartment_id=compartment.id, vcn_id=vcn.id, display_name="default").data
security_list = security_lists.pop() if len(security_lists) else network_client.create_security_list(security_list_payload).data
repeat_until_success(lambda: wait_until(network_client, network_client.get_security_list(security_list.id), 'lifecycle_state', 'AVAILABLE'))
print("✅  Created Security Rules ...")

# Skip or Create default internet gateway for virtual machine
print("🌼  Creating Internet Gateway ...", end="\r")
internet_gateways = network_client.list_internet_gateways(compartment_id=compartment.id, vcn_id=vcn.id, display_name="default").data
internet_gateway_payload = {"displayName": "default", "isEnabled": True, "compartmentId": compartment.id, "vcnId": vcn.id, **TAGS}
internet_gateway = internet_gateways.pop() if len(internet_gateways) else network_client.create_internet_gateway(internet_gateway_payload).data
repeat_until_success(lambda: wait_until(network_client, network_client.get_internet_gateway(internet_gateway.id), 'lifecycle_state', 'AVAILABLE'))
print("✅  Created Internet Gateway ...")

# Skip or Create default route table for default internet gateway
print("🌼  Creating Route Table ...", end="\r")
route_tables = network_client.list_route_tables(compartment_id=compartment.id, vcn_id=vcn.id, display_name="default").data
route_table_payload = {"displayName": "default", "vcnId": vcn.id, "compartmentId": compartment.id, "routeRules": [{"cidrBlock": "0.0.0.0/0", "networkEntityId": internet_gateway.id}], **TAGS}
route_table = route_tables.pop() if len(route_tables) else network_client.create_route_table(route_table_payload).data
repeat_until_success(lambda: wait_until(network_client, network_client.get_route_table(route_table.id), 'lifecycle_state', 'AVAILABLE'))
print("✅  Created Route Table ...")

# Skip or Create default subnet
print("🌼  Creating Subnet ...", end="\r")
subnets = network_client.list_subnets(compartment_id=compartment.id, vcn_id=vcn.id, display_name="default").data
subnet_payload = {"displayName": "default", "cidrBlock": "10.0.0.0/24", "routeTableId": route_table.id, "securityListIds": [security_list.id], "vcnId": vcn.id, "compartmentId": compartment.id, **TAGS}
subnet = subnets.pop() if len(subnets) else network_client.create_subnet(subnet_payload).data
repeat_until_success(lambda: wait_until(network_client, network_client.get_subnet(subnet.id), 'lifecycle_state', 'AVAILABLE'))
print("✅  Created Subnet ...")

# Get default availability zone for free instance
print("🌼  Fetching Availability Domain ...", end="\r")
availability_domains = identity_client.list_availability_domains(compartment_id=oci_config.get("tenancy")).data
for availability_domain in availability_domains:
    availability_domain.shapes = compute_client.list_shapes(oci_config.get("tenancy"), availability_domain=availability_domain.name).data
    availability_domain.free_shapes = [item for item in availability_domain.shapes if item.shape == "VM.Standard.E2.1.Micro"]
free_availability_domains = [item.name for item in availability_domains if len(item.free_shapes)]
availability_domain = free_availability_domains[0] if len(free_availability_domains) else availability_domain.name
print("✅  Fetched Availability Domain ...")

# Update the machine's public ip back to bin2bin
print("🌼  Updating Machine Config ...", end="\r")
payload = {
    "Compartment OCID": compartment.id, "User OCID": user.id, "Region": oci_config["region"],
    "Availability Domains": availability_domain, "Key Fingerprint": api_key.fingerprint,
    "Tenant OCID": oci_config.get("tenancy"), "Subnet OCID": subnet.id, "Policy OCID": policy.id}
put(f"{BASE_API_URL}/custom/integration_details", json={"config": payload}, headers=auth_headers)
print("✅  Updated Machine Config ...")

print("\n😃  Please go back to the bin2bin application to view machine status 😃\n")
