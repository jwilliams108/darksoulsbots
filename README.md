# FlairSync
A python script/bot for [reddit](http://www.reddit.com) to keep flair in sync across related subreddits

## Requirements

FlairSync requires [PRAW](http://praw.readthedocs.org/en/latest/index.html), and also requires that you have correctly setup [OAuth access](https://github.com/reddit/reddit/wiki/OAuth2).

# Getting Started

To begin, create a flairsync.ini file from the sample provided, modifying fields as necessary - setup a list of your subreddits, as well as user and application credentials, and specify which flair(s) are considered valid (i.e., which to sync) via a regular expression.

You may choose between continuous or single mode - the former will keep the script running, executing the sync at an interval specified by loop_time (in seconds).

You may also choose between automatic or manual operation - automatic will determine which flair to choose based on the longest length, while manual will prompt the user for a selection.

In general, continuous and automatic mode/operation are meant to work together as a bot, while single and manual mode/operation are meant to function as a script.

Output verbosity can be changed by altering the debug level to DEBUG from NOTICE for more information on the actions being taken by the flairsync script.

## What's New

New version now supports syncing across more than two subs.

A note about automatic mode - it is based on flair length as this script is used across a set of subs that share platinum trophy flair - one for each game. Therefore, the longest valid flair string contains the most trophies and is considered the preferred flair.

### TODO
* only login if credentials have expired
