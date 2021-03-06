"""
These are utility methods that can be used within the controller methods to
parse the json responses from the various knowledge sources. Each knowledge
source returns a different json structured response, and we do not want our
response parser to be agnostic about which knowledge source we're retreiving.
These methods are fallible heuristics for pulling the relevant information out
of those variable responses.
"""

import requests
from typing import List
from flask import abort

bioentities_endpoint = 'http://biothings.io/explorer/api/v2/metadata/bioentities'

_category_map = None

def lookup_category(prefix:str) -> str:
    """
    Returns the category that this prefix belongs to
    """
    global _category_map

    if _category_map == None:
        response = requests.get(bioentities_endpoint)

        if response.ok:
            _category_map = {}
            data = response.json()
            for category, prefixes in data['bioentity'].items():
                for prefix in prefixes:
                    _category_map[prefix.lower()] = category
        else:
            abort(500, 'Could not connect to: {}'.format(bioentities_endpoint))

    return _category_map.get(prefix.lower())

def safe_get(d:dict, *vkeys) -> object:
    """
    Chains together multiple dict.get calls safely, returning None if they
    cannot be performed.

    >> d = {'x' : {'y' : 'z'}}
    >> safe_get(d, 'x', 'y')
    'z'
    """
    try:
        for key in vkeys:
            d = d.get(key)
        return d
    except:
        return None

def get_apis(sources:List[str], targets:List[str]=None, relation:str=None, categories:List[str]=None):
    """
    Returns the API's that fulfill the given search constraints
    """

    pattern = re.compile('\{.*\}')

    from biothings_explorer_test import APILocator
    locator = APILocator()

    source_apis = []

    for source_id in sources:
        prefix, identifier = source_id.split(':', 1)
        source_apis.extend(locator.locate_apis_by_input_prefix_only(input_prefix=prefix.lower()))

    if categories != None:
        source_apis = [a for a in source_apis if a['object']['semantic_type'] in categories]

    if relation != None:
        source_apis = [a for a in source_apis if a['predicate'] == relation]

    if targets != None:
        target_prefixes = [t.split(':')[0].lower() for t in targets if ':' in t]
        source_apis = [a for a in source_apis if a['object']['prefix'] in target_prefixes]

    return source_apis

# @deprecated
def is_object(obj):
    """
    A json object will be an object if it has a:
        - id
        - name (or label)

    *Remember, we're assuming the category from the endpoint used.

    If a json object contains keys that contain all three fields, then it will
    be chosen. We also want to extract these values (as well as others, e.g.
    a description if possible). If there are multiple keys that contain the term
    "name", then we will take the shortest match. E.g. between keys:
        - "chebi_name"
        - "iupac_names"
    we will take "chebi_name".
    """
    if isinstance(obj, dict):
        is_identified = any('id' in k.lower() for k in obj.keys())
        is_named = any('name' in k.lower() for k in obj.keys())

        return is_identified and is_named
    else:
        return False

# @deprecated
def collect_objects(obj, identifiers=('id', '_id')):
    """
    Recursively searches for the highest level json objects containing a given
    identifier as a key, and returns them all. This is intended to cut through
    extra metadata in json responses that do not contain identified objects.

    Note: In the future should we require that identifiers not only be strings
          but also be curies? A number of the knowledge sources do not work with
          curies, though.
    """
    if isinstance(obj, (list, tuple, set)):
        generator = (collect_objects(item, identifiers) for item in obj)
        return [item for item in generator if item != None and item != []]
    elif isinstance(obj, dict):
        if is_object(obj):
            return obj
        else:
            for key, value in obj.items():
                result = collect_objects(value, identifiers)
                if result != None and result != []:
                    return result
    return []

# @deprecated
def get_recursive(d, key, default=None):
    """
    Gets the value of the highest level key in a json structure.

    key can be a list, will match the first one
    """
    if isinstance(key, (list, tuple, set)):
        for k in key:
            value = get_recursive(d, k)
            if value != None:
                return value
    else:
        if isinstance(d, dict):
            return d[key] if key in d else get_recursive(list(d.values()), key)

        elif isinstance(d, (list, tuple, set)):
            for item in d:
                value = get_recursive(item, key)
                if value != None:
                    return value

    return default
