from datetime import datetime
import requests
import requests.auth
import sys
import re
from praw import Reddit


###
# Authentication Helpers
###
#
# login to reddit using OAuth w/ supplied refresh token
def reddit_login(cfg_file, debug_level='NOTICE'):

    if debug_level == 'NOTICE' or debug_level == 'DEBUG':
        print('[{}] [NOTICE] Logging in to Reddit...'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    try:
        r = Reddit(client_id=cfg_file.get('auth', 'client_id'),
                   client_secret=cfg_file.get('auth', 'client_secret'),
                   refresh_token=cfg_file.get('auth', 'refresh_token'),
                   user_agent=cfg_file.get('auth', 'user_agent'))

    except Exception as e:
        sys.stderr.write('[{}] [ERROR]: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))
        sys.exit()

    return r


###
# Flair Helpers
###
#
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
        flair_list = r.subreddit(sub_name).flair()
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


# set flairs via update
def reddit_set_flair(r, sub_name, flairs, sync_flairs='y', debug_level='NOTICE'):
    if sync_flairs == 'n' or debug_level == 'NOTICE' or debug_level == 'DEBUG':
        for flair in flairs:
            print('[{}] [NOTICE] In /r/{}, setting flair for User: {}, flair: {}, flair_text: {}'
                  .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_name, flair['user'], flair['flair_css_class'], flair['flair_text'].encode('utf-8')))

    # confirm operation or proceed if automatic
    if sync_flairs == 'n':
        print('Sync {} flair(s) to /r/{}?'.format(len(flairs), sub_name))
        sync_flairs = raw_input('(y/n) ')
    else:
        print('[{}] Syncing {} flair(s) to /r/{}'
              .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(flairs), sub_name))
        sync_flairs = 'y'

    if sync_flairs == 'y':
        try:
            response = r.subreddit(sub_name).flair.update(flairs)

            if response[0]['ok'] is True:
                print('[{}] Updating {} flair(s) to /r/{} successful!'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(flairs), sub_name))
            else:
                sys.stderr.write('[{}] [ERROR]: Error updating flair: {}\n'
                    .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), response[0]['status']))

        except Exception as e:
            sys.stderr.write('[{}] [ERROR]: Error updating flair: {}\n'
                .format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), e))


###
# Post helpers
###
#
# reply to comment
def reddit_reply_to_comment(comment, text=None, distinguish=True):
    if text is not None:
        reply_comment = comment.reply(text)

        if distinguish:
            reply_comment.distinguish()
