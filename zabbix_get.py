#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
开发者：龚朝晖
版本：1.1
用途：获取zabbix告警持续时间
开发日期：2018.12.21
使用数据库：MySQL8.0.13
涉及到的表：zabbix_alert_record
使用的字段：trigger_id（触发器ID），priority（灾难级别），hostname（主机可见名），groups（主机所属组），description（触发器描述），
            lastchange（触发时间戳），recovery_time（恢复时间戳），alert_type（告警类型），duration（持续时间）

本次修复了duration在新增相同triggerid告警的时候数据会被全都被修改统一的问题
"""

from __future__ import unicode_literals
from __future__ import absolute_import
import datetime, time
import json
import requests
import pymysql




time = int(time.mktime(datetime.datetime.now().timetuple()))

db_host = '127.0.0.1'
db_user = 'root'
db_passwd = '345501'
db_name = 'zabbix'
db = pymysql.connect(db_host, db_user, db_passwd, db_name, charset='utf8')
cursor = db.cursor()


def get_database_data(): # 数据库中取得的数据
    sql = "SELECT trigger_id,lastchange FROM `zabbix_alert_record` WHERE `recovery_time` IS NULL" #从数据库表中筛选出没有恢复告警的对应的triggerid和时间戳
    cursor.execute(sql)
    data = cursor.fetchall()  # c从数据库中取出的旧版数据
    return data #


def insert_data(trigger_id,priority,hostname,groups,description,lastchange,alert_type):               #将数据插入mysql数据库的方法。有告警恢复，则表中添加新行
    sql = "INSERT INTO `zabbix_alert_record` \
    (`trigger_id`, `priority`, `hostname`, `groups`, `description`, `lastchange`, `alert_type`)" \
          " VALUES ('%s', '%s' , '%s', '%s', '%s', '%s', '%s')" \
          % \
          (trigger_id,priority,hostname,groups,description,lastchange,alert_type)
    cursor.execute(sql)


def update_data(trigger_id,lastchange):     #有告警恢复，根据对应的triggerid，输入恢复时间的时间戳和持续时间
    duration = time - lastchange            #持续时间
    sql = "UPDATE `zabbix_alert_record` SET `recovery_time` = '%s',`duration` = '%s' WHERE (`trigger_id` = '%s') AND `recovery_time` IS NULL  " % (time,str(duration),trigger_id)
    cursor.execute(sql)


def get_zabbix_token():                                                         #定义获取zabbix登陆token方法
    data = {                                                                    #接口需要的参数
        "jsonrpc": "2.0",
        "method": "user.login",
        "id": 1,
        "params": {
            "user": "zbxreader",
            "password": "zbxreader123"
        }
    }
    url = 'http://10.0.13.106/zabbix/api_jsonrpc.php/'                          #接口地址
    headers = {"Content-Type": "application/json"}                              #请求头数据
    response = requests.post(url, json.dumps(data), headers=headers).content    #封装数据以及请求头使用POST方法请求数据获取返回结果
    result = json.loads(response)['result']
    return result                                                               #获取返回的结果内容（本接口返回结果为token）


def get_zabbix_trigger():                                             #定义根据trigger_id获取zabbix触发器详细信息的方法
    data = {"jsonrpc": "2.0",
            "method": "trigger.get",
            "params": {
                "output": ["triggerid", "description", "priority","lastchange"],
                "filter": {"value": 1},
                "sortfield": "priority",
                "sortorder": "DESC",
                "min_severity": 4,
                "skipDependent": 1,
                "monitored": 1,
                "active": 1,
                "expandDescription": 1,
                "selectHosts": ['host'],
                "selectGroups": ['name'],
                "only_true": 1},
            "auth": token,
            "id": 1
            }
    url = 'http://10.0.13.106/zabbix/api_jsonrpc.php/'
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json.dumps(data), headers=headers).content
        result = json.loads(response)['result']
    except:
        result = {}
    return result


def get_zabbix_item(triggerid):         #根据zabbix的triggerid  获取监控项
    data = {"jsonrpc": "2.0",
            "method": "item.get",
            "params": {
                "output":"extend",
                "triggerids":triggerid
                },
            "auth": token,
            "id": 1
            }
    url = 'http://10.0.13.106/zabbix/api_jsonrpc.php/'
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json.dumps(data), headers=headers).content
        result = json.loads(response)['result'][0]['itemid']
    except:
        result = {}
    return result


def get_zabbix_application(itemid):    #根据监控项获取告警类型
    data = {"jsonrpc": "2.0",
            "method": "application.get",
            "params": {
                "output": "extend",
                "itemids": itemid
            },
            "auth": token,
            "id": 1
            }
    url = 'http://10.0.13.106/zabbix/api_jsonrpc.php/'
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json.dumps(data), headers=headers).content
        result1 = json.loads(response)['result']
        list = []
        for app_name in result1:
            list.append(app_name['name'])
        if 'CPU' in list or 'Filesystems' in list or 'Memory' in list:
            result = '性能'
        elif 'General' in list or 'OS' in list:
            result = '其他'
        else:
            result = '故障'
    except:
        result = '故障'
    return result


token = get_zabbix_token()


database_trigger_list = [] #定义数据库中的triggerid组成的list
database_data = get_database_data()
for j in database_data:
    database_trigger_list.append(str(j[0]))  #将原来从数据库中取得的数据转换成列表的形式


zabbix_trigger_list = []
zabbix_trigger = get_zabbix_trigger()
for e in zabbix_trigger:
    zabbix_trigger_list.append(e['triggerid']) ##将原来从数据库中取得的数据转换成列表的形式


for i in zabbix_trigger:
    if str(i['triggerid']) not in database_trigger_list:   #如果从zabbix拉去的最新数据里有triggerid不在数据库中，则说明该告警已经恢复
        insert_data(i['triggerid'], i['priority'], i['hosts'][0]['host'], i['groups'][0]['name'], i['description'], i['lastchange'], get_zabbix_application(get_zabbix_item(i['triggerid'])))  #表中在恢复的告警中插入新数据 恢复时间戳以及持续时间

for j in database_data:
    if str(j[0]) not in zabbix_trigger_list:  #从数据库里拉出的数据里有triggerid不在最新的zabbix中，说明有新告警增加
        update_data(str(j[0]),j[1])           #表中增加新告警

db.commit()
db.close()




