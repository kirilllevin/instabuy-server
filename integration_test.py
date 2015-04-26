#!/usr/bin/env python
import getopt
import json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import sys


_DEV_SERVER = 'http://localhost:8080'


def clear_all(headers):
    r = requests.post(_DEV_SERVER + '/clear_all',
                      headers=headers)
    assert r.status_code == requests.codes.ok


def auth(headers, name):
    user_data = {
        'name': name
    }
    r = requests.post(_DEV_SERVER + '/user/auth',
                      data=json.dumps(user_data), headers=headers)
    assert r.status_code == requests.codes.ok


def post(headers):
    item_data = {
        'title': 'Grey Sofa',
        'description': 'IKEA sofa, seats 3 people. Colour grey.',
        'price': 300,
        'currency': 'CHF',
        'category': 'Furniture',
        # Coordinates for Eichstrasse 27, Zurich.
        'lat': 47.3624020,
        'lng': 8.5199550
    }
    r = requests.post(_DEV_SERVER + '/item/post',
                      data=json.dumps(item_data), headers=headers)
    assert r.status_code == requests.codes.ok
    item_id = r.json()['item_id']
    # Get a URL to upload an image.
    r = requests.get(_DEV_SERVER + '/item/image/upload_url',
                     headers=headers)
    assert r.status_code == requests.codes.ok
    upload_url = r.json()['upload_url']
    # Upload the image.
    upload_data = MultipartEncoder(
        fields={'item_id': str(item_id),
                'file': ('filename', open('test_data/image.jpg', 'rb'),
                         'image/jpeg')})
    upload_headers = headers
    upload_headers['Content-Type'] = upload_data.content_type
    r = requests.post(upload_url,
                      data=upload_data, headers=upload_headers)
    assert r.status_code == requests.codes.ok


def list(headers):
    # Coordinates for Zurich HB.
    list_data = {'lat': 47.3778700, 'lng': 8.5403990}
    r = requests.get(_DEV_SERVER + '/item/list',
                     params=list_data, headers=headers)
    print r.json()


def like(headers, item_id):
    like_data = {'item_id': item_id, 'like_state': 1}
    r = requests.post(_DEV_SERVER + '/item/like',
                      data=json.dumps(like_data), headers=headers)
    assert r.status_code == requests.codes.ok


def chat(headers, item_id, receiver_id):
    chat_data = {'item_id': item_id,
                 'receiver_id': receiver_id,
                 'message': 'Hello?'}
    r = requests.post(_DEV_SERVER + '/chat/post',
                      data=json.dumps(chat_data), headers=headers)
    assert r.status_code == requests.codes.ok


def updates(headers):
    r = requests.get(_DEV_SERVER + '/updates', headers=headers)
    return r.json()


def delete(headers, item_id):
    delete_data = {'item_id': item_id}
    r = requests.post(_DEV_SERVER + '/item/delete',
                      data=json.dumps(delete_data), headers=headers)
    print r.json()


def main(argv=None):
    if argv is None:
        argv = sys.argv

    opts, args = getopt.getopt(
        argv[1:], '',
        ['token=', 'name=', 'actions=', 'item_id=', 'receiver_id='])
    opts = dict([(k.lstrip('--'), v) for (k, v) in opts])

    assert 'token' in opts
    assert 'actions' in opts
    actions = opts['actions'].split(',')

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Auth-Token': opts['token'],
    }
    if 'clear_all' in actions:
        clear_all(headers)

    if 'auth' in actions:
        auth(headers, opts['name'] if 'name' in opts else 'name')

    if 'post' in actions:
        post(headers)

    if 'list' in actions:
        list(headers)

    if 'like' in actions:
        assert 'item_id' in opts
        like(headers, opts['item_id'])

    if 'chat' in actions:
        assert 'item_id' in opts
        assert 'receiver_id' in opts
        chat(headers, opts['item_id'], opts['receiver_id'])

    if 'updates' in actions:
        updates(headers)

    if 'delete' in actions:
        assert 'item_id' in opts
        delete(headers, opts['item_id'])


if __name__ == '__main__':
    sys.exit(main())
