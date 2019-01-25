# -*- coding:utf-8 -*-

"""
此脚本用于更新hub用户权限，与gitlab保持一致
"""

import sys
from upsource_hub_api.HubClient import HubClient
from upsource_hub_api.UpsourceClient import UpsourceClient
import multiprocessing
from gitlab_utils import get_gitlab_group_members, get_gitlab_pages_project_info
import datetime
from gitlab_api.base import gitlabapi

def operate_hub_team_permission(gitlab_group, hub_client, hub_users, user_groups, gitlab_group_members):
    """
    处理hub team
    :param gitlab_group:
    :param hub_client:
    :param hub_users:
    :param user_groups:
    :param gitlab_group_members:
    :return:
    """
    team_name = gitlab_group + '-team'
    # 创建新的user group
    if team_name not in user_groups:
        user_group_data = {
            'name': team_name,
            'project': {'id': "0", 'name': "Global"}
        }
        res = hub_client.create_user_group(user_group_data)
        user_group_id = res['id']

        # 更新user_groups
        user_groups[team_name] = user_group_id

        print('create Group {}'.format(team_name))

        # 给新创建的group添加成员
        for m in gitlab_group_members[gitlab_group]:
            if m in hub_users:
                user_info = hub_client.get_user(hub_users[m])
                hub_client.add_user_to_users_of_user_group(user_group_id, user_info)
                print('add {} to {}'.format(m, team_name))

    else:
        user_group_id = user_groups[team_name]
        user_group_exist_users = hub_client.get_users_of_user_group(user_group_id, fields='login')
        existing_users = [u['login'] for u in list(user_group_exist_users)]

        need_add_users_to_user_group = list(set(gitlab_group_members[gitlab_group]) - set(existing_users))
        need_delete_users_from_user_group =  list(set(existing_users) - set(gitlab_group_members[gitlab_group]))

        # 更新组内成员
        for m in need_add_users_to_user_group:
            if m in hub_users:
                user_info = hub_client.get_user(hub_users[m])
                hub_client.add_user_to_users_of_user_group(user_group_id, user_info)
                print('add {} to {}'.format(m, team_name))

        for m in need_delete_users_from_user_group:
            if m in hub_users:
                user_id = hub_users[m]
                hub_client.remove_user_from_users_of_user_group(user_group_id, user_id)
                print('delete {} from {}'.format(m, team_name))

def operate_hub_project_permission(upsource_project_name, hub_client, upsource_client, hub_projects, hub_users, resources, user_groups, develop_role, gitlab_group_members, gitlab_project_members):
    """
    处理hub project权限
    :param upsource_project_name:
    :param hub_client:
    :param upsource_client:
    :param hub_projects:
    :param hub_users:
    :param resources:
    :param user_groups:
    :param develop_role:
    :param gitlab_group_members:
    :param gitlab_project_members:
    :return:
    """
    hub_project_key = upsource_project_name.replace('/','-').replace('.','-')
    # 创建hub project，将upsource的project关联起来,将hub project添加到hub team中，更新人员权限
    if hub_project_key not in hub_projects:
        hub_project_name = upsource_project_name
        hub_resource = []
        hub_resource.append(resources[hub_project_key])
        response = hub_client.create_project(hub_project_key, hub_project_name, hub_resource, fields = 'id')
        print('Create project {}'.format(hub_project_key))

        new_project_id = response['id']

        hub_team = upsource_project_name.split('/')[0] + '-team'

        project_role = {
            'project': {'id': new_project_id},
            'role': develop_role
        }
        # 获取team中存在project
        existing_project_roles_of_usergroup = list(hub_client.get_project_roles_of_usergroup(user_groups[hub_team], fields = 'project'))
        existing_project_id = [p['project']['id'] for p in existing_project_roles_of_usergroup if 'project' in p]

        if new_project_id not in existing_project_id:
            hub_client.add_project_role_to_project_roles_of_usergroup(user_groups[hub_team], project_role)
            print('add project {} to team {}'.format(hub_project_key,hub_team))

        # 给hub project添加人员权限
        gitlab_group = upsource_project_name.split('/')[0]
        if upsource_project_name in gitlab_project_members:
            need_add_users_to_hub_project = list(set(gitlab_project_members[upsource_project_name]) - set(gitlab_group_members[gitlab_group]))

            # 将用户添加到项目(project)权限中
            for m in need_add_users_to_hub_project:
                if m in hub_users:
                    user_id = hub_users[m]
                    upsource_client.add_user_to_project(hub_project_key, user_id)
                    print('Add user {} to project {}'.format(m, hub_project_key))
    else:
        hub_team = upsource_project_name.split('/')[0] + '-team'
        hub_project_id = hub_projects[hub_project_key]

        hub_project_owners = list(hub_client.get_all_project_roles_of_project(hub_project_id, fields='owner'))
        owner_ids = [p['owner']['id'] for p in hub_project_owners]

        # 判断hub project是否和对应的team关联
        if not user_groups[hub_team] in owner_ids:
            project_role = {
                'project': {'id': hub_project_id},
                'role': develop_role
            }
            hub_client.add_project_role_to_project_roles_of_usergroup(user_groups[hub_team], project_role)
            print('add project {} to team {}'.format(hub_project_key,hub_team))

        # 给hub project添加和删除人员权限
        gitlab_group = upsource_project_name.split('/')[0]

        hub_project_roles = list(hub_client.get_all_project_roles_of_project(hub_projects[hub_project_key], fields='owner,role'))
        hub_project_exits_developers = []
        for r in hub_project_roles:
            if r['role'] == develop_role:
                if 'login' in r['owner']:
                    hub_project_exits_developers.append(r['owner']['login'])
        if upsource_project_name in gitlab_project_members:
            need_add_users_to_hub_project = list(set(gitlab_project_members[upsource_project_name]) - set(hub_project_exits_developers) - set(gitlab_group_members[gitlab_group]))
            need_delete_users_from_hub_project =  list(set(hub_project_exits_developers) - set(gitlab_project_members[upsource_project_name]))
        else:
            need_add_users_to_hub_project = []
            need_delete_users_from_hub_project = hub_project_exits_developers

        # 将用户添加到项目(project)权限中
        for m in need_add_users_to_hub_project:
            if m in hub_users:
                user_id = hub_users[m]
                upsource_client.add_user_to_project(hub_project_key, user_id)
                print('Add user {} to project {}'.format(m, hub_project_key))
        # 删除多余的用户
        for m in need_delete_users_from_hub_project:
            if m in hub_users:
                user_id = hub_users[m]
                upsource_client.delete_user_from_project(hub_project_key, user_id)
                print('delete {} from {}'.format(m, hub_project_key))

if __name__ == '__main__':
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print("Today: " + today)

    # hub账号信息
    hub_config = {
        'hub_url': 'http://upsource.*.work/hub',
        'hub_username': "****",
        'hub_password': "****"
    }
    # 连接hub
    hub_client = HubClient(hub_config['hub_url'], hub_config['hub_username'], hub_config['hub_password'])
    print('{} connect successful.'.format(hub_client))

    # upsource账号信息
    upsource_config = {
        'upsource_url': 'http://upsource.*.work',
        'upsource_username': "****",
        'upsource_password': "****"
    }
    # 连接upsource
    upsource_client = UpsourceClient(upsource_config['upsource_url'], upsource_config['upsource_username'], upsource_config['upsource_password'])
    print('{} connect successful.'.format(upsource_client))

    # gitlab账号信息
    gitlab_config = {
        "gitlab_url": "http://git.*.work",
        "email": "****",
        "password": "****"
    }
    # 连接gitlab
    try:
        gitlab_client = gitlabapi(**gitlab_config)
        print("Connect Gitlab Successful")
    except Exception as e:
        print("Connect Gitlab Failed: " + str(e))
        sys.exit(1)

    # 获取gitlab groups
    group_ignore_list = ['Component']
    all_gitlab_groups = list(set(gitlab_client.groups().keys()) - set(group_ignore_list))

    # 获取gitlab组成员
    gitlab_group_members = get_gitlab_group_members(gitlab_client)

    # 获取项目成员
    count_pages = 20
    start_page = 1
    gitlab_project_members = {}
    while True:
        numbers, results, _ = get_gitlab_pages_project_info(gitlab_client, all_gitlab_groups, start_page, start_page + count_pages, need_info="members")
        gitlab_project_members.update(results)
        start_page += count_pages
        if numbers != 20 * count_pages:
            break

    develop_role = {
        'id': 'b72ba599-4e78-4714-abae-f50bdbb7fd3a',
        'key': 'developer',
        'name': 'Developer'
    }

    # 获取hub用户组信息
    user_groups_info = hub_client.get_all_user_groups(fields = 'name,id')
    user_groups = {u['name']: u['id'] for u in list(user_groups_info)}

    # 获取hub用户信息
    all_users_info = hub_client.get_all_users(fields='login,id')
    hub_users = {u['login']: u['id'] for u in list(all_users_info)}

    # 获取upsource上所有的项目名称
    upsource_projects_name = upsource_client.get_all_project_names()

    # 获取hub上所有的项目key
    hub_projects_info = hub_client.get_all_projects(fields = 'id,key')
    hub_projects = {hp['key']:hp['id'] for hp in list(hub_projects_info)}

    resources_info = hub_client.get_all_resources(fields = 'id,key,name')
    resources = {}
    for r in list(resources_info):
        resources[r['key']] = {
            'id': r['id'],
            'key': r['key'],
            'name': r['name']
    }

    # 用户更新共享数据
    user_groups_dict = multiprocessing.Manager().dict()
    for key, vaule in user_groups.items():
        user_groups_dict[key] = vaule

    # 使用多进程处理hub team权限分配
    pool1 = multiprocessing.Pool(4)
    for p in range(len(all_gitlab_groups)):
        pool1.apply_async(operate_hub_team_permission, args=(all_gitlab_groups[p], hub_client, hub_users, user_groups_dict, gitlab_group_members, ))
    pool1.close()
    pool1.join()

    # 使用多进程处理hub project权限分配
    pool2 = multiprocessing.Pool(4)
    for p in range(len(upsource_projects_name)):
        pool2.apply_async(operate_hub_project_permission, args=(upsource_projects_name[p], hub_client, upsource_client, hub_projects, hub_users, resources, user_groups_dict, develop_role, gitlab_group_members, gitlab_project_members, ))
    pool2.close()
    pool2.join()

