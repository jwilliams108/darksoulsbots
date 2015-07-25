#!/usr/bin/env python
# vim: ts=4 sts=4 et sw=4

# A script to keep mod-granted trophy flair in sync
# across Dark Souls subs
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
    global cfg_file
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
                        token_data['access_token']
                )

            else:
                sys.stderr.write('[{}] [ERROR]: {} Reponse code from OAuth attempt'
                                  .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), response.status_code))
                sys.exit()

            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: {}'
                              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.exit()


# retrieve valid flairs from specified sub
def reddit_retrieve_flairs(sub_name, valid):
    global debug_level
    global r

    flairs = {}

    # get flairs
    sub = r.get_subreddit(sub_name)
    flair_list = sub.get_flair_list(limit=None)

    for index, flair in enumerate(flair_list):
        # progress indicator
        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            sys.stdout.write('[%s] [NOTICE] Processing %i flair(s) from /r/%s...\r' %
                              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index, sub_name))
            sys.stdout.flush()

        flairs[flair['user']] = {}

        if flair['flair_text'] is not None:
            flairs[flair['user']]['flair_text'] = flair['flair_text']
        else:
            flairs[flair['user']]['flair_text'] = ''

        if flair['flair_css_class'] is not None:
            flairs[flair['user']]['flair_css_class'] = flair['flair_css_class']
        else:
            flairs[flair['user']]['flair_css_class'] = ''

        if debug_level == 'DEBUG':
            print('[{}] [DEBUG] Retrieving from /r/{} ({}) User: {} has flair class: {}' # and flair text: \'{}\''
                   .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, index, flair['user'], flair['flair_css_class'])) #, flair['flair_text']))

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        sys.stdout.write('\n')
        sys.stdout.flush()

    return flairs


# check that new flairs are valid
def validate_flairs(sub_name, keys, flairs, valid):
    global debug_level

    valid_keys = set()

    for key in keys:
        # check that new flairs contain valid flair
        match = re.search(valid, flairs[key]['flair_css_class'])

        if match is not None:
            valid_keys.add(key)

            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                print('[{}] [NOTICE] Only in /r/{} User: {} has flair class: {}'
                       .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, key, match.group()))

    return valid_keys


# build list of new flairs to add
def add_new_flairs(dest_flairs, keys, source_flairs, new_flairs, valid):
    global debug_level

    for key in keys:
        new_flairs[key] = {}

        # copy existing flair text if present
        if key in dest_flairs and 'flair_text' in dest_flairs[key]:
            new_flairs[key]['flair_text'] = dest_flairs[key]['flair_text']
        else:
            new_flairs[key]['flair_text'] = ''

        # only copy the valid flair substring
        match = re.search(valid, source_flairs[key]['flair_css_class'])

        if match is not None:
            if key in dest_flairs:
                # keep existing non-valid dest flairs
                new_flairs[key]['flair_css_class'] = dest_flairs[key]['flair_css_class'] + match.group()
            else:
                new_flairs[key]['flair_css_class'] = match.group()
        #else:
            # we shouldn't get here as there must be a valid flair

        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            print('[{}] [NOTICE] Adding User: {}, flair class: {}' #, flair text: {}'
                   .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), key, new_flairs[key]['flair_css_class'])) #, new_flairs[key]['flair_text']))


# sync users present in source sub but not dest sub
def sync_missing_flairs(source_sub, source_flairs, dest_sub, dest_flairs, valid):
    global cfg_file

    source_only_keys = set(source_flairs.keys()) - set(dest_flairs.keys())
    source_only_keys = validate_flairs(source_sub, source_only_keys, source_flairs, valid)

    if len(source_only_keys) > 0:
        print('[{}] {} flair(s) present in /r/{}, but not in /r/{}'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(source_only_keys), source_sub, dest_sub))

        new_dest_flairs = {}

        if cfg_file.get('flairsync', 'operation') == 'automatic':
            add_new_dest = 'y'
        else:
            print('Add missing flair(s) to /r/{}?'
                .format(dest_sub))
            add_new_dest = raw_input('(y/n) ')

        if add_new_dest == 'y':
            add_new_flairs(dest_flairs, source_only_keys, source_flairs, new_dest_flairs, valid)
            add_new_dest_response = build_csv_response(new_dest_flairs)
            bulk_set_user_flair(dest_sub, add_new_dest_response)
    else:
        print('[{}] There are no missing valid flairs in /r/{}'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), dest_sub))


# retrieve mismatched flairs between source_sub and dest_sub and request user input to resolve conflicts
#
# returns a hash of flair strings to set in source_sub and dest_sub
def build_flairs_to_sync(source_sub, source_flairs, dest_sub, dest_flairs, valid):
    global debug_level

    non_matching_flairs = { source_sub: {}, dest_sub: {} }
    index = 0

    for key in source_flairs.keys():
        index += 1
        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            sys.stdout.write('[%s] [NOTICE] Comparing %i flair(s) in /r/%s to /r/%s...\r' %
                              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index, source_sub, dest_sub))
            sys.stdout.flush()

        if key in dest_flairs.keys():
            valid_source_flair = ''
            valid_dest_flair = ''

            # only replace valid flair substring, there may be others
            if re.search(valid, source_flairs[key]['flair_css_class']) is not None:
                valid_source_flair = re.search(valid, source_flairs[key]['flair_css_class']).group()

            if re.search(valid, dest_flairs[key]['flair_css_class']) is not None:
                valid_dest_flair = re.search(valid, dest_flairs[key]['flair_css_class']).group()

            if valid_dest_flair != valid_source_flair:
                other_dest_flair = re.split(valid, dest_flairs[key]['flair_css_class'])
                other_source_flair = re.split(valid, source_flairs[key]['flair_css_class'])
                new_dest_flair = ''
                new_source_flair = ''

                if valid_source_flair != '':
                    if len(other_source_flair) == 1:
                        # source flair did not contain a valid flair substring
                        new_source_flair = other_source_flair[0] + ' ' + valid_dest_flair
                    elif len(other_source_flair) == 2:
                        new_source_flair = other_source_flair[0] + valid_dest_flair + other_source_flair[1]

                    if len(other_dest_flair) == 1:
                        # dest flair did not contain a valid flair substring
                        new_dest_flair = other_dest_flair[0] + ' ' + valid_source_flair
                    elif len(other_dest_flair) == 2:
                        new_dest_flair = other_dest_flair[0] + valid_source_flair + other_dest_flair[1]
                else:
                    # source flair did not contain a valid flair substring
                    # although we can assume dest flair has a valid flair
                    # substring otherwise we would not have reached this point
                    new_source_flair = other_source_flair[0] + ' ' + valid_dest_flair
                    new_dest_flair = other_dest_flair[0] + other_dest_flair[1]

                new_dest_flair = new_dest_flair.strip()
                new_source_flair = new_source_flair.strip()
                display_dest_flair = valid_dest_flair if valid_dest_flair != '' else '(none)'
                display_source_flair = valid_source_flair if valid_source_flair != '' else '(none)'

                print("[{}] Mismatched flair for User: {}, (s)ource: {}, (d)estination: {}"
                       .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), key, display_source_flair, display_dest_flair))

                if debug_level == 'DEBUG':
                    print("[{}] [DEBUG] From (s)ource [/r/{}]: /r/{} should have flair class: {}, but has: {}\n"
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub, dest_sub, new_dest_flair, dest_flairs[key]['flair_css_class']) +
                        '[{}] [DEBUG] From (d)estination [/r/{}]: /r/{} should have flair class: {}, but has: {}'
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), dest_sub, source_sub, new_source_flair, source_flairs[key]['flair_css_class']))

                if cfg_file.get('flairsync', 'operation') != 'automatic':
                    # query user to resolve flair mismatch
                    sync_flair = raw_input('Sync flair from (s/d/n)? ')
                else:
                    # choose longest string (i.e., most flair), or n if equal
                    if len(valid_source_flair) > len(valid_dest_flair):
                        sync_flair = 's'
                    elif len(valid_source_flair) < len(valid_dest_flair):
                        sync_flair = 'd'
                    else:
                        sync_flair = 'n'

                if debug_level == 'DEBUG':
                    print("[{}] [DEBUG] Selecting '{}' after comparing lengths: (s)ource: {} ({}), (d)estination: {} ({})"
                        .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sync_flair, display_source_flair, len(valid_source_flair), display_dest_flair, len(valid_dest_flair)))

                if sync_flair == 's':
                    # set new flair from source_sub
                    non_matching_flairs[dest_sub][key] = {}
                    if key in dest_flairs and 'flair_text' in dest_flairs[key]:
                        non_matching_flairs[dest_sub][key]['flair_text'] = dest_flairs[key]['flair_text']
                    else:
                        non_matching_flairs[dest_sub][key]['flair_text'] = ''
                    non_matching_flairs[dest_sub][key]['flair_css_class'] = new_dest_flair
                elif sync_flair == 'd':
                    # set new flair from dest_sub
                    non_matching_flairs[source_sub][key] = {}
                    if key in source_flairs and 'flair_text' in source_flairs[key]:
                        non_matching_flairs[source_sub][key]['flair_text'] = source_flairs[key]['flair_text']
                    else:
                        non_matching_flairs[source_sub][key]['flair_text'] = ''
                    non_matching_flairs[source_sub][key]['flair_css_class'] = new_source_flair

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        sys.stdout.write('\n')
        sys.stdout.flush()

    return non_matching_flairs


# sync users present in boths subs
def sync_mismatched_flairs(source_sub, source_flairs, dest_sub, dest_flairs, valid):
    global cfg_file

    operation = cfg_file.get('flairsync', 'operation')

    # find differences in flairs that are in both subs
    flairs_to_sync = build_flairs_to_sync(source_sub, source_flairs, dest_sub, dest_flairs, valid)

    # sync from source_sub to dest_sub
    if len(flairs_to_sync[dest_sub]) > 0:
        print('[{}] Of {} flair(s) in /r/{}, {} require(s) syncing from /r/{}'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(dest_flairs), dest_sub, len(flairs_to_sync[dest_sub]), source_sub))

        if operation == 'automatic':
            sync_dest_flairs = 'y'
        else:
            print('Sync flair(s) from /r/{} to /r/{}?'
                   .format(source_sub, dest_sub))
            sync_dest_flairs = raw_input('(y/n) ')

        if sync_dest_flairs == 'y':
            sync_dest_flairs_response = build_csv_response(flairs_to_sync[dest_sub])
            bulk_set_user_flair(dest_sub, sync_dest_flairs_response)
    else:
        print('[{}] There are no valid flairs to sync between /r/{} and /r/{}'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub, dest_sub))

    # sync from dest_sub to source_sub
    if len(flairs_to_sync[source_sub]) > 0:
        print('[{}] Of {} flair(s) in /r/{}, {} require(s) syncing from /r/{}'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(source_flairs), source_sub, len(flairs_to_sync[source_sub]), dest_sub))

        if operation == 'automatic':
            sync_source_flairs = 'y'
        else:
            print('Sync flair(s) from /r/{} to /r/{}?'
                   .format(dest_sub, source_sub))
            sync_source_flairs = raw_input('(y/n) ')

        if sync_source_flairs == 'y':
            sync_source_flairs_response = build_csv_response(flairs_to_sync[source_sub])
            bulk_set_user_flair(source_sub, sync_source_flairs_response)
    else:
        print('[{}] There are no valid flairs to sync between /r/{} and /r/{}'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), dest_sub, source_sub))


# build response for API call
def build_csv_response(flairs):
    response = []
    for flair in flairs:
        row = {}
        row['user'] = flair
        row['flair_text'] = flairs[flair]['flair_text']
        row['flair_css_class'] = flairs[flair]['flair_css_class']
        response.append(row)

    return response


# perform the flair updates via a bulk set
def bulk_set_user_flair(sub_name, flair_mapping):
    # execute upload
    while True:
        try:
            r.get_subreddit(sub_name).set_flair_csv(flair_mapping)
            break
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: Error bulk setting flair: {}'
                              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.exit()

    print('[{}] Bulk setting {} flair(s) to /r/{} successful!'
           .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(flair_mapping), sub_name))


def main():
    global debug_level
    global cfg_file
    global r

    source_flairs = {}
    dest_flairs = {}

    # read config
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
    source_sub = cfg_file.get('source', 'source_sub')
    dest_sub = cfg_file.get('source', 'dest_sub')
    valid_flairs = cfg_file.get('flairs', 'valid')

    # main loop at set interval
    while True:
        print('[{}] Syncing flairs between /r/{} and /r/{}...'
               .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), source_sub, dest_sub))

        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            print('[{}] [NOTICE] Loading flairs...'
                   .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # login
        reddit_login()

        # retrieve flairs from source and dest subs
        source_flairs = reddit_retrieve_flairs(source_sub, valid_flairs)
        dest_flairs = reddit_retrieve_flairs(dest_sub, valid_flairs)

        # handle flairs present in source sub but not dest
        sync_missing_flairs(source_sub, source_flairs, dest_sub, dest_flairs, valid_flairs)

        # handle flairs present in dest sub but not source
        sync_missing_flairs(dest_sub, dest_flairs, source_sub, source_flairs, valid_flairs)

        # handle flairs present in both subs
        sync_mismatched_flairs(source_sub, source_flairs, dest_sub, dest_flairs, valid_flairs)

        if mode == 'continuous':
            time.sleep(loop_time)
        else:
            break

if __name__ == '__main__':
    main()
