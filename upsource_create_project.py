# -*- coding:utf-8 -*-

"""
此脚本用于创建upsource项目
"""

import json
import sys
from upsource_hub_api.UpsourceClient import UpsourceClient
from gitlab_api.base import gitlabapi
from utils.common import judge_day
import time
import datetime
import pprint
import os
from gitlab_utils import get_gitlab_pages_project_info

def generate_project_settings(project_path, default_branch, project_type, maven_settings, vcsPrivateKey):
    """
    生成upsource项目配置
    :param project_path:
    :param default_branch:
    :param project_type:
    :param maven_settings:
    :param vcsPrivateKey:
    :return:
    """
    vcsUrl = 'git@git.weidai.work:{}.git'.format(project_path)
    mapping = {}
    mapping['id'] = ''
    mapping['key'] = vcsPrivateKey
    mapping['mapping'] = '/'
    mapping['url'] = vcsUrl
    mapping['vcs'] = 'git'
    vcs = {}
    vcs['mappings'] = [mapping]
    pattern = ''.join([word[0].upper() for word in project_path.replace('/','-').split('-')])

    # 初始化项目设置
    project_settings = {}
    project_settings['addMergeCommitsToBranchReview'] = False
    project_settings['authorCanCloseReview'] = True
    project_settings['authorCanDeleteReview'] = True
    project_settings['buildStatusReceiveToken'] = ''
    project_settings['checkIntervalSeconds'] = 43200
    project_settings['codeReviewIdPattern'] = pattern + '-CR-{}'
    project_settings['defaultBranch'] = default_branch
    project_settings['defaultEncoding'] = 'UTF-8'
    project_settings['gradleInitScript'] = ''
    project_settings['gradleProperties'] = ''
    project_settings['limitResolveDiscussion'] = True
    project_settings['mavenProfiles'] = ''
    project_settings['modelConversionSystemProperties'] = ''
    project_settings['projectName'] = project_path

    project_settings['skipFileContentsImport'] = ['*.bin','*.dll','*.exe','*.so'] 
    project_settings['vcsSettings'] = json.dumps(vcs)

    if project_type == 'java':
        project_settings['mavenSettings'] = maven_settings
        project_settings['projectModel'] = {'type':'maven', 'pathToModel':''}
        project_settings['javascriptLanguageLevel'] = 'none'
    else:
        project_settings['javascriptLanguageLevel'] = 'none'
        project_settings['projectModel'] = {'type':'none', 'pathToModel':''}

    project_settings['runInspections'] = False

    return project_settings

def judge_project_isready(client, project_id):
    """
    判断项目是否同步完成
    :param client:
    :param project_id:
    :return:
    """
    projects = client.GET('getAllProjects', {'projectId': project_id})
    return projects['project'][0]['isReady'] if projects else False

if __name__ == '__main__':
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print("Today: " + today)

    # Upsource server URL and login credentials
    upsource_config = {
        'upsource_url': 'http://upsource.*.work',
        'upsource_username': "****",
        'upsource_password': "****"
    }
    upsource_client = UpsourceClient(upsource_config['upsource_url'], upsource_config['upsource_username'], upsource_config['upsource_password'])
    print('{} connect successful.'.format(upsource_client))

    # 加载私钥
    script_path = os.path.split(os.path.realpath(__file__))[0]
    vcsPrivateKeyFile = 'id_rsa'
    with open(os.path.join(script_path, 'config', vcsPrivateKeyFile), "r") as fp:
        vcsPrivateKey = fp.read()

    # 加载maven setting文件
    maven_settings_File = 'settings.xml'
    with open(os.path.join(script_path, 'config', maven_settings_File), "r") as fp:
        maven_settings = fp.read()

    # gitlab账号信息
    gitlab_config = {
        "gitlab_url": "http://git.*.work",
        "email": "*",
        "password": "*"
    }
    # 连接gitlab服务器
    try:
        gitlab_client = gitlabapi(**gitlab_config)
        print("Connect Gitlab Successful")
    except Exception as e:
        print("Connect Gitlab Failed: " + str(e))
        sys.exit(1)

    # 获取所有项目
    project_ids = upsource_client.get_all_project_ids()

    # 过滤名单
    path_whitelist = ['cocoapods/QIYU_iOS_SDK',
'scm/csvn_conf',
'test/biaozhunjinjian-xinzengjiekuanren_cunguanzhanghujihuo',
'test/jinjianzhongxin-chexiaofeijinrongjiekoujichenghuaceshi',
'android/MicroWantBorrow',
'android/CreditLoan',
'fed/admin.bwcrm',
'scm/jenkins-fed-bak',
'wechat/credit.treasure',
'scm/jenkins-bak']
    group_whitelist = ['Component']
    all_gitlab_groups = list(set(gitlab_client.groups().keys()) - set(group_whitelist))

    project_infos = []
    #获取项目成员
    count_pages = 20
    start_page = 1
    while True:
        numbers, _, results = get_gitlab_pages_project_info(gitlab_client, all_gitlab_groups, start_page, start_page + count_pages, need_info="default_branch,last_activity_day,project_type")
        for project_path, value in results.items():
            project_id = value['project_id']
            default_branch = value['default_branch']
            last_activity_day = value['last_activity_day']
            project_type = value['project_type']
            if project_path not in path_whitelist and project_path.split('/')[0] in all_gitlab_groups and project_path.replace('/', '-').replace('.', '-') not in project_ids:
                if judge_day(last_activity_day, today) < 90:
                    if len(list(gitlab_client.projects().list_project_commits(project_id))):
                        project_infos.append((project_path, default_branch, project_type))
        start_page += count_pages
        if numbers != 20 * count_pages:
            break

    print('Creating Projects:')
    pprint.pprint(project_infos)

    while len(project_infos) != 0:
        project_path, default_branch, project_type = project_infos.pop()
        print('operating project: {}, default branch: {}, project_type: {}'.format(project_path, default_branch, project_type))
        #创建项目
        project_id = project_path.replace('/', '-').replace('.', '-')
        if project_id not in project_ids:
            try:
                project_settings = generate_project_settings(project_path, default_branch, project_type, maven_settings, vcsPrivateKey)
                upsource_client.create_project(project_id, project_settings)
                print('Create project {}'.format(project_path))
            except Exception as e:
                print(e)

        #等待项目同步完成，最多等待5分钟时间
        count = 0
        while not judge_project_isready(upsource_client, project_id) and count < 30:
            print('Waiting...')
            time.sleep(10)
            count += 1
