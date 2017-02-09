#!/usr/bin/env python
# vim: ts=4 sts=4 et sw=4

# A script/bot for reddit to keep flair in sync across related subreddits
#
# see flairsync.ini to set options

from reddit import reddit_login
from reddit import reddit_get_all_flair
from reddit import reddit_get_valid_flair
from reddit import reddit_set_flair
import ConfigParser
import sys
import time
from datetime import datetime

# globals
debug_level = ''
cfg_file = None
r = None


# helper class for tee logging
class FlushOutput(object):
    def __init__(self):
        self.terminal = sys.stdout

    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()

sys.stdout = FlushOutput()


# merge valid flairs from source_subs
def merge_flairs(source_subs, source_flairs, valid_flairs):
    merged_flairs = {}

    for source_sub in source_subs:
        print('[{}] Merging flairs from /r/{}'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub))

        # determine new flairs as well as flairs in both merge and source_sub
        source_only_keys = set(source_flairs[source_sub].keys()) - set(merged_flairs.keys())
        both_keys = set.intersection(set(source_flairs[source_sub].keys()), set(merged_flairs.keys()))

        # merge all flairs from source_sub not already present in merge_flairs
        if len(source_only_keys) > 0:
            for key in source_only_keys:
                merged_flairs[key] = source_flairs[source_sub][key]['valid_flair']

            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                print('[{}] [NOTICE] {} new valid flair(s) merged from /r/{}'
                      .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(source_only_keys), source_sub))
        else:
            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                print('[{}] [NOTICE] There are no valid new flairs to merge from /r/{} '
                      .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub))

        # update flair present in both current source_sub and merged_flairs
        if len(both_keys) > 0:
            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                print('[{}] [NOTICE] Checking existing flair(s) from /r/{}...'
                      .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub))

            both_count = 0

            for key in both_keys:
                merged_flair = merged_flairs[key]
                source_flair = source_flairs[source_sub][key]['valid_flair']

                # only work with the valid flair substring - we know valid flairs are present
                # but there still may be additional invalid/ignorable flair
                merged_flair = reddit_get_valid_flair(merged_flair, valid_flairs)
                source_flair = reddit_get_valid_flair(source_flair, valid_flairs)

                if merged_flair != source_flair:
                    operation = cfg_file.get('general', 'operation')
                    sync_flair = ''

                    if operation != 'automatic':
                        print("[{}] Mismatched flair for User: {}, (m)erged: {}, (s)ource: {}, (c)ustom"
                              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), key, merged_flair, source_flair))

                        # query user to resolve flair mismatch
                        sync_flair = raw_input('Sync flair from (m/s/c/n)? ')
                    else:
                        # choose longest flair for merge
                        if len(merged_flair) < len(source_flair):
                            sync_flair = 's'

                    if sync_flair == 'c':
                        merged_flairs[key] = raw_input('Enter a custom flair: ')
                    elif sync_flair == 's':
                        both_count += 1
                        merged_flairs[key] = source_flairs[source_sub][key]['valid_flair']

            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                if both_keys > 0:
                    print('[{}] [NOTICE] {} updated valid flair(s) merged from /r/{}'
                          .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), both_count, source_sub))
                else:
                    print('[{}] [NOTICE] There are no valid updated flair(s) to merge from /r/{}'
                          .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), both_count, source_sub))

    return merged_flairs


# sync merged_flairs to source_subs
def sync_flairs(source_subs, source_flairs, merged_flairs, valid_flairs, kill_list=None):
    for source_sub in source_subs:
        print('[{}] Checking for flairs to sync to /r/{}...'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub))

        response = []

        # determine flairs to sync as flairs in merge set but not source set,
        # as well as flairs present in both sets that do not match
        merge_only_keys = set(merged_flairs.keys()) - set(source_flairs[source_sub].keys())
        both_keys = set.intersection(set(source_flairs[source_sub].keys()), set(merged_flairs.keys()))
        keys_to_sync = merge_only_keys | set(user for user in both_keys if source_flairs[source_sub][user]['valid_flair'] != merged_flairs[user])

        for user in keys_to_sync:
            source_flair = source_flairs[source_sub][user]['valid_flair'] if user in source_flairs[source_sub] else ''
            other_flair = source_flairs[source_sub][user]['other_flair'] if user in source_flairs[source_sub] else ''
            merged_flair = merged_flairs[user]

            if debug_level == 'DEBUG':
                print("[{}] [DEBUG] In /r/{}, syncing flair for User: {}, old: {}, new: {}, other: {}"
                      .format(
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                          source_sub,
                          user,
                          source_flair if source_flair != '' else '(none)',
                          merged_flair if merged_flair != '' else '(none)',
                          other_flair if other_flair != '' else '(none)'
                      ))

            row = {}
            row['user'] = user

            # don't set flair for any user in the kill list
            if kill_list is not None and user in kill_list:
                row['flair_css_class'] = ''
            else:
                row['flair_css_class'] = ' '.join([other_flair, merged_flair]) if other_flair != '' else merged_flair

            row['flair_text'] = '\"' + source_flairs[source_sub][user]['flair_text'] + '\"' if user in source_flairs[source_sub] else ''
            response.append(row)

        # send response to reddit if there are flairs to sync
        if len(response) > 0:
            if cfg_file.get('general', 'operation') != 'automatic':
                sync_flairs = 'n'
            else:
                sync_flairs = 'y'

            reddit_set_flair(r, source_sub, response, sync_flairs, debug_level)


def main():
    global cfg_file
    global debug_level
    global r

    source_flairs = {}
    merged_flairs = {}

    # read ini and set config
    cfg_file = ConfigParser.RawConfigParser()
    while True:
        try:
            cfg_file.read('flairsync.ini')
            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.exit()

    # required config options
    debug_level = cfg_file.get('debug', 'level')
    mode = cfg_file.get('general', 'mode')
    loop_time = cfg_file.getint('general', 'loop_time')
    source_subs = (cfg_file.get('flairsync', 'subreddits')).split(',')
    valid_flairs = cfg_file.get('flairsync', 'valid_flairs')

    # optional config options
    try:
        kill_list = cfg_file.get('flairsync', 'kill_list')
    except NoOptionError:
        kill_list = None

    if kill_list is not None:
        kill_list = kill_list.split(',')

    # main loop at set interval if mode is set to 'continuous'
    while True:
        print('[{}] Starting flair sync...'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        try:
            # login
            r = reddit_login(cfg_file, debug_level)

            # retrieve valid flairs from each sub
            source_flairs = reddit_get_all_flair(r, source_subs, valid_flairs, debug_level)

            # build list of flairs to merge from source_subs
            merged_flairs = merge_flairs(source_subs, source_flairs, valid_flairs)

            # sync merged flairs
            sync_flairs(source_subs, source_flairs, merged_flairs, valid_flairs, kill_list)

            if mode == 'continuous':
                print('[{}] Pausing flair sync...'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                time.sleep(loop_time)
            else:
                break
        except KeyboardInterrupt, SystemExit:
            print('[{}] Stopping flair sync...'
                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}\n'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))

            if mode == 'continuous':
                time.sleep(loop_time)
            else:
                break

if __name__ == '__main__':
    main()
