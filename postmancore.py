import difflib
import json
import re
import logging
from copy import copy
import requests

log = logging.getLogger(__name__)
from vc.raiden.pypostman.extractor import extract_dict_from_raw_headers, extract_dict_from_raw_mode_data, format_object


##########################################################################
#Helper Functions
##########################################################################
def normalize_class_name(string):
    string = re.sub(r'[?!@#$%^&*()_\-+=,./\'\\\"|:;{}\[\]]', ' ', string)
    return string.title().replace(' ', '')


def normalize_func_name(string):
    string = re.sub(r'[?!@#$%^&*()_\-+=,./\'\\\"|:;{}\[\]]', ' ', string)
    return '_'.join(string.lower().split())


class CaseInsensitiveDict(dict):
    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(key.upper(), value)

    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(key.upper())

    def update(self, d=None, **kwargs):
        d = d or {}
        for k, v in d.items():
            self[k.upper()] = v

class PostmanCore:
    def __init__(self, _collection_file_path, _config_file_path = None):
        try:
            with open(_collection_file_path, encoding='utf8') as coll_fd:
                self.__postman_collection = json.load(coll_fd)

            if not coll_fd:
                with open(_config_file_path, encoding='utf8') as conf_fd:
                    self.__postman_config = json.load(conf_fd)

            self.__folders = {}
            self.environments = CaseInsensitiveDict()
            self.__load()
        except Exception as e:
            log.error('Unable to open the Postman Collection {}'.format(e))

    def __load(self):
        id_to_request = dict()
        requests_list = {}
        for index, req in enumerate(self.__postman_collection['item']):
            id_to_request[index] = req

            req_data = id_to_request[index]
            requests_list[normalize_func_name(req['name'])] = PostmanRequest(self, req_data)

            col_name = normalize_class_name(req['name'])
            self.__folders[col_name] = PostmanPost(col_name, requests_list)

    def __getattr__(self, item):
        if item in self.__folders:
            return self.__folders[item]
        else:
            folders = list(self.__folders.keys())
            similar_folders = difflib.get_close_matches(item, folders)
            if len(similar_folders) > 0:
                similar = similar_folders[0]
                raise AttributeError('%s folder does not exist in Postman collection.\n'
                                     'Did you mean %s?' % (item, similar))
            else:
                raise AttributeError('%s folder does not exist in Postman collection.\n'
                                     'Your choices are: %s' % (item, ", ".join(folders)))

    def help(self):
        print("Possible methods:")
        for fol in self.__folders.values():
            print()
            fol.help()

class PostmanRequest:
    def __init__(self, core, data):
        self.name = normalize_func_name(data['name'])
        self.core = core
        self.request_kwargs = dict()

        if data['request']['body']['mode'] == 'raw' and 'rawModeData' in data['request']['body']:
            self.request_kwargs['json'] = extract_dict_from_raw_mode_data(data['request']['body']['mode'])
            # Validate the empty dictionary
            if not self.request_kwargs['json']:
                del(self.request_kwargs['json'])

        self.request_kwargs['headers'] = extract_dict_from_raw_headers(data['request']['header'])
        self.request_kwargs['method'] = data['request']['method']
        self.request_kwargs['url'] = data['request']['url']

    def __call__(self, *args, **kwargs):
        new_env = copy(self.core.environments)
        new_env.update(kwargs)
        formatted_kwargs = format_object(self.request_kwargs, new_env)
        url_bkp = formatted_kwargs['url']['raw']
        del(formatted_kwargs['url'])
        formatted_kwargs['url'] = url_bkp

        # Backing up and validating the headers
        if formatted_kwargs['headers']:
            header_bkp = formatted_kwargs['headers']
            del(formatted_kwargs['headers'])
            _header_key = header_bkp['key']
            _header_value = header_bkp['value']
            formatted_kwargs['headers'] = {}
            formatted_kwargs['headers'][_header_key] = _header_value

        return requests.request(**formatted_kwargs)

class PostmanPost:
    def __init__(self, name, requests_list):
        self.name = name
        self.__requests = requests_list

    def __getattr__(self, item):
        if item in self.__requests:
            return self.__requests[item]
        else:
            post_requests = list(self.__requests.keys())
            similar_requests = difflib.get_close_matches(item, post_requests, cutoff=0.0)
            if len(similar_requests) > 0:
                similar = similar_requests[0]
                raise AttributeError('%s request does not exist in %s folder.\n'
                                     'Did you mean %s' % (item, self.name, similar))
            else:
                raise AttributeError('%s request does not exist in %s folder.\n'
                                     'Your choices are: %s' % (item, self.name, ", ".join(post_requests)))

    def help(self):
        for req in self.__requests.keys():
            print("post_python.{COLLECTION}.{REQUEST}()".format(COLLECTION=self.name, REQUEST=req))

if __name__ == '__main__':
    pp = PostmanCore('/Users/xyz/Desktop/test/CRUD.postman_collection.json')
    pp.environments.update({'API_SERVER': 'disen.dev.abc.logi.com',
                            'ID_TOKEN': "eyJraWQiOiJJYkdCXC9UwRMCAsecret",
                            'ID_TOKEN_TTL': 3600,
                            'PROTOCOL': 'https'
                            })
    print(pp.SignIn.sign_in().json())
    print(pp.DeleteUser.delete_user().json())
    print(pp.CreateUser.get_user().json())
    print(pp.UpdateUser.update_user().json())
