"""
Copyright (c) 2008-2011, Anthony Garcia <lagg@lavabit.com>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""

import web
import os
import json
import logging
import urllib2
import cPickle as pickle
import memcache
from email.utils import formatdate, parsedate
from time import time, mktime

import steam
from optf2.backend import config

memcached = memcache.Client([config.ini.get("cache", "memcached-address")],
                            pickleProtocol = pickle.HIGHEST_PROTOCOL)

# Keeps track of connection times, until I think of a better way
last_server_checks = {}

def _load_generic_cached(sclass, label, freshfunc = None, lang = None):
    """ For asset, schema, and whatever other compatible implementation """

    lm = None
    ctime = int(time())
    memkey = "{0}-{1}-{2}".format(label, web.ctx.current_game, lang)

    oldobj = memcached.get(memkey)
    if oldobj:
        if (ctime - last_server_checks.get(memkey, 0)) < config.ini.getint("cache", label + "-check-interval"):
            return oldobj
        lm = oldobj.get_last_modified()

    result = None
    try:
        result = sclass(lang = lang, lm = lm)
        if freshfunc: freshfunc(result)
        memcached.set(memkey, result, min_compress_len = 1048576)
    except steam.items.HttpStale:
        result = oldobj
    except Exception as E:
        logging.error("Cached loading error: {0}".format(E))
        result = oldobj

    last_server_checks[memkey] = ctime

    return result

def load_schema_cached(lang = None):
    def freshfunc(result):
        result.optf2_paints = {}
        for item in result:
            if item._schema_item.get("name", "").startswith("Paint Can"):
                for attr in item:
                    if attr.get_name().startswith("set item tint RGB"):
                        result.optf2_paints[int(attr.get_value())] = item.get_schema_id()

    try:
        modclass = getattr(steam, web.ctx.current_game).item_schema
    except AttributeError:
        raise steam.items.SchemaError("steamodd hasn't implemented a schema for {0}".format(web.ctx.current_game))

    return _load_generic_cached(modclass, "schema", freshfunc = freshfunc, lang = lang)

def load_assets_cached(lang = None):
    try:
        modclass = getattr(steam, web.ctx.current_game).assets
    except AttributeError:
        print("Failing asset load for " + web.ctx.current_game + " softly")
        return None

    return _load_generic_cached(modclass, "assets", lang = lang)

def load_profile_cached(sid, stale = False):
    memkey = "profile-" + str(sid)

    profile = memcached.get(memkey)
    if not profile:
        profile = steam.user.profile(sid)
        memcached.set(memkey, profile, time = config.ini.getint("cache", "profile-expiry"))

    return profile

def get_pack_timeline_for_user(user, tl_size = None):
    """ Returns None if a backpack couldn't be found, returns
    tl_size rows from the timeline
    """
    return []

def fetch_item_for_id(id64):
    return None

def load_pack_cached(user, pid = None):
    memkey = "backpack-{0}-{1}".format(web.ctx.current_game, user.get_id64())

    pack = memcached.get(memkey)
    if not pack:
        pack = getattr(steam, web.ctx.current_game).backpack(schema = load_schema_cached(web.ctx.language))
        pack.load(user)
        memcached.set(memkey, pack, time = config.ini.getint("cache", "backpack-expiry"))
    return pack

def get_user_pack_views(user):
    """ Returns the viewcount of a user's backpack """

    return 0

def get_top_pack_views(limit = 10):
    """ Will return the top viewed backpacks sorted in descending order
    no more than limit rows will be returned """

    return []
