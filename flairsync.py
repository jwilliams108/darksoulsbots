#!/usr/bin/env python
# vim: ts=4 sts=4 et sw=4

# A script/bot for reddit to keep flair in sync across related subreddits
#
# see flairsync.ini to set options

from datetime import datetime
from praw import Reddit
import ConfigParser
import requests
import requests.auth
import re
import sys
import time

# globals
debug_level = ''
cfg_file = None
r = None


# login to reddit using OAuth
def reddit_login():
    global r

    while True:
        try:
            r = Reddit(user_agent = cfg_file.get('flairsync', 'user_agent'))
            r.set_oauth_app_info(
                    client_id = cfg_file.get('flairsync', 'client_id'),
                    client_secret = cfg_file.get('flairsync', 'client_secret'),
                    redirect_uri = 'http://www.example.com/unused/redirect/uri'
                    'authorize_callback'
            )

            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                print('[{}] [NOTICE] Logging in as {}...'
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cfg_file.get('reddit', 'username')))

            # get OAuth token
            client_auth = requests.auth.HTTPBasicAuth(
                    cfg_file.get('flairsync', 'client_id'),
                    cfg_file.get('flairsync', 'client_secret'),
            )
            post_data = {
                    'grant_type': 'password',
                    'username': cfg_file.get('reddit', 'username'),
                    'password': cfg_file.get('reddit', 'password')
            }
            headers = { 'User-Agent': cfg_file.get('flairsync', 'user_agent') }
            response = requests.post(
                    'https://www.reddit.com/api/v1/access_token',
                    auth = client_auth,
                    data = post_data,
                    headers = headers
            )

            if response.status_code == 200:
                # set access credentials using token from reponse
                token_data = response.json()

                r.set_access_credentials(
                        set(['modflair']), #token_data['scope'],
                        token_data['access_token'])

            else:
                sys.stderr.write('[{}] [ERROR]: {} Reponse code from OAuth attempt'
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), response.status_code))
                sys.exit()

            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.exit()


# validate individual flair
def get_valid_flair(flair, valid_flairs):
    valid_flair = ''

    # check that new flairs contain valid flair
    match = re.search(valid_flairs, flair)

    if match is not None:
        valid_flair = match.group()

    return valid_flair


# if key exists, get other flair (not valid) substring from list
def get_other_flair(flair, valid_flairs):
    other_flair = ''

    # check if other non-valid flair is present
    split_flair = re.split(valid_flairs, flair)

    if len(split_flair) == 1:
        other_flair = split_flair[0].strip()
    elif len(split_flair) == 2:
        # handle if other flair comes before or after split flair
        if split_flair[0].strip() == '':
            other_flair = split_flair[1].strip()
        else:
            other_flair = split_flair[0].strip()

    return other_flair


# retrieve valid flairs from specified subs
def reddit_retrieve_flairs(sub_names, valid_flairs):
    flairs = {}

    print('[{}] Loading flairs...'
            .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # get flairs
    for sub_name in sub_names:
        sub = r.get_subreddit(sub_name)
        flair_list = sub.get_flair_list(limit=None)
        sub_flairs = {}

        for index, flair in enumerate(flair_list):
            # progress indicator
            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                sys.stdout.write('[%s] [NOTICE] Retrieving %i flair(s) from /r/%s...\r' %
                                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index, sub_name))
                sys.stdout.flush()

            if flair['flair_css_class'] is not None:
                valid_flair = get_valid_flair(flair['flair_css_class'], valid_flairs)
                other_flair = get_other_flair(flair['flair_css_class'], valid_flairs)

                if valid_flair != '':
                    sub_flairs[flair['user']] = {}
                    sub_flairs[flair['user']]['valid_flair'] = valid_flair
                    sub_flairs[flair['user']]['other_flair'] = other_flair

                    if flair['flair_text'] is not None:
                        sub_flairs[flair['user']]['flair_text'] = flair['flair_text']
                    else:
                        sub_flairs[flair['user']]['flair_text'] = ''

                    if debug_level == 'DEBUG':
                        print('[{}] [DEBUG] Retrieving from /r/{} ({}) User: {} has flair class: {}' # and flair text: \'{}\''
                                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, index, flair['user'], flair['flair_css_class'])) #, flair['flair_text']))

        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            sys.stdout.write('\n')
            sys.stdout.flush()

        flairs[sub_name] = sub_flairs

    return flairs


# merge valid flairs from source_subs
def merge_flairs(merged_flairs, source_subs, source_flairs, valid_flairs):
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
                merged_flair = get_valid_flair(merged_flair, valid_flairs)
                source_flair = get_valid_flair(source_flair, valid_flairs)

                if merged_flair != source_flair:
                    operation = cfg_file.get('flairsync', 'operation')
                    sync_flair = ''

                    if operation != 'automatic' or debug_level == 'NOTICE' or debug_level == 'DEBUG':
                        print("[{}] [NOTICE] Mismatched flair for User: {}, (m)erged: {}, (s)ource: {}, (c)ustom"
                                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), key, merged_flair, source_flair))

                    if operation != 'automatic':
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

        current_sub = source_sub

    return merged_flairs


# sync merged_flairs to source_subs
def sync_flairs(source_subs, source_flairs, merged_flairs, valid_flairs):
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
                            )
                        )

            row = {}
            row['user'] = user
            row['flair_text'] = source_flairs[source_sub][user]['flair_text'] if user in source_flairs[source_sub] else ''
            row['flair_css_class'] = ' '.join( [other_flair, merged_flair] ) if other_flair != '' else merged_flair
            response.append(row)

        # send response to reddit if there are flairs to sync
        if len(response) > 0:
            bulk_set_user_flair(source_sub, response)


# perform the flair updates via a bulk set
def bulk_set_user_flair(sub_name, response):
    if cfg_file.get('flairsync', 'operation') != 'automatic' or debug_level == 'NOTICE' or debug_level == 'DEBUG':
        for row in response:
            print('[{}] [NOTICE] In /r/{}, setting flair for User: {}, flair: {}, flair_text: {}'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, row['user'], row['flair_css_class'], row['flair_text'].encode('utf-8')))

    # confirm operation or proceed if automatic
    if cfg_file.get('flairsync', 'operation') != 'automatic':
        print('Sync {} flair(s) to /r/{}?'.format(len(response), sub_name))
        sync_flairs = raw_input('(y/n) ')
    else:
        print('[{}] Syncing {} flair(s) to /r/{}'
                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(response), sub_name))
        sync_flairs = 'y'

    if sync_flairs == 'y':
        # execute upload
        while True:
            try:
                r.get_subreddit(sub_name).set_flair_csv(response)
                break
            except Exception as e:
                sys.stderr.write('[{}] [ERROR]: Error bulk setting flair: {}'
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
                sys.exit()

        print('[{}] Bulk setting {} flair(s) to /r/{} successful!'
                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(response), sub_name))


def main():
    global cfg_file
    global debug_level

    source_flairs = {}
    merged_flairs = {}

    # read ini and set config
    cfg_file = ConfigParser.RawConfigParser()
    while True:
        try:
            cfg_file.read('flairsync.ini')
            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.exit()

    debug_level = cfg_file.get('debug', 'level')
    mode = cfg_file.get('flairsync', 'mode')
    loop_time = cfg_file.getint('flairsync', 'loop_time')
    source_subs = (cfg_file.get('source', 'source_subs')).split(',')
    valid_flairs = cfg_file.get('flairs', 'valid')

    # main loop at set interval if mode is set to 'continuous'
    while True:
        print('[{}] Starting flair sync...'
                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # login
        reddit_login()

        # retrieve valid flairs from each sub
        source_flairs = reddit_retrieve_flairs(source_subs, valid_flairs)

        # build list of flairs to merge from source_subs
        merged_flairs = merge_flairs(merged_flairs, source_subs, source_flairs, valid_flairs)

        # sync merged flairs
        sync_flairs(source_subs, source_flairs, merged_flairs, valid_flairs)

        if mode == 'continuous':
            print('[{}] Pausing flair sync...'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            time.sleep(loop_time)
        else:
            break

if __name__ == '__main__':
    main()
