import time
import datetime
from bson import ObjectId

from flask import Flask, request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.notification.wechat import Wechat
from eclogue.notification.smtp import SMTP
from eclogue.notification.slack import Slack

@jwt_required
def add_setting():
    is_admin = login_user.get('is_admin')
    if not is_admin:
        return jsonify({
            'message': 'permission deny',
            'code': 104010

        }), 401

    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'invalid params',
            'code': 104000,
        }), 400

    slack = payload.get('slack')
    data = {}
    if slack and type(slack) == dict:
        webhook = slack.get('webhook')
        if webhook:
            data['slack'] = {
                'webhook': webhook,
                'enable': bool(slack.get('enable'))
            }

    smtp = payload.get('smtp')
    if smtp and type(smtp) == dict:
        server = smtp.get('server')
        sender = smtp.get('sender')
        send_from = smtp.get('from')
        port = smtp.get('port')
        tls = smtp.get('tls')
        user = smtp.get('user')
        password = smtp.get('password')
        if server and sender and send_from:
            data['smtp'] = {
                'server': server,
                'sender': sender,
                'from': send_from,
                'tls': bool(tls),
                'user': user,
                'port': port,
                'password': password,
                'enable': bool(smtp.get('enable'))
            }

    nexmo = payload.get('nexmo')
    if nexmo:
        api_key = nexmo.get('key')
        api_secret = nexmo.get('secret')
        if api_key and api_secret:
            data['nexmo'] = {
                'key': api_key,
                'secret': api_secret,
                'enable': bool(nexmo.get('enable'))
            }
    wechat = payload.get('wechat')
    if wechat:
        corp_id = wechat.get('corp_id')
        secret = wechat.get('secret')
        aggent_id = wechat.get('agent_id')
        if corp_id and secret and aggent_id:
            data['wechat'] = {
                'corp_id': corp_id,
                'secret': secret,
                'agent_id': aggent_id,
                'enable': bool(wechat.get('enable'))
            }

    if data:
        _id = payload.get('_id')
        if _id:
            db.collection('setting').update_one({'_id': ObjectId(_id)}, {'$set': data})
        else:
            db.collection('setting').insert_one(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def get_setting():
    record = db.collection('setting').find_one({})

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record or {}
    })


def test():
    record = db.collection('setting').find_one({})

    # wechat = record.get('wechat')
    # print(wechat)
    # sender = Wechat()
    # result = sender.send('fuck world')
    # print('rr', result)
    # smtp = record.get('smtp')
    # print(record.get('smtp'))
    # smtp = SMTP()
    # smtp.send('fuck world', 'bugbear', ['craber234@sina.cn'])
    # try:
    #     raise Exception('fuck')
    # except Exception:
    #     print(traceback.format_exc())

    # slack = Slack()
    # slack.send('fuck world')

    return jsonify({
        'message': 'ok',
        'code': 0,
    })

