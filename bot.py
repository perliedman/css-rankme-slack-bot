import sqlite3
from slackclient import SlackClient
import time
import os
import sys

def print_score():
    conn = sqlite3.connect(sys.argv[1])

    c = conn.cursor()

    score_query = 'select name, (cast(score as float) - 1000) / (rounds_tr + rounds_ct) as spr, score from rankme order by spr desc'

    i = 1
    lines = []
    for row in c.execute(score_query):
        lines.append('%d. %20s%8.02f%6d' % (i, row[0], row[1], row[2]))
        i += 1

    return '\n'.join(lines)


# constants
BOT_ID = os.environ.get("BOT_ID")
AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "rankme"


def handle_command(command, channel):
    response = "Not sure what you mean. Use the *" + EXAMPLE_COMMAND + \
               "* command with numbers, delimited by spaces."
    if command.startswith(EXAMPLE_COMMAND):
        response = '```\n' + print_score() + '```\n:cs: :c4: :cs:'
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=response, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                    output['channel']
    return None, None


if __name__ == "__main__":
    slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose

    if slack_client.rtm_connect():
        print("StarterBot connected and running!")
        while True:
            command, channel = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
