#!/usr/bin/env python
# vim: ts=4 sts=4 et sw=4

# A script/bot for reddit to manage user awarded karma
#
# see karmaflair.ini to set options

from praw import Reddit
from praw import helpers
from reddit import reddit_auth
from reddit import reddit_reply_to_comment
import ConfigParser
from string import Template
import psycopg2, psycopg2.extras
import sys
import re
import time
from datetime import datetime
import uuid

# globals
debug_level = ''
cfg_file = None
r = None
conn = None
cur = None
session_id = None


# helper class for tee logging
class FlushOutput(object):
    def __init__(self):
        self.terminal = sys.stdout

    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()

sys.stdout = FlushOutput()


def get_reply_text(reply_type, reply_vars):
    template = open('tmpl/karmaflair/' + reply_type + '.tpl')

    return Template(template.read()).substitute(reply_vars)


def check_for_reply(submission, name, granter, reply_type):
    replied = False

    try:
        cur.execute("SELECT session_id FROM karma WHERE id=%s AND name=%s AND granter=%s AND type=%s AND replied=TRUE",
                (submission.id, name, granter, reply_type,))
        result = cur.fetchone()

        if result is not None:
            replied = True

            if debug_level == 'DEBUG':
                print('[{}] [DEBUG] Reply exists for submission {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), submission.id))
    except Exception as e:
        conn.rollback()

        sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
        sys.stderr.flush()
    else:
        conn.commit()

        return not replied


def set_replied(submission, name, granter, reply_type):
    try:
        cur.execute("INSERT INTO " + cfg_file.get('karmaflair', 'dbtablename') + " (id, name, granter, type, replied, session_id)" +
                " VALUES (%s, %s, %s, %s, TRUE, %s) ON CONFLICT (id, name, granter, type) DO UPDATE SET replied=TRUE",
                (submission.id, name, granter, reply_type, session_id,))
    except Exception as e:
        conn.rollback()

        sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
        sys.stderr.flush()
    else:
        conn.commit()

        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            print('[{}] [NOTICE] Message reply has been recorded to {} by {}, for submission {} of type {}'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, granter, submission.id, reply_type))


def handle_reply(comment, submission, name, granter, reply_type, reply_vars):
    if check_for_reply(submission, name, granter, reply_type):
        try:
            reddit_reply_to_comment(comment, get_reply_text(reply_type, reply_vars))
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.stderr.flush()
        else:
            set_replied(submission, name, granter, reply_type)


def grant_karma(comment, submission, name, granter, reply_vars):
    try:
        cur.execute("INSERT INTO " + cfg_file.get('karmaflair', 'dbtablename') + " (id, name, granter, type, session_id)" +
                " VALUES (%s, %s, %s, 'successful_award', %s)",
                (submission.id, name, granter, session_id,))
    except psycopg2.IntegrityError as e:
        conn.rollback()

        if e.pgcode == '23505':
            # unique key violation, potentially already granted
            cur.execute("SELECT session_id FROM karma WHERE id=%s AND name=%s AND granter=%s AND type='successful_award' AND replied=TRUE",
                    (submission.id, name, granter,))
            result = cur.fetchone()

            if result is not None and result[0] == session_id:
                # karma has already been awarded this session, reply to this attempt
                if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                    print('[{}] [NOTICE] Karma has already been granted to {} by {}, for submission {}'
                            .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, granter, submission.id))

                handle_reply(comment, submission, name, granter, 'already_awarded', reply_vars)
            else:
                if debug_level == 'DEBUG':
                    print('[{}] [DEBUG] Reply exists for submission {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), submission.id))
        else:
            sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.stderr.flush()
    else:
        conn.commit()

        print('[{}] Karma successfully granted to {} by {}, for submission {}'
                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, granter, submission.id))

        # reply and update karma flair
        handle_reply(comment, submission, name, granter, 'successful_award', reply_vars)
        set_karma_flair(name)


def set_karma_flair(name):
    try:
        # get their total karma from the db
        cur.execute("SELECT name, count(*) AS karma FROM karma WHERE name=%s AND type='successful_award' GROUP BY name", (name,))
        result = cur.fetchone()

        if result is not None and result[1]:
            # grab their existing flair info
            subreddit = cfg_file.get('karmaflair', 'subreddit')
            current_flair = r.get_flair(subreddit, name)
            karma_flair_text = str(result[1]) + " Karma"

            r.set_flair(subreddit, name, karma_flair_text, current_flair['flair_css_class'])
    except Exception as e:
        conn.rollback()

        sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
        sys.stderr.flush()
    else:
        conn.commit()

        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            print('[{}] [NOTICE] Karma flair successfully updated for {} to {}'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, karma_flair_text))


def process_comment_command(command, command_type, valid_commands, comment, submission, parent=None):
    if command == 'karma' and command_type == '+' and parent is not None:
        # dict of vars for template completion
        reply_vars = {
            'name': comment.author.name,
            'parent_name': parent.author.name if parent.author is not None else None,
        }

        # valid grant karma command, check for additional criteria
        while True:
            # request must have correct link flair
            # if re.match(cfg_file.get('karmaflair', 'valid_link_flair'), submission.link_flair_text) is None:
            #     handle_reply(comment, submission, parent.author.name, comment.author.name, 'invalid_link_flair', reply_vars)
            #     break

            # do not grant karma to a deleted submission or comment
            if submission.author is None or parent.author is None:
                handle_reply(comment, submission, '[deleted]', comment.author.name, 'invalid_parent_author', reply_vars)
                break

            # command must be a reply to a comment, unless excepted
            submission_flair_text = submission.link_flair_text if submission.link_flair_text is not None else ''
            if comment.is_root and re.match(cfg_file.get('karmaflair', 'valid_root_flair'), submission_flair_text) is None:
                handle_reply(comment, submission, parent.author.name, comment.author.name, 'top_level', reply_vars)
                break

            # user cannot grant karma to themselves
            if parent.author.name == comment.author.name:
                handle_reply(comment, submission, parent.author.name, comment.author.name, 'award_to_self', reply_vars)
                break

            # cannot grant karma to another command
            if re.search("^([\+|-])(" + valid_commands + ")$", parent.body.lower().strip()) is not None:
                handle_reply(comment, submission, parent.author.name, comment.author.name, 'award_to_command', reply_vars)
                break

            # user granting karma must be the same as the submitter, or the parent must be the submitter
            if comment.author.name != comment.link_author and parent.author.name != comment.link_author:
                handle_reply(comment, submission, parent.author.name, comment.author.name, 'invalid_author', reply_vars)
                break

            grant_karma(comment, submission, parent.author.name, comment.author.name, reply_vars)
            break


def main():
    global cfg_file
    global debug_level
    global r
    global conn
    global cur
    global session_id

    # read ini and set config
    cfg_file = ConfigParser.RawConfigParser()
    while True:
        try:
            cfg_file.read('karmaflair.ini')
            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.stderr.flush()
            sys.exit()

    debug_level = cfg_file.get('debug', 'level')
    mode = cfg_file.get('general', 'mode')
    loop_time = cfg_file.getint('general', 'loop_time')
    subreddit = cfg_file.get('karmaflair', 'subreddit')
    valid_commands = cfg_file.get('karmaflair', 'valid_commands')

    # main loop at set interval if mode is set to 'continuous'
    while True:
        print('[{}] Starting karma flair...'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        try:
            # connect to db
            psycopg2.extras.register_uuid()
            conn = psycopg2.connect('dbname=' + cfg_file.get('karmaflair', 'dbname') + ' user=' + cfg_file.get('karmaflair', 'dbuser'))
            cur = conn.cursor()

            # login
            r = Reddit(user_agent=cfg_file.get('auth', 'user_agent'))
            reddit_auth(r, cfg_file, debug_level)

            # generate session id
            session_id = uuid.uuid1()

            # retrieve comments, stream will go back limit # of comments from start
            for comment in helpers.comment_stream(r, subreddit, limit=100, verbosity=0):
                if debug_level == 'DEBUG':
                    print('[{}] [DEBUG] Checking comment posted at {} by {}'
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), datetime.utcfromtimestamp(comment.created_utc), comment.author.name))

                # command format is to start with a + or -
                match = re.match("^([\+|-])(" + valid_commands + ")", comment.body.lower().strip())

                if match is not None and match.group(2):
                    # comment contains a valid command
                    command = match.group(2)
                    command_type = match.group(1)

                    submission = r.get_info(thing_id=comment.link_id)
                    parent = r.get_info(thing_id=comment.parent_id)

                    if debug_level == 'DEBUG':
                        print('[{}] [DEBUG] Processing comment command: {}{}'
                            .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), command_type, command))

                    process_comment_command(command, command_type, valid_commands, comment, submission, parent)

            if mode == 'continuous':
                print('[{}] Pausing karma flair...'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                time.sleep(loop_time)
            else:
                cur.close()
                conn.close()
                break
        except KeyboardInterrupt, SystemExit:
            cur.close()
            conn.close()

            print('[{}] Stopping summon karma...'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            break
        except Exception as e:
            cur.close()
            conn.close()

            sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.stderr.flush()

            if mode == 'continuous':
                time.sleep(loop_time)
            else:
                break

if __name__ == '__main__':
    main()
