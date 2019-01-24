# -*- coding:utf-8 -*-

import requests
from common import copy_dict
from common import ClientError, AuthError, ValidationError, ServerError
import base64

class HubClient:
    RULES_USERS_ENDPOINT = '/api/rest/users'
    RULES_USERS_INVITE_ENDPOINT = '/api/rest/users/invite'
    RULES_USERS_MERGE_ENDPOINT = '/api/rest/users/merge'
    RULES_USERGROUPS_ENDPOINT = '/api/rest/usergroups'
    RULES_PROJECTS_ENDPOINT = '/api/rest/projects'
    RULES_AVATAR_ENDPOINT = '/api/rest/avatar'
    RULES_PROJECT_ROLES_ENDPOINT = '/api/rest/projectroles'
    RULES_RESOURCES_ENDPOINT = '/api/rest/resources'

    def __init__(self, hub_url = None, username = None, password = None, token=None):
        """
        Set connection info and session, including auth (if username + password
        and/or auth token were provided).
        """
        self._url = hub_url
        self._session = requests.Session()

        #: Headers that will be used in request to Hub
        self.headers = {}

        if username and password:
             self._http_auth = requests.auth.HTTPBasicAuth(username, password)

    def __repr__(self):
        return '{}'.format(self._url)

    def _get_url(self, endpoint):
        """
        Return the complete url including host and port for a given endpoint.

        :param endpoint: service endpoint as str
        :return: complete url (including host and port) as str
        """
        if endpoint.startswith('http://') or endpoint.startswith('https://'):
            return endpoint
        else:
            return '{}{}'.format(self._url, endpoint)

    def _create_headers(self, content_type=None):
        request_headers = self.headers.copy()
        if content_type is not None:
            request_headers['Content-type'] = content_type
        return request_headers

    def _get_session_opts(self, content_type):
        return {
            'headers': self._create_headers(content_type),
            'auth': self._http_auth,
        }

    def http_request(self, verb, endpoint, query_data={}, post_data=None, files=None, **kwargs):
        """Make an HTTP request to the Gitlab server.

        Args:
            verb (str): The HTTP method to call ('get', 'post', 'put',
                        'delete')
            endpoint (str): Path or full URL to query ('/api/rest/projects' or
                        'http://whatever/api/rest/projects')
            query_data (dict): Data to send as query parameters
            post_data (dict): Data to send in the body (will be converted to
                              json)
            files (dict): The files to send to the server
            **kwargs: Extra options to send to the server (e.g. sudo)

        Returns:
            A requests result object.
        """

        url = self._get_url(endpoint)
        params = {}
        copy_dict(params, query_data)
        copy_dict(params, kwargs)
        
        opts = self._get_session_opts(content_type='application/json')

        # We need to deal with json vs. data when uploading files
        if files:
            data = post_data
            json = None
            del opts["headers"]["Content-type"]
        else:
            json = post_data
            data = None

        result = self._session.request(verb, url, json=json, data=data, params=params,
                               files=files, **opts)
        self.__check_response(result)
        return result

    def http_get(self, endpoint, query_data={}, **kwargs):
        """
        Make a GET request to the Hub server.

        Args:
            endpoint (str): endpoint or full URL to query 
            query_data (dict): Data to send as query parameters
            **kwargs: Extra options to send to the server (e.g. sudo)
        """
        result = self.http_request('get', endpoint, query_data=query_data, **kwargs)
        return result

    def http_post(self, endpoint, query_data={}, post_data={}, files=None,
                  **kwargs):
        """
        Make a POST request to the Hub server.

        Args:
            endpoint (str): endpoint or full URL to query 
            query_data (dict): Data to send as query parameters
            post_data (dict): Data to send in the body (will be converted to
                              json)
            files (dict): The files to send to the server
            **kwargs: Extra options to send to the server (e.g. sudo)

        Returns:
            The parsed json returned by the server.
        """
        result = self.http_request('post', endpoint, query_data=query_data,
                                   post_data=post_data, files=files, **kwargs)
        return result

    def http_put(self, endpoint, query_data={}, post_data={}, files=None,
                 **kwargs):
        """Make a PUT request to the Hub server.

        Args:
            endpoint (str): endpoint or full URL to query
            query_data (dict): Data to send as query parameters
            post_data (dict): Data to send in the body (will be converted to
                              json)
            files (dict): The files to send to the server
            **kwargs: Extra options to send to the server (e.g. sudo)

        Returns:
            The parsed json returned by the server.
        """
        result = self.http_request('put', endpoint, query_data=query_data,
                                   post_data=post_data, files=files, **kwargs)
        return result

    def http_delete(self, endpoint, **kwargs):
        """Make a PUT request to the Hub server.

        Args:
            endpoint (str): endpoint or full URL to query
            **kwargs: Extra options to send to the server (e.g. sudo)

        Returns:
            The requests object.
        """
        return self.http_request('delete', endpoint, **kwargs)

    # Analyse response status and return or raise exception
    # Note: redirects are followed automatically by requests
    @staticmethod
    def __check_response(res):
        if res.status_code < 300:
            # OK, return http response
            pass
        elif res.status_code == 400:
            # Validation error
            raise ValidationError("Response: {} {}".format(res.status_code, res.reason))
        elif res.status_code in (401, 403):
            # Auth error
            raise AuthError("Response: {} {}".format(res.status_code, res.reason))
        elif res.status_code < 500:
            # Other 4xx, generic client error
            raise ClientError("Response: {} {}".format(res.status_code, res.reason))
        else: 
            # 5xx is server error
            raise ServerError("Response: {} {}".format(res.status_code, res.reason))
    
    @staticmethod
    def getall(fn, params, search_key, *args, **kwargs):
        """
        Auto-iterate over the paginated results of various methods of the API.
        Pass the http method as the first argument, followed by the
        other parameters as normal. Include `page` to determine first page to poll.
        Remaining kwargs are passed on to the called method, including `per_page`.

        :param fn: Actual method to call
        :param page: Optional, page number to start at, defaults to 0
        :param args: Positional arguments to actual method
        :param kwargs: Keyword arguments to actual method
        :return: Yields each item in the result until exhausted, and then implicit StopIteration; or no elements if error
        """
        skip = 0
        while True:
            params['$skip'] = skip
            results = fn(*args, **kwargs)

            skip += params['$top']
            if search_key in results.json():
                for prj in results.json()[search_key]:
                    yield prj

                if len(results.json()[search_key]) != params['$top']:
                    break
            else:
                break

    def get_user(self, user_id, fields=None):
        """
        获取指定用户的信息
        :param user_id:
        :param fields:
        :return:
        """
        params = {}
        if fields:
            params['fields'] = fields
        resp = self.http_get(self.RULES_USERS_ENDPOINT + '/' + user_id, query_data=params)
        return resp.json()

    def get_all_users(self, fields=None):
        """
        获取所有用户信息
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'users', self.RULES_USERS_ENDPOINT, query_data=params)

    def create_user(self, login, name, profile, VCSUserNames, fields=None):
        """
        创建用户
        :param login:
        :param name:
        :param profile:
        :param VCSUserNames:
        :param fields:
        :return:
        """
        user_data = {
            'login': login,
            'profile': profile,
            'VCSUserNames': VCSUserNames,
            'name': name
        }

        params = {}
        if fields:
            params['fields'] = fields

        res = self.http_post(self.RULES_USERS_ENDPOINT, query_data=params, post_data=user_data)
        return res.json()

    def update_existing_user(self, user_id, user_data):
        """
        更新user
        :param user_id:
        :param user_data:
        :return:
        """
        self.http_post(self.RULES_USERS_ENDPOINT + '/' + user_id, post_data=user_data)

    def delete_user(self, user_id):
        """
        删除指定用户
        :param user_id:
        :return:
        """
        self.http_delete(self.RULES_USERS_ENDPOINT + '/' + user_id)

    def update_user_avatar(self, user_id, avatar_content):
        """
        更新用户头像
        :param user_id:
        :param avatar_content:
        :return:
        """
        user_info = self.get_user(user_id)
        base64_data = base64.b64encode(avatar_content)

        user_info['profile']['avatar'] = {
            "type": "urlavatar", 
            "avatarUrl": "data:image/jpeg;base64,{}".format(base64_data)
        }

        self.http_post(self.RULES_USERS_ENDPOINT + '/' + user_id, post_data=user_info)

    def update_user_email_verified(self, user_id, email_verified):
        """
        更新用户邮箱授权
        :param user_id:
        :param email_verified:
        :return:
        """
        user_info = self.get_user(user_id)
        user_info['profile']['email']['verified'] = email_verified
        self.http_post(self.RULES_USERS_ENDPOINT + '/' + user_id, post_data=user_info)

    def get_groups_of_user(self, user_id, fields=None):
        """
        Get All Groups of a User
        :param user_id:
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'groups', self.RULES_USERS_ENDPOINT + '/' + user_id + '/groups', query_data=params)

    def get_user_group(self, user_group_id, fields=None):
        """
        Get User Group
        :param user_group_id:
        :param fields:
        :return:
        """
        params = {}
        if fields:
            params['fields'] = fields
        resp = self.http_get(self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id, query_data=params)
        return resp.json()

    def get_all_user_groups(self, fields=None):
        """
        Get All User Groups
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'usergroups', self.RULES_USERGROUPS_ENDPOINT, query_data=params)

    def create_user_group(self, user_group, fields=None):
        """
        Create New User Group
        :param user_group:
        :param fields:
        :return:
        """
        params = {}
        if fields:
            params['fields'] = fields

        response = self.http_post(self.RULES_USERGROUPS_ENDPOINT, query_data=params, post_data=user_group)
        return response.json()

    def delete_user_group(self, user_group_id):
        """
        Delete Existing User Group
        :param user_group_id:
        :return:
        """
        self.http_delete(self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id)

    def update_existing_user_group(self, user_group_id, user_group_data):
        """
        Update Existing User Group
        :param user_group_id:
        :param user_group_data:
        :return:
        """
        self.http_post(self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id, post_data=user_group_data)

    def get_users_of_user_group(self, user_group_id, fields=None):
        """
        Get All Users of a User Group
        :param user_group_id:
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'users', self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id + '/users', query_data=params)

    def get_user_from_users_of_user_group(self, user_group_id, user_id, fields=None):
        """
        Get User from Users of a User Group
        :param user_group_id:
        :param user_id:
        :param fields:
        :return:
        """
        params = {}
        if fields:
            params['fields'] = fields
        resp = self.http_get(self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id + '/users/' + user_id, query_data=params)
        return resp.json()

    def add_user_to_users_of_user_group(self, user_group_id, user):
        """
        Add User to Users of a User Group
        :param user_group_id:
        :param user:
        :return:
        """
        self.http_post(self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id + '/users', post_data=user)

    def remove_user_from_users_of_user_group(self, user_group_id, user_id):
        """
        Remove User from Users of a User Group
        :param user_group_id:
        :param user_id:
        :return:
        """
        self.http_delete(self.RULES_USERGROUPS_ENDPOINT + '/' + user_group_id + '/users/' + user_id)

    def get_project_roles_of_usergroup(self, usergroup_id, fields=None):
        """
        Get All Project Roles of a User Group
        :param usergroup_id:
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'projectroles', self.RULES_USERGROUPS_ENDPOINT + '/' + usergroup_id + '/projectroles', query_data=params)

    def add_project_role_to_project_roles_of_usergroup(self, usergroup_id, project_role):
        """
        Add Project Role to Project Roles of a User Group
        :param usergroup_id:
        :param project_role:
        :return:
        """
        self.http_post(self.RULES_USERGROUPS_ENDPOINT + '/' + usergroup_id + '/projectroles', post_data=project_role)

    def get_project(self, project_id, fields=None):
        """
        获取指定project的信息
        :param project_id:
        :param fields:
        :return:
        """
        params = {}
        if fields:
            params['fields'] = fields
        resp = self.http_get(self.RULES_PROJECTS_ENDPOINT + '/' + project_id, query_data=params)
        return resp.json()

    def get_all_projects(self, fields=None):
        """
        获取所有project的信息
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'projects', self.RULES_PROJECTS_ENDPOINT, query_data=params)

    def delete_project(self, project_id):
        """
        删除指定project
        :param project_id:
        :return:
        """
        self.http_delete(self.RULES_PROJECTS_ENDPOINT + '/' + project_id)

    def create_project(self, key, name, resources, fields=None):
        """
        创建project
        :param key:
        :param name:
        :param resources:
        :param fields:
        :return:
        """
        project_data = {
            'key': key,
            'name': name,
            'resources': resources
        }

        params = {}
        if fields:
            params['fields'] = fields

        res = self.http_post(self.RULES_PROJECTS_ENDPOINT, query_data=params, post_data=project_data)
        return res.json()

    def update_existing_project(self, project_id, project_data):
        """
        更新project
        :param project_id:
        :param project_data:
        :return:
        """
        self.http_post(self.RULES_PROJECTS_ENDPOINT + '/' + project_id, post_data=project_data)

    def get_teams_of_project(self, project_id, fields=None):
        """
        Get All Teams of a Project
        :param project_id:
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'teams', self.RULES_PROJECTS_ENDPOINT + '/' + project_id + '/teams', query_data=params)

    def add_team_to_teams_of_project(self, project_id, team_data):
        """
        Add Team to Teams of a Project
        :param project_id:
        :param team_data:
        :return:
        """
        self.http_post(self.RULES_PROJECTS_ENDPOINT + '/' + project_id + '/teams', post_data=team_data)

    def delete_team_from_teams_of_project(self, project_id, team_id):
        """
        Remove Team from Teams of a Project
        :param project_id:
        :param team_id:
        :return:
        """
        self.http_delete(self.RULES_PROJECTS_ENDPOINT + '/' + project_id + '/teams/' + team_id)

    def get_all_resources(self, fields=None):
        """
        Get All Resources
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'resources', self.RULES_RESOURCES_ENDPOINT, query_data=params)

    def get_all_project_roles_of_project(self, project_id, fields=None):
        """
        Get All Transitive Project Roles of a Project
        :param project_id:
        :param fields:
        :return:
        """
        top = 100
        params = {
            '$top': top
        }
        if fields:
            params['fields'] = fields
        return self.getall(self.http_get, params, 'transitiveprojectroles', self.RULES_PROJECTS_ENDPOINT + '/' + project_id + '/transitiveprojectroles', query_data=params)

    def get_project_role_from_project_roles_of_project(self, project_id, project_role_id, fields=None):
        """
        Get Transitive Project Role from Transitive Project Roles of a Project
        :param project_id:
        :param project_role_id:
        :param fields:
        :return:
        """
        params = {}
        if fields:
            params['fields'] = fields
        resp = self.http_get(self.RULES_PROJECTS_ENDPOINT + '/' + project_id + '/transitiveprojectroles/' + project_role_id, query_data=params)
        return resp.json()
