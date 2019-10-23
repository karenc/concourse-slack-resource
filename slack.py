#!/usr/bin/env python3

import functools
import glob
import json
import os.path
import re
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


SLACK_API = 'https://slack.com/api'
CHANNELS_LIMIT = 50


def log(message, file=sys.stderr):
    print(message, file=file)


def call_api(method, params):
    log('Calling slack api {} {}'.format(
        method, {k: v for k, v in params.items() if k != 'token'}))
    result = json.loads(urlopen(f'{SLACK_API}/{method}',
                                data=urlencode(params).encode('utf-8')).read())
    log(result)
    return result


def log_to_file(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with open(f'/tmp/{func.__name__}.log', 'w') as f:
            def log_(message):
                log(message, file=f)
                log(message)
            return func(log, *args, **kwargs)

    return wrapper


class SlackResource:
    @staticmethod
    @log_to_file
    def check_(log, body):
        log('calling SlackResource.check_')
        source = body['source']

        # check which channels the bot is in
        channels = call_api('users.conversations', {
            'token': source['bot_access_token'],
            'user': source['bot_user_id'],
            'limit': CHANNELS_LIMIT,
        })['channels']

        log('bot is in these channels: {}'.format(
            ', '.join([c['name'] for c in channels])))

        if not body.get('version'):
            last_checked = '0'
        else:
            log(f'last checked: {body["version"]["ts"]}')
            last_checked = body['version']['ts']

        # for each channel, check messages since last check
        messages = []
        for channel in channels:
            for m in call_api('conversations.history', {
                        'token': source['user_access_token'],
                        'channel': channel['id'],
                    })['messages']:
                if m['ts'] > last_checked and (not source.get('regexp') or \
                        re.search(source['regexp'], m['text'])):
                    messages.append({'channel': channel['id'], 'ts': m['ts']})

        if last_checked == '0':
            messages = messages[:1]
        print(json.dumps(list(reversed(messages))))

    @staticmethod
    def in_(body, destination):
        log('calling SlackResource.in_')

        extra_args = {}
        if 'thread_ts' in body['version']:
            api = 'conversations.replies'
            extra_args = {'ts': body['version']['thread_ts']}
        else:
            api = 'conversations.history'

        message = call_api(api, dict(
            token=body['source']['user_access_token'],
            channel=body['version']['channel'],
            inclusive=True,
            oldest=body['version']['ts'],
            limit=1,
            **extra_args
        ))['messages'][0]
        if body['source'].get('regexp'):
            m = re.search(body['source']['regexp'], message['text'])
            for i, group in enumerate(m.groups()):
                with open(os.path.join(
                        destination, f'message_text_{i}'), 'w') as f:
                    f.write(group)
        with open(os.path.join(destination, 'message_text'), 'w') as f:
            f.write(message['text'])
        with open(os.path.join(destination, 'user'), 'w') as f:
            f.write(message.get('user', message.get('username')))
        with open(os.path.join(destination, 'channel'), 'w') as f:
            f.write(body['version']['channel'])
        with open(os.path.join(destination, 'ts'), 'w') as f:
            f.write(body['version']['ts'])

        print(json.dumps({'version': body['version']}))

    @staticmethod
    def out_(body, inputs):
        log('calling SlackResource.out_')

        def replace_filename_with_content(match):
            filename = match.group(1).strip()
            with open(os.path.join(inputs, filename)) as f:
                content = f.read()
                return content

        # expect message and channel to look something like this:
        #    'got a message {{ce-bot/message_text_0}}'
        # {{ce-bot/message_text_0}} is the filename and is replaced by the
        # content of that file
        log(f'params: {body["params"]}')
        files = '\n  '.join(glob.glob(f'{inputs}/*/*'))
        log(f'files:\n  {files}')
        for key, value in body['params'].items():
            body['params'][key] = re.sub(
                '{{([^}]+)}}', replace_filename_with_content, value)

        resp = call_api('chat.postMessage', dict(
            token=body['source']['bot_access_token'], **body['params']))

        version = {'channel': resp['channel'], 'ts': resp['ts']}
        if resp.get('message', {}).get('thread_ts'):
            version['thread_ts'] = resp['message']['thread_ts']

        print(json.dumps({'version': version}))


if __name__ == '__main__':
    script_name = os.path.basename(sys.argv[0])
    if hasattr(SlackResource, f'{script_name}_'):
        m = getattr(SlackResource, f'{script_name}_')
        body = json.loads(sys.stdin.read())
        with open('/tmp/body.json', 'w') as f:
            json.dump(body, f)
        m(body, *sys.argv[1:])
