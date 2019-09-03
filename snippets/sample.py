#!/usr/bin/python
# coding: utf-8

from urllib.parse import urlparse
from datetime import datetime
import re
import urllib.parse
# RocketChatに投稿するモジュール群(自作、restAPI or webhook利用)
#import notificationToRocketChat
import requests
import json
import sys
import os


KEY_NOBUILD = 'nobuild'
KEY_EXCEEDED = 'exceed'

# jenkinsインスタンスの設定（Basic認証）
username = "admin"
password = "password"
mention = "@all"  # 全員に通知するときの文字列

# [パラメータで与えた数]*月前から、ビルドがないものを抽出
# ★実行日は1日想定なので、月末に動かすときは動作確認してください。


def get_jobs_inventory(jenkins_url, months):
    # apiで取得
    request_url = jenkins_url + "api/json?depth=2&tree=jobs" +\
        "[jobConfigHistory,displayName,buildable," +\
        "lastSuccessfulBuild[number,timestamp,result,url,duration]," +\
        "lastBuild[number,timestamp,result,url,duration]]"
    r = requests.get(request_url, auth=(username, password)).json()
    today = datetime.today()
    dt = datetime(today.year, today.month - months, today.day)
    print(dt)
    # print(str(r))
    notify_dict_no = []
    notify_dict_exceed = {}
    for job in r["jobs"]:
        if job["lastBuild"] is None:
            # 1度も動かしていないジョブ
            print('No builds\t' + job["displayName"])
            notify_dict_no.append(job["displayName"])
        else:
            lastbuildtime = datetime.fromtimestamp(
                job["lastBuild"]['timestamp']/1000)
            if(lastbuildtime < dt):  # 指定月数以上動かされていないもの
                print(str(lastbuildtime) + '\t' + job["displayName"])
                notify_dict_exceed[job["displayName"]] = lastbuildtime

    # 動かしてないジョブは時間の古い順にソートする
    notify_dict_exceed_sorted = {}
    for k, v in sorted(notify_dict_exceed.items(), key=lambda x: x[1]):
        notify_dict_exceed_sorted[k] = v
    notify_dict = {KEY_EXCEEDED: notify_dict_exceed_sorted,
                   KEY_NOBUILD: notify_dict_no}
    print(notify_dict)
    return notify_dict


def make_json_to_rocketChat(jenkins_url, builds_datas, months, server_name):
    # 通知データを作る
    msg_no = ''
    msg_exceeded = ''
    for no_build in builds_datas[KEY_NOBUILD]:
        msg_no = msg_no + "[" + no_build + \
            "](" + jenkins_url + "job/" + no_build + ")\n"
    for k in builds_datas[KEY_EXCEEDED]:
        msg_exceeded = msg_exceeded + \
            str(builds_datas[KEY_EXCEEDED][k].strftime("%Y/%m/%d %H:%M:%S"))
        + "   [" + k + "](" + jenkins_url + "job/" + \
            urllib.parse.quote(k) + ")\n"
    attachmentJson = {"fields": [
        {"short": True, "title": "ビルド履歴なし", "value": msg_no},
        {"short": True, "title": str(months) + "か月ビルドなし(古い順)",
         "value": msg_exceeded}],
        "title": server_name,
        "title_link": jenkins_url,
        "color": "#764FA5",
        "collapsed": True}
    jsonDict = {"text": "棚卸ジョブだよ",
                "attachments": attachmentJson}
    return jsonDict


def main(token, jenkins_url, server_name, tuchiJob, months):

    # Jenkinsインスタンスのチェックを行う。
    # 接続エラーの場合は、この時点で後続処理をスキップする（正常終了扱い）
    # さらに、チャットに通知する。通知先は、tokenで渡された部屋。
    try:
        r = requests.get(jenkins_url + "api/json",
                         auth=(username, password))
    except requests.exceptions.ConnectionError:
        print('Connection error:'+jenkins_url + "api/json")
        message = ':thinking: ' + mention + \
            "[" + server_name + "](" + jenkins_url + ') ' + \
            ' に接続できません。 ' + tuchiJob
        notificationToRocketChat.post_text(token, message)
        sys.exit(0)

    builds_datas = get_jobs_inventory(jenkins_url, months)
    jsonDict = make_json_to_rocketChat(
        jenkins_url, builds_datas, months, server_name)

    notificationToRocketChat.post_json(token, jsonDict)


if __name__ == "__main__":
    argvs = sys.argv  # コマンドライン引数を格納したリストの取得
    argc = len(argvs)
    print(str(argvs).encode("cp932", errors="ignore"))  # デバッグプリント
    print(str(argc))  # デバッグプリント
    if (argc != 6):   # 引数が適切でない場合は、その旨を表示
        print('Error: invalid argument')
        print(('Usage: python %s ROCKET_CHAT_TOKEN JENKINS_URL "\
          +JENKINS_SERVER_NAME ADD_MESSAGE (dev_servers_pass)' %
               argvs[0]).encode("cp932", errors="ignore"))
        sys.exit(1)         # プログラムの終了
    main(argvs[1], argvs[2], argvs[3], argvs[4], int(argvs[5]))
