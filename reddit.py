from datetime import datetime
import requests
import requests.auth
import sys
import re


###
# Authentication Helpers
###
# post request
def reddit_send_request(auth, post_data, headers):
    # send and process request
    response = requests.post(
        'https://www.reddit.com/api/v1/access_token',
        auth=auth,
        data=post_data,
        headers=headers
    )

    if response.status_code == 200:
        # set access credentials using token from reponse
        return (response.json(), response.status_code)

    return (None, response.status_code)


# login to reddit using OAuth
def reddit_auth(r, scope, cfg_file, debug_level='NOTICE'):
    r.set_oauth_app_info(
        client_id=cfg_file.get('auth', 'client_id'),
        client_secret=cfg_file.get('auth', 'client_secret'),
        redirect_uri='http://www.example.com/unused/redirect/uri'
        'authorize_callback'
    )

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        print('[{}] [NOTICE] Logging in as {}...'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cfg_file.get('auth', 'username')))

    try:
        # get OAuth token
        client_auth = requests.auth.HTTPBasicAuth(
            cfg_file.get('auth', 'client_id'),
            cfg_file.get('auth', 'client_secret'),
        )

        # construct request data
        post_data = {
            'grant_type': 'password',
            'username': cfg_file.get('auth', 'username'),
            'password': cfg_file.get('auth', 'password')
        }

        headers = {'User-Agent': cfg_file.get('auth', 'user_agent')}

        token_data, status_code = reddit_send_request(client_auth, post_data, headers)

        if status_code == 200:
            r.set_access_credentials(
                scope,
                token_data['access_token'])

            return token_data
        else:
            sys.stderr.write('[{}] [ERROR]: {} Reponse code from OAuth attempt'
                             .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), status_code))
            sys.exit()

    except Exception as e:
        sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
        sys.exit()


# refresh an existing auth token
def reddit_refresh_auth(r, scope, refresh_token, cfg_file, debug_level='NOTICE'):
    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        print('[{}] [NOTICE] Refreshing token for {}...'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cfg_file.get('auth', 'username')))

    try:
        # construct request data
        post_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }

        headers = {'User-Agent': cfg_file.get('auth', 'user_agent')}

        token_data, status_code = reddit_send_request(client_auth, post_data, headers)

        if status_code == 200:
            r.set_access_credentials(
                scope,
                token_data['access_token'])

            return token_data
        else:
            sys.stderr.write('[{}] [ERROR]: {} Reponse code from OAuth refresh attempt'
                             .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), status_code))
            sys.exit()

    except Exception as e:
        sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
        sys.exit()


###
# Flair Helpers
###

# get flairs that match specified condition
def reddit_get_valid_flair(flair, valid_flairs):
    valid_flair = ''

    # check that new flairs contain valid flair
    match = re.search(valid_flairs, flair)

    if match is not None:
        valid_flair = match.group()

    return valid_flair


# get flairs other than those that match specified condition
def reddit_get_additional_flair(flair, valid_flairs):
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
def reddit_get_all_flair(r, sub_names, valid_flairs, debug_level='NOTICE', progress=False):
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
            if progress is True and (debug_level == 'NOTICE' or debug_level == 'DEBUG'):
                sys.stdout.write('[%s] [NOTICE] Retrieving %i flair(s) from /r/%s...\r' %
                                 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index, sub_name))
                sys.stdout.flush()

            if flair['flair_css_class'] is not None:
                valid_flair = reddit_get_valid_flair(flair['flair_css_class'], valid_flairs)
                other_flair = reddit_get_additional_flair(flair['flair_css_class'], valid_flairs)

                if valid_flair != '':
                    sub_flairs[flair['user']] = {}
                    sub_flairs[flair['user']]['valid_flair'] = valid_flair
                    sub_flairs[flair['user']]['other_flair'] = other_flair

                    if flair['flair_text'] is not None:
                        sub_flairs[flair['user']]['flair_text'] = flair['flair_text']
                    else:
                        sub_flairs[flair['user']]['flair_text'] = ''

                    if debug_level == 'DEBUG':
                        print('[{}] [DEBUG] Retrieving from /r/{} ({}) User: {} has flair class: {}'  # and flair text: \'{}\''
                              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, index, flair['user'], flair['flair_css_class']))  # , flair['flair_text']))

        if progress is True and (debug_level == 'NOTICE' or debug_level == 'DEBUG'):
            sys.stdout.write('\n')
            sys.stdout.flush()
        elif debug_level == 'NOTICE' or debug_level == 'DEBUG':
            print('[{}] [NOTICE] Retrieved {} flair(s) from /r/{}'
                  .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index, sub_name))

        flairs[sub_name] = sub_flairs

    return flairs


# perform flair updates via a bulk set
def reddit_set_flair(r, sub_name, response, sync_flairs='y', debug_level='NOTICE'):
    if sync_flairs == 'n' or debug_level == 'NOTICE' or debug_level == 'DEBUG':
        for row in response:
            print('[{}] [NOTICE] In /r/{}, setting flair for User: {}, flair: {}, flair_text: {}'
                  .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, row['user'], row['flair_css_class'], row['flair_text'].encode('utf-8')))

    # confirm operation or proceed if automatic
    if sync_flairs == 'n':
        print('Sync {} flair(s) to /r/{}?'.format(len(response), sub_name))
        sync_flairs = raw_input('(y/n) ')
    else:
        print('[{}] Syncing {} flair(s) to /r/{}'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(response), sub_name))
        sync_flairs = 'y'

    if sync_flairs == 'y':
        # execute upload
        try:
            r.get_subreddit(sub_name).set_flair_csv(response)
        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: Error bulk setting flair: {}'
                             .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
            sys.exit()

        print('[{}] Bulk setting {} flair(s) to /r/{} successful!'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(response), sub_name))
