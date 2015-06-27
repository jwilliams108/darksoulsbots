import sys
import pickle
import ConfigParser
import re
import praw

# globals
debug_level = ''
location = 'local'
r = None


def reddit_retrieve_flairs(sub_name, valid):
    global debug_level
    global r

    flairs = {}

    # get flairs
    output = open(sub_name + '_flairs.pkl', 'wb')
    sub = r.get_subreddit(sub_name)
    flair_list = sub.get_flair_list(limit=None)

    for index, flair in enumerate(flair_list):
        # progress indicator
        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            sys.stdout.write('[NOTICE] Processing %i flair(s) from /r/%s...\r' %
                             (index, sub_name))
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
            print('[DEBUG] Retrieving from /r/{0} ({1}) User: {2} has flair class: {3}' # and flair text: \'{4}\''
                  .format(sub_name, index, flair['user'], flair['flair_css_class'])) #, flair['flair_text']))

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        sys.stdout.write('\n')
        sys.stdout.flush()

    pickle.dump(flairs, output)
    output.close()

    return flairs


def local_retrieve_flairs(sub_name):
    global debug_level

    # get flairs
    output = open(sub_name + '_flairs.pkl', 'rb')
    flairs = pickle.load(output)
    index = 0

    for user, flair in flairs.iteritems():
        index += 1
        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            sys.stdout.write('[NOTICE] Processing %i flair(s) from /r/%s...\r' %
                             (index, sub_name))
            sys.stdout.flush()

        if debug_level == 'DEBUG':
            print('[DEBUG] Reading from {0} User: {1} has flair class: {2} and flair text: {3}'
                  .format(sub_name + '_flairs.pkl', user, flair['flair_css_class'], flair['flair_text']))

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        sys.stdout.write('\n')
        sys.stdout.flush()

    output.close()

    return flairs


def check_new_flairs(sub_name, keys, flairs, valid):
    global debug_level

    valid_keys = set()

    for key in keys:
        # check that new flairs contain valid flair
        match = re.search(valid, flairs[key]['flair_css_class'])

        if match is not None:
            valid_keys.add(key)

            if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                print('[NOTICE] Only in /r/{0} User: {1} has flair class: {2}'
                    .format(sub_name, key, match.group()))

    return valid_keys


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
            print('[NOTICE] Adding User: {0}, flair class: {1}, flair text: {2}'
                  .format(key, new_flairs[key]['flair_css_class'], new_flairs[key]['flair_text']))


def get_flairs_to_sync(source_sub, source_flairs, dest_sub, dest_flairs, valid):
    global debug_level

    non_matching_flairs = { source_sub: {}, dest_sub: {} }
    index = 0

    for key in source_flairs.keys():
        index += 1
        if debug_level == 'NOTICE' or debug_level == 'DEBUG':
            sys.stdout.write('[NOTICE] Comparing %i flair(s) in /r/%s to /r/%s...\r' %
                             (index, source_sub, dest_sub))
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

                print("Mismatched flair for User: {0}, (s)ource: {1}, (d)estination: {2}!"
                      .format(key, display_source_flair, display_dest_flair))

                if debug_level == 'DEBUG':
                    print("[DEBUG] From (s)ource [/r/{0}]: /r/{1} should have flair class: {2}, but has: {3}.\n"
                          .format(source_sub, dest_sub, new_dest_flair, dest_flairs[key]['flair_css_class']) +
                          '[DEBUG] From (d)estination [/r/{0}]: /r/{1} should have flair class: {2}, but has: {3}.'
                          .format(dest_sub, source_sub, new_source_flair, source_flairs[key]['flair_css_class']))

                sync_flair = raw_input('Sync flair (s/d/n)? ')

                if sync_flair == 's':
                    non_matching_flairs[dest_sub][key] = {}
                    if key in dest_flairs and 'flair_text' in dest_flairs[key]:
                        non_matching_flairs[dest_sub][key]['flair_text'] = dest_flairs[key]['flair_text']
                    else:
                        non_matching_flairs[dest_sub][key]['flair_text'] = ''
                    non_matching_flairs[dest_sub][key]['flair_css_class'] = new_dest_flair
                elif sync_flair == 'd':
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


def build_csv_response(flairs):
    response = []
    for flair in flairs:
        row = {}
        row['user'] = flair
        row['flair_text'] = flairs[flair]['flair_text']
        row['flair_css_class'] = flairs[flair]['flair_css_class']
        response.append(row)

    return response


def bulk_set_user_flair(sub_name, flair_mapping):
    global location

    if location == 'reddit':
        # execute upload
        while True:
            try:
                r.get_subreddit(sub_name).set_flair_csv(flair_mapping)
                break
            except Exception as e:
                sys.stderr.write('[ERROR]: Error bulk setting flair: {0}'.format(e))
                sys.exit()

        print('Bulk setting {0} flair(s) to /r/{1} successful!'
              .format(len(flair_mapping), sub_name))
    else:
        print('Your location setting is local, bulk upload disabled!!!')


def main():
    global debug_level
    global location
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
            sys.stderr.write('[ERROR]: {0}'.format(e))
            sys.exit()

    location = cfg_file.get('source', 'location')
    debug_level = cfg_file.get('debug', 'level')
    source_sub = cfg_file.get('source', 'source_sub')
    dest_sub = cfg_file.get('source', 'dest_sub')
    valid_flairs = cfg_file.get('flairs', 'valid')

    print('Syncing flairs between /r/{0} and /r/{1}...'
          .format(source_sub, dest_sub))

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        print('[NOTICE] Loading flairs from source: {0}...'
              .format(location))

    if location == 'reddit':
        # login to reddit
        while True:
            try:
                r = praw.Reddit(user_agent=cfg_file.get('reddit', 'user_agent'))

                if debug_level == 'NOTICE' or debug_level == 'DEBUG':
                    print('[NOTICE] Logging in as {0}...'
                          .format(cfg_file.get('reddit', 'username')))

                r.login(cfg_file.get('reddit', 'username'),
                        cfg_file.get('reddit', 'password'))
                break
            except Exception as e:
                sys.stderr.write('[ERROR]: {0}'.format(e))
                sys.exit()

        # get flairs from source and dest subs
        source_flairs = reddit_retrieve_flairs(source_sub, valid_flairs)
        dest_flairs = reddit_retrieve_flairs(dest_sub, valid_flairs)
    else:
        source_flairs = local_retrieve_flairs(source_sub)
        dest_flairs = local_retrieve_flairs(dest_sub)

    # show users in source but not dest
    source_only_keys = set(source_flairs.keys()) - set(dest_flairs.keys())
    source_only_keys = check_new_flairs(source_sub, source_only_keys, source_flairs, valid_flairs)

    if len(source_only_keys) > 0:
        print('{0} flair(s) present in /r/{1}, but not in /r/{2}'
              .format(len(source_only_keys), source_sub, dest_sub))

        new_dest_flairs = {}

        print('Add missing flair(s) to /r/{0}?'
              .format(dest_sub))
        add_new_dest = raw_input('(y/n) ')

        if add_new_dest == 'y':
            add_new_flairs(dest_flairs, source_only_keys, source_flairs, new_dest_flairs, valid_flairs)
            add_new_dest_response = build_csv_response(new_dest_flairs)
            bulk_set_user_flair(dest_sub, add_new_dest_response)
    else:
        print('There are no missing flairs in /r/{0}!'
              .format(dest_sub))

    # show users in dest but not in source
    dest_only_keys = set(dest_flairs.keys()) - set(source_flairs.keys())
    dest_only_keys = check_new_flairs(dest_sub, dest_only_keys, dest_flairs, valid_flairs)

    if len(dest_only_keys) > 0:
        print('{0} flair(s) present in /r/{1}, but not in /r/{2}'
              .format(len(dest_only_keys), dest_sub, source_sub))

        new_source_flairs = {}

        print('Add missing flair(s) to /r/{0}?'
              .format(source_sub))
        add_new_source = raw_input('(y/n) ')

        if add_new_source == 'y':
            add_new_flairs(source_flairs, dest_only_keys, dest_flairs, new_source_flairs, valid_flairs)
            add_new_source_response = build_csv_response(new_source_flairs)
            bulk_set_user_flair(source_sub, add_new_source_response)
    else:
        print('There are no missing flairs in /r/{0}!'
              .format(source_sub))

    # show differences in flairs that are in both subs
    flairs_to_sync = get_flairs_to_sync(source_sub, source_flairs, dest_sub, dest_flairs, valid_flairs)

    # sync from source_sub to dest_sub
    if len(flairs_to_sync[dest_sub]) > 0:
        print('Of {0} flair(s) in /r/{1}, {2} require(s) syncing from /r/{3}'
              .format(len(dest_flairs), dest_sub, len(flairs_to_sync[dest_sub]), source_sub))

        print('Sync flair(s) from /r/{0} to /r/{1}?'
              .format(source_sub, dest_sub))
        sync_dest_flairs = raw_input('(y/n) ')

        if sync_dest_flairs == 'y':
            sync_dest_flairs_response = build_csv_response(flairs_to_sync[dest_sub])
            bulk_set_user_flair(dest_sub, sync_dest_flairs_response)
    else:
        print('There are no flairs to sync between /r/{0} and /r/{1}!'
              .format(source_sub, dest_sub))

    # sync from dest_sub to source_sub
    if len(flairs_to_sync[source_sub]) > 0:
        print('Of {0} flair(s) in /r/{1}, {2} require(s) syncing from /r/{3}'
              .format(len(source_flairs), source_sub, len(flairs_to_sync[source_sub]), dest_sub))

        print('Sync flair(s) from /r/{0} to /r/{1}?'
              .format(dest_sub, source_sub))
        sync_source_flairs = raw_input('(y/n) ')

        if sync_source_flairs == 'y':
            sync_source_flairs_response = build_csv_response(flairs_to_sync[source_sub])
            bulk_set_user_flair(source_sub, sync_source_flairs_response)
    else:
        print('There are no flairs to sync between /r/{0} and /r/{1}!'
              .format(dest_sub, source_sub))


if __name__ == '__main__':
    main()
