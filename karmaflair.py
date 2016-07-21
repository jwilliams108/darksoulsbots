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
import psycopg2
import sys
import time
from datetime import datetime
import re
from pprint import pprint

# globals
debug_level = ''
cfg_file = None
r = None
conn = None
cur = None


# helper class for tee logging
class FlushOutput(object):
    def __init__(self):
        self.terminal = sys.stdout

    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()

# sys.stdout = FlushOutput()


def get_reply_text(reply_type, reply_vars):
    template = open('tmpl/karmaflair/' + reply_type + '.tpl')

    return Template(template.read()).substitute(reply_vars)


def set_karma_flair(name):
    try:
        # get their total karma from the db
        cur.execute("SELECT name, count(*) AS karma FROM karma WHERE name=%s GROUP BY name", (name,))
        result = cur.fetchone()

        if result[1]:
            # grab their existing flair info
            subreddit = cfg_file.get('karmaflair', 'subreddit')
            current_flair = r.get_flair(subreddit, name)
            karma_flair_text = str(result[1]) + " Karma"

            r.set_flair(subreddit, name, karma_flair_text, current_flair['flair_css_class'])
    except Exception as e:
        conn.rollback()

        sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
    else:
        conn.commit()

        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            print('[{}] [NOTICE] Karma flair successfully updated for {} to {}'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name, karma_flair_text))


def process_comment_command(command, command_type, comment, submission, parent=None):
    if command == 'karma' and command_type == '+' and parent is not None:
        # dict of vars for template completion
        reply_vars = {
            'name': comment.author.name,
            'parent_name': parent.author.name,
        }

        # valid grant karma command, check for additional criteria
        while True:
            # request must have correct link flair
            if submission.link_flair_text != cfg_file.get('karmaflair', 'valid_flair_text'):
                reddit_reply_to_comment(comment, get_reply_text('invalid_link_flair', reply_vars))
                break

            # user granting karma must be the same as the submitter, or the parent must be the submitter
            if comment.author.name != comment.link_author and parent.author.name != comment.link_author:
                reddit_reply_to_comment(comment, get_reply_text('invalid_author', reply_vars))
                break

            # user cannot grant karma to themselves
            if parent.author.name == comment.author.name:
                reddit_reply_to_comment(comment, get_reply_text('award_to_self', reply_vars))
                break

            # cannot grant karma to another command
            if re.match("^([\+|-])(" + valid_commands + ")$", parent.body.lower().strip()):
                reddit_reply_to_comment(comment, get_reply_text('award_to_command', reply_vars))
                break

            try:
                cur.execute("INSERT INTO " + cfg_file.get('karmaflair', 'dbtablename') + " (id, name, granter) VALUES (%s, %s, %s)",
                        (submission.id, parent.author.name, comment.author.name))
            except psycopg2.IntegrityError as e:
                conn.rollback()

                if e.pgcode == '23505':
                    # unique key violation
                    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                        print('[{}] [NOTICE] Karma has already been granted to {} by {}, for submission {}'
                                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), parent.author.name, comment.author.name, submission.id))

                    reddit_reply_to_comment(comment, get_reply_text('already_awarded', reply_vars))
                else:
                    sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            else:
                conn.commit()

                print('[{}] Karma successfully granted to {} by {}, for submission {}'
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        parent.author.name, comment.author.name, submission.id))

                # update karma flair
                set_karma_flair(parent.author.name)
                reddit_reply_to_comment(comment, get_reply_text('successful_award', reply_vars))

            break


def main():
    global cfg_file
    global debug_level
    global r
    global conn
    global cur

    # read ini and set config
    cfg_file = ConfigParser.RawConfigParser()
    while True:
        try:
            cfg_file.read('karmaflair.ini')
            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
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
            conn = psycopg2.connect('dbname=' + cfg_file.get('karmaflair', 'dbname') + ' user=' +
                    cfg_file.get('karmaflair', 'dbuser'))
            cur = conn.cursor()

            # login
            r = Reddit(user_agent=cfg_file.get('auth', 'user_agent'))
            reddit_auth(r, cfg_file, debug_level)

            # retrieve comments, stream will go back limit # of comments from start
            for comment in helpers.comment_stream(r, subreddit, limit=100, verbosity=0):
                if not comment.is_root:
                    # comment has a parent that isn't the submission, so is a candidate for a command
                    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                        print('[{}] [NOTICE] Checking comment posted at {} by {}'
                            .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), datetime.utcfromtimestamp(comment.created_utc), comment.author.name))

                    # command format is to start with a + or - and be the only text in the comment, whitespace is excluded
                    match = re.match("^([\+|-])(" + valid_commands + ")$", comment.body.lower().strip())

                    if match is not None and match.group(2):
                        # comment is both a sub comment and contains a valid command
                        command = match.group(2)
                        command_type = match.group(1)

                        submission = r.get_info(thing_id=comment.link_id)
                        parent = r.get_info(thing_id=comment.parent_id)

                        process_comment_command(command, command_type, comment, submission, parent)

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
            sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))

if __name__ == '__main__':
    main()
