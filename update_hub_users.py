# -*- coding:utf-8 -*-

"""
此脚本用户在hub平台上同步gitlab用户（激活状态）数据
"""

import sys
from upsource_hub_api.HubClient import HubClient
import requests
import collections
import base64
import datetime
import pymysql
from gitlab_api.base import gitlabapi

reload(sys)
sys.setdefaultencoding('utf-8')

def get_hub_users(hub):
    """
    获取hub用户信息（邮箱、授权、ID）
    :param hub:
    :return:
    """
    hub_all_users = hub.get_all_users(fields='profile,id')
    Hub_User = collections.namedtuple('Hub_User', ['user_email','email_verified','user_id'])
    for user_info in hub_all_users:
        if 'email' in user_info['profile']:
            user_email = user_info['profile']['email']['email']
            email_verified = user_info['profile']['email']['verified']
            user_id = user_info['id']
            hub_user = Hub_User(user_email,email_verified,user_id)
            yield hub_user

if __name__ == '__main__':
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print('Today:' + today)

    dingtalkdb_config = {
        'host': '*.*.*.*',
        'port': 3306,
        'user': 'sonar',
        'password': 'sonar',
        'db': 'dingtalk_develop_members',
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
    }

    # 连接Dingtalk的数据库
    try:
        db = pymysql.connect(**dingtalkdb_config)
        print("Open Dingtalk Database Successful!")
        cursor = db.cursor()
    except Exception as err:
        print("Failed to Open Dingtalk Database!" + str(err))
        sys.exit(1)

    cursor.execute('select email, name, userid, avatar from dingtalk_members;')

    # 获取研发组内成员信息
    development_center_members_info = {item['email']: {'name': item['name'].decode('utf-8'), 'userid': item['userid'], 'avatar': item['avatar']} for item in cursor.fetchall()}

    # 关闭Dingtalk数据库
    db.close()
    print('Close Dingtalk Database.')

    # gitlab账号信息
    gitlab_config = {
        "gitlab_url": "http://git.*.work",
        "email": "****",
        "password": "****"
    }

    # 连接gitlab
    try:
        gitlab_client = gitlabapi(**gitlab_config)
        print("Connect Gitlab Server Successfull")
    except Exception as e:
        print("Connect Gitlab Server Failed: " + str(e))
        sys.exit(1)

    # hub配置信息
    hub_config = {
        'hub_url': 'http://upsource.*.work/hub',
        'hub_username': "****",
        'hub_password': "****"
    }

    # 连接hub
    hub_client = HubClient(hub_config['hub_url'], hub_config['hub_username'], hub_config['hub_password'])
    print('{} connect successfull.'.format(hub_client))

    # 获取hub中用户信息
    hub_all_users = list(hub_client.get_all_users(fields='profile,id,login'))
    hub_user_logins = [u['login'] for u in hub_all_users]
    hub_user_emails = [u['profile']['email']['email'] for u in hub_all_users if 'email' in u['profile']]
    hub_users_data = {u['login']: u['id'] for u in hub_all_users}

    # 获取gitlab用户信息
    gitlab_users_info = {item['email']: {'username': item['username'], 'name': item['name']} for item in gitlab_client.users().list_users(active='true')}

    # hub中需要创建的用户
    need_created_user_emails = list(set(gitlab_users_info.keys()) - set(hub_user_emails))

    for email in need_created_user_emails:
        user_name = gitlab_users_info[email]['name']
        login = gitlab_users_info[email]['username']

        if login not in hub_user_logins:
            profile = {
                "email": {
                    "email": "{}".format(email),
                    "type": "EmailJSON",
                    "verified": True
                }
            }

            # 获取用户头像
            if email in development_center_members_info:
                dingtalk_user_avatar_url = development_center_members_info[email]['avatar']
                if dingtalk_user_avatar_url:
                    response = requests.get(dingtalk_user_avatar_url)
                    avatar_content = response.content
                    base64_data = base64.b64encode(avatar_content)
                    profile['avatar'] = {
                        "type": "urlavatar",
                        "avatarUrl": "data:image/jpeg;base64,{}".format(base64_data)
                    }

            VCSUserNames = [
                {
                    "name": "{}".format(email)
                },
                {
                    "name": "{}".format(login)
                }
            ]

            # 创建hub用户
            try:
                hub_client.create_user(login, user_name, profile, VCSUserNames)
                print('create user {} in hub.'.format(login))
            except Exception as e:
                print(e)

        else:
            profile = {
                "email": {
                    "email": "{}".format(email),
                    "type": "EmailJSON",
                    "verified": True
                }
            }

            VCSUserNames = [
                {
                    "name": "{}".format(email)
                },
                {
                    "name": "{}".format(login)
                }
            ]

            user_data = {
                'login': login,
                'profile': profile,
                'VCSUserNames': VCSUserNames,
                'name': user_name
            }

            # 更新用户数据
            try:
                hub_client.update_existing_user(hub_users_data[login], user_data)
                print('update user {} in hub.'.format(login))
            except Exception as e:
                print(e)

