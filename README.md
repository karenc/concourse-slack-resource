What is concourse-slack-resource?
---------------------------------

A concourse resource to read and post messages to slack as a bot.

It reads messages from all the channels the bot is in (not tested but maximum
50 channels) and allows the bot to write to any of the channels.

Prerequisites for using this resource
-------------------------------------

You'll need to create a slack app and a bot: https://api.slack.com/bot-users

Once you set everything up, you should be able to find your app on
https://api.slack.com/apps

Under "OAuth & Permissions", you'll need the "OAuth Access Token" and "Bot User
OAuth Access Token".  They look something like `xoxo-1234567890-abcdefghij` and
`xoxo-1234567890-klmnopqrst`.

The bot needs these scopes:

  - `channels:history` (Access user's public channels)
  - `chat:write:bot` (Send messages as bot)
  - `bot` (Add a bot user with the username @bot)
  - `users:read` (Access your workspaces's profile information)

You also need the bot user id (which is not the username and not the bot
id), I found the user id by doing `@<bot-username>` in the slack web app and
then copying the url, it looks something like this:
https://openstax.slack.com/team/ABC123GHI and the user id is the last bit
`ABC123GHI`.

These need to be stored in the `vars.yml` to be used with the example pipeline
below, for example:

```yaml
slack-user-access-token: xoxo-1234567890-abcdefghij
slack-bot-access-token: xoxo-1234567890-klmnopqrst
slack-bot-user-id: ABC123GHI
```

Example concourse pipeline
--------------------------

You can find this in [pipeline.yml](pipeline.yml).

```yaml
---
resource_types:
  - name: slack
    type: docker-image
    source:
      repository: karenc/concourse-slack-resource

resources:
  - name: bot
    type: slack
    source:
      user_access_token: ((slack-user-access-token))
      bot_access_token: ((slack-bot-access-token))
      bot_user_id: ((slack-bot-user-id))
      regexp: '<@((slack-bot-user-id))> (.*)'
    check_every: 10s

  - name: bot-write
    type: slack
    source:
      user_access_token: ((slack-user-access-token))
      bot_access_token: ((slack-user-bot-access-token))
      bot_user_id: ((slack-bot-user-id))

jobs:
  - name: test
    plan:
      - get: bot
        trigger: true
        version: every

      - put: bot-write
        params:
          text: '{{bot/message_text_0}} :tada:'
          channel: '{{bot/channel}}'
```

**Note:** The read and write resources need to be separate, otherwise there's
an infinite loop after the `put` step when the implicit `get` triggers a new
job :/

From https://concourse-ci.org/put-step.html:

> When the `put` succeeds, the produced version of the resource will be
> immediately fetched via an implicit get step.

Filtering and parsing incoming messages
---------------------------------------

`regexp` can be defined in the `get` resource, it is used to filter messages so
only messages matching the regular expression are returned.  It is also used to
parse the messages so if you add groups, they will be available as different
files.

In this example, if the message looks like `<@ABC123GHI> hey!`, the `bot/`
directory contains:

1. `message_text`: `<@ABC123GHI> hey!`
2. `message_text_0`: `hey!`
3. `channel`: `CDEF7890`
4. `user`: `U0123456`
5. `ts`: `1571329099.413700`

Sending messages
----------------

You need to provide at least two params `text` and `channel`.  All the
params can be found in https://api.slack.com/methods/chat.postMessage, any
params will be turned into arguments for `chat.postMessage`.

You can include content from files by doing something like:
`{{bot/message_text_0}} :tada:`, following the example message above, this will
be:

`hey! :tada:`

Creating the pipeline on concourse
----------------------------------

To create the example pipeline you can do:

```bash
fly -t example sp -p slack-bot -c pipeline.yml -l vars.yml
```

Unpause the pipeline:

```bash
fly -t example up -p slack-bot
```

And wait for the slack bot to respond.  Remember to invite your bot to the
channels you want.

Debugging
---------

If you're expecting the concourse pipeline to trigger but it's not happening,
you can try:

```bash
fly -t example intercept -c slack-bot/bot
```

This gives you access to the container the resource is running in.

There should be a `/tmp/body.json` and `/tmp/check_.log`.

`/tmp/body.json` is what concourse is sending to `/opt/resource/check` or
`/opt/resource/in` or `/opt/resource/out`.

It should look something like: (added line breaks for readability)

```json
{
    "source": {
        "bot_access_token": "xoxo-1234567890-klmnopqrst",
        "bot_user_id": "ABC123GHI",
        "user_access_token": "xoxo-1234567890-abcdefghij"
    },
    "version": {
        "channel_id": "CDEF7890",
        "ts": "1570673298.005900"
    }
}
```

You can try running the check script yourself by doing:

```bash
cat /tmp/body.json | /opt/resource/check
```

There are some debugging output in stderr so hopefully you'll find the problem
there.

For more information about concourse resources, see
https://concourse-ci.org/implementing-resource-types.html
