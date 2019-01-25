# -*- coding:utf-8 -*-

"""
此脚本用于在gitlab项目中生成Webhooks
"""

import sys
from upsource_hub_api.UpsourceClient import UpsourceClient
from gitlab_api.base import gitlabapi
from jenkins_api.base_api import jenkinsapi
import datetime

if __name__ == '__main__':
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    print("Today: " + today)

    gitlab_config = {
        "gitlab_url": "http://git.*.work",
        "email": "****",
        "password": "****"
    }

    # 连接gitlab
    try:
        gitlab_client = gitlabapi(**gitlab_config)
        print("Connect Gitlab Server Successful")
    except:
        print("Connect Gitlab Server Failed")
        sys.exit(1)

    upsource_config = {
        "base_url": "http://upsource.*.work",
        "username": "****",
        "password": "****"
    }
    # 连接Upsource
    try:
        client = UpsourceClient(**upsource_config)
        print("Connect Upsource Successful")
    except:
        print("Connect Upsource Failed")
        sys.exit(1)

    jenkins_config = {
        "jenkins_url": "http://sonar.jenkins.*.work/",
        "username": "****",
        "password": "****"
    }
    # 连接jenkins
    try:
        jenkins_client = jenkinsapi(**jenkins_config)
        print("Connect Jenkins Successful")
    except:
        print("Connect Jenkins Failed")
        sys.exit(1)

    # 获取upsource所有项目的名称
    upsource_project_names = client.get_all_project_names()

    # 获取所有jenkins项目
    jenkins_jobs = jenkins_client.get_jobs_name()

    #获取gitlab所有项目
    all_gitlab_projects = gitlab_client.projects().list_projects(simple=True)

    #获取gitlab所有分组
    all_gitlab_groups = gitlab_client.groups().keys()

    for item in all_gitlab_projects:
        gitlab_project_path = item['path_with_namespace']
        gitlab_group = gitlab_project_path.split('/')[0]
        gitlab_project_id = item['id']

        upsource_project_key = gitlab_project_path.replace('/', '-').replace('.', '-')
        upsource_hook_url = 'http://upsource.*.work/~vcs/' + upsource_project_key

        job_key = gitlab_project_path.replace('/', '-')
        sonar_jenkins_hook_url = 'http://sonar.jenkins.*.work/project/' + job_key

        if gitlab_group in all_gitlab_groups:
            # 已存在的hook url
            project_hook_urls = [h['url'] for h in gitlab_client.projects().list_project_hooks(gitlab_project_id)]

            # 为upsource项目创建webhook
            if gitlab_project_path in upsource_project_names and upsource_hook_url not in project_hook_urls:
                try:
                    gitlab_client.projects().add_project_hook(gitlab_project_id, upsource_hook_url)
                    print("Create Upsource hook url for project {} Successful.".format(gitlab_project_path))
                except Exception as err:
                    print("Create Upsource hook url for project {} Failed.".format(gitlab_project_path) + str(err))

            # 为Jenkins(sonar)项目创建webhook
            if job_key in jenkins_jobs and sonar_jenkins_hook_url not in project_hook_urls:
                try:
                    gitlab_client.projects().add_project_hook(gitlab_project_id, sonar_jenkins_hook_url)
                    print("Create Jenkins hook url for project {} Successful.".format(job_key))
                except Exception as err:
                    print("Create Jenkins hook url for project {} Failed.".format(job_key) + str(err))
