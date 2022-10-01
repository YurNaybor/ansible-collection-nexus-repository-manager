#!/usr/bin/python

# Some inspiration from
# - https://vincent.bernat.ch/en/blog/2020-custom-ansible-module
# - https://stackoverflow.com/a/8187408

from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
from ansible.errors import AnsibleError

import json

def repository_exists(module):
  ret = False

  base_url = module.params.get('url')

  api_endpoint = '/service/rest/v1/repositories/' + module.params.get('name')
  api_url = base_url + api_endpoint

  headers = {'Content-Type':'application/json'}

  resp, info = fetch_url(module,method="GET",url=api_url,headers=headers)

  if info["status"] == 200:
    ret = True
  elif info["status"] == 404:
    ret = False
  else:
    raise AnsibleError(r"Got unexpected response from Nexus: " + str(info))

  return ret

def get_repository_simple(module):
  repo = None

  base_url = module.params.get('url')

  # Careful, in case the format is empty the request silently fails(?)
  api_endpoint = '/service/rest/v1/repositories/' + module.params.get('name')
  api_url = base_url + api_endpoint

  headers = {'Content-Type':'application/json'}

  resp, info = fetch_url(module,method="GET",url=api_url,headers=headers)

  if info["status"] == 200:
    repo = json.loads(resp.read())
  elif info["status"] == 404:
    repo = None
  else:
    raise AnsibleError(r"Got unexpected response from Nexus: " + str(info))

  return repo

def get_repository(module):
  repo = None

  base_url = module.params.get('url')

  # Unfortunately Nexus' API is strange. Endpoints are named "maven", while the data contains "maven2"
  format = module.params.get('format')
  if format == "maven2":
    format = "maven"

  # Careful, in case the format is empty the request silently fails(?)
  api_endpoint = '/service/rest/v1/repositories/' + format + '/' + module.params.get('type') + '/' + module.params.get('name')
  api_url = base_url + api_endpoint

  headers = {'Content-Type':'application/json'}

  resp, info = fetch_url(module,method="GET",url=api_url,headers=headers)

  if info["status"] == 200:
    repo = json.loads(resp.read())
  elif info["status"] == 404:
    repo = None
  else:
    raise AnsibleError(r"Got unexpected response from Nexus: " + str(info))

  return repo

def prepare_wanted_repo(module):
  # Fill initial dict with basic attributes
  wanted_repo = {
      "name": module.params.get('name'),
      "format": module.params.get('format'),
      "type": module.params.get('type'),
      "online": True,
      "storage": {
        "blobStoreName": module.params.get('blob_store_name'),
        "strictContentTypeValidation": True,
      }
  }

  # Note: For now we only care for required attributes and leave many defaults
  if module.params.get('type') == 'proxy':
    proxy_dict = {
        "proxy": {
          "remoteUrl": module.params.get('remote_url'),
          "contentMaxAge": 1440,
          "metadataMaxAge": 1440
        },
        "negativeCache": {
          "enabled": True,
          "timeToLive": 1440
        },
        "httpClient": {
          "blocked": False,
          "autoBlock": True
        }
    }
    wanted_repo |= proxy_dict

    if module.params.get('format') == 'apt':
      apt_dict = {
          "apt": {
            "distribution": module.params.get('apt_distribution'),
            "flat": False
          }
      }
      wanted_repo |= apt_dict
    elif module.params.get('format') == 'maven2':
      maven_dict = {
          "maven": {
            "versionPolicy": "RELEASE",
            "layoutPolicy": "STRICT"
          }
      }
      wanted_repo |= maven_dict
    elif module.params.get('format') == 'docker':
      # If index type is REGISTRY, the index url can be empty
      index_url = ""
      if module.params.get('docker_index_url') != "":
        index_url = module.params.get('docker_index_url')

      docker_dict = {
          "docker": {
            "v1Enabled": module.params.get('docker_v1enabled'),
            "forceBasicAuth": module.params.get('docker_force_basic_auth'),
            "httpPort": module.params.get('docker_http_port')
          }
      }

      docker_proxy_dict = {
          "dockerProxy": {
            "indexType": module.params.get('docker_index_type'),
            "indexUrl": index_url
          }
      }
      wanted_repo |= docker_dict
      wanted_repo |= docker_proxy_dict

  return wanted_repo


def create_repository(module, repo):
  base_url = module.params.get('url')

  # Unfortunately Nexus' API is strange. Endpoints are named "maven", while the data contains "maven2"
  format = repo['format']
  if format == "maven2":
    format = "maven"

  api_endpoint = '/service/rest/v1/repositories/' + format + '/' + repo['type']
  api_url = base_url + api_endpoint

  headers = {'Content-Type':'application/json'}

  data = module.jsonify(repo)

  resp, info = fetch_url(module,method="POST",url=api_url,headers=headers,data=data)

  if info["status"] != 201:
    raise AnsibleError(r"Got unexpected response from Nexus: " + str(info))

def update_repository(module, repo):
  base_url = module.params.get('url')

  # Unfortunately Nexus' API is strange. Endpoints are named "maven", while the data contains "maven2"
  format = repo['format']
  if format == "maven2":
    format = "maven"

  api_endpoint = '/service/rest/v1/repositories/' + format + '/' + repo['type'] + '/' + repo['name']
  api_url = base_url + api_endpoint

  headers = {'Content-Type':'application/json'}

  data = module.jsonify(repo)

  resp, info = fetch_url(module,method="PUT",url=api_url,headers=headers,data=data)

  if info["status"] != 204:
    raise AnsibleError(r"Got unexpected response from Nexus: " + str(info))

def delete_repository(module):
  base_url = module.params.get('url')

  api_endpoint = '/service/rest/v1/repositories/' + module.params.get('name')
  api_url = base_url + api_endpoint

  headers = {'Content-Type':'application/json'}

  resp, info = fetch_url(module,method="DELETE",url=api_url,headers=headers)

  if info["status"] != 204:
    raise AnsibleError(r"Got unexpected response from Nexus: " + str(info))

# Merge dict recursively to get all attributes
# Taken from https://karthikbhat.net/recursive-dict-merge-python/
def merge(dict1, dict2):
  for key, val in dict1.items():
    if isinstance(val, dict):
      dict2_node = dict2.setdefault(key, {})
      merge(val, dict2_node)
    else:
      if key not in dict2:
        dict2[key] = val

  return dict2


def main():
    module_args = dict(
        # Basic and required args
        name=dict(type='str', required=True),
        state=dict(default='present', choices=['present', 'absent'], type='str'),
        url=dict(type='str', required=True),
        url_username=dict(type='str', required=True),
        url_password=dict(type='str', required=True, no_log=True),
        force_basic_auth=dict(type='bool', default=True),

        # General optional repo args
        type=dict(type='str', choices=['','proxy'], required=False),
        format=dict(type='str', choices=['', 'apt', 'raw', 'pypi', 'rubygems', 'docker', 'maven2'], required=False),
        blob_store_name=dict(default='default', type='str', required=False),

        # Type Proxy repo args
        remote_url=dict(type='str', required=False),

        # Format Apt repo args
        apt_distribution=dict(type='str', required=False),

        # Format Docker repo args
        docker_v1enabled=dict(type='bool', default=False, required=False),
        docker_force_basic_auth=dict(type='bool', default=False, required=False),
        docker_http_port=dict(type='int', default=None, required=False),
        docker_index_type=dict(type='str', default='REGISTRY', required=False, choices=['HUB', 'REGISTRY', 'CUSTOM'])
    )

    # TODO: validate params based on state and type / format

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    result = dict(
      changed=False,
      action="Nothing"
    )

    if module.params.get('state') == 'absent':
      if repository_exists(module) == True:
        existing_repo = get_repository_simple(module)
        result['existing_repo'] = existing_repo

        delete_repository(module)
        result['action'] = "Delete"
        result['changed'] = True
    else:
      wanted_repo = prepare_wanted_repo(module)
      result['wanted_repo'] = wanted_repo

      if repository_exists(module) == True:
        existing_repo = get_repository(module)
        result['existing_repo'] = existing_repo

        # Merge the existing and wanted repos to get values that we don't (yet) explicitely set and prevent accidental changes
        merged_repo = merge(existing_repo, wanted_repo)
        result['merged_repo'] = merged_repo

        if existing_repo != merged_repo:
          update_repository(module,wanted_repo)
          result['action'] = "Update"
          result['changed'] = True
        else:
          result['action'] = "Nothing"
          result['changed'] = False
      else:
        create_repository(module,wanted_repo)
        result['action'] = "Create"
        result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
