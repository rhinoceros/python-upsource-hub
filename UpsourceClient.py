#-*- coding:utf-8 -*-
import json
import requests

class ConnectionError(Exception):
    pass

# Makes HTTP requests to the Upsource API

class UpsourceClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.url = base_url + '/~rpc/'
        self.auth = (username, password)
        self.headers = {'Content-Type': 'application/json'}

    def __repr__(self):
        return '{}'.format(self.base_url)

    def GET(self, method, request=None):
        response = requests.get(self.url + method, auth=self.auth, params={'params': json.dumps(request)} if request else '')
        self.__check_response(response)
        if 'result' in response.json():
            return response.json()['result']

    def POST(self, method, data):
        response = requests.post(self.url + method, auth=self.auth, headers=self.headers, data=json.dumps(data))
        self.__check_response(response)

    @staticmethod
    def __check_response(response):
        if response.status_code != 200:
            raise ConnectionError("Response: {} {}".format(response.status_code, response.text))

    #获取所有项目id
    def get_all_project_ids(self):
        projects = self.GET('getAllProjects')
        if projects:
            project_ids = [project['projectId'] for project in projects['project']]
        else:
            project_ids = []
        return project_ids

    #获取所有项目名称
    def get_all_project_names(self):
        projects = self.GET('getAllProjects')
        if projects:
            project_names = [project['projectName'] for project in projects['project']]
        else:
            project_names = []
        return project_names

    #获取项目属性(其中包含归属组信息)
    def get_project_attribute(self, project_id):
        projects_attribute = self.GET('getProjectInfo', {'projectId': project_id})
        return projects_attribute

    #获取项目设置
    def load_project_settings(self, project_id):
        settings = self.GET('loadProject', {'projectId': project_id})
        return settings

    #重新设置项目属性
    def edit_project_settings(self, project_id, project_settings):
        self.POST('editProject', {'projectId': project_id, 'settings': project_settings})

    #创建项目
    def create_project(self, project_id, project_settings):
        self.POST('createProject', {'newProjectId': project_id, 'settings': project_settings})

    #删除项目
    def delete_project(self, project_id):
        self.POST('deleteProject', {'projectId': project_id})

    #重置项目
    def reset_project(self, project_id):
       self.POST('resetProject', {'projectId': project_id})

    #获取用户信息
    def load_user_info(self, user_id):
        infos = self.GET('getUserInfo', {'ids': user_id})['infos'][0]
        if 'login' in infos:
            return infos
        else:
            return None

    #将用户添加到项目中
    def add_user_to_project(self, project_id, user_id):
        self.POST('addUserRole', {'projectId': project_id, 'userId': user_id, 'roleKey': 'developer'})

    #将用户从项目中移除
    def delete_user_from_project(self, project_id, user_id):
        self.POST('deleteUserRole', {'projectId': project_id, 'userId': user_id, 'roleKey': 'developer'})

    #获取用户在项目中的权限
    def load_user_roles_in_project(self, project_id):
        user_roles = self.GET('getUsersRoles', {'projectId': project_id, 'offset': 0, 'pageSize': 1000})
        return user_roles
