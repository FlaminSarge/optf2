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
import re
import time
import operator
import steam
from optf2.frontend.markup import get_class_for_id
from optf2.backend import config
from optf2.backend import log
import database

# Russia, for the sake of OPTF2. Give real symbol.
currencysymbols = {"USD": "$",
                   "RUB": "",
                   "GBP": unichr(0x00A3),
                   "EUR": unichr(0x20AC)}

class ItemError(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return str(self.msg)

class ItemBackendUnimplemented(ItemError):
    def __init__(self, msg):
        ItemError.__init__(self, msg)

def condensed_to_id64(value):
    return "7656" + str(int(value) + 1197960265728)

def build_page_object_unpositioned(items, pagesize = None):
    """ Returns the same thing build_page_object does, but
    ignores positioning info and places cells in the order
    items are listed, pagesize is the number of items per page """

    if not pagesize: pagesize = 50

    fitems = filter(None, items)
    ilen = len(fitems)
    pagecount = (ilen + (pagesize - (ilen % pagesize))) / pagesize
    imap = {}

    for page in xrange(1, pagecount + 1):
        offset = page * pagesize
        itemslice = fitems[offset - pagesize:offset]
        imap[page] = itemslice + ([None] * (pagesize - len(itemslice)))

    return imap

def build_page_object(items, pagesize = None, ignore_position = False):
    """ Returns a dict of items mapped to their sections and positions, or a default integer
    map if not implemented. Pagesize is the default minimum number of cells to a page
    if ignoreposition is true ignore any positioning info and build pages as items are given
    in the list """

    imap = {}
    displaced = []

    if not pagesize: pagesize = 50

    if ignore_position:
        return build_page_object_unpositioned(items, pagesize), displaced

    for item in items:
        if not item: continue

        itempos = item.get("pos")

        if not itempos:
            displaced.append(item)
            continue

        # Will use page names before
        # numbered if available
        pagename = item.get("cat")
        posrem = itempos % pagesize
        if posrem > 0: posrem += pagesize - posrem
        pageno = (itempos + posrem) / pagesize
        page = pageno
        roundedsize = pageno * pagesize
        realsize = pagesize

        if pagename:
            page = pagename
            realsize = roundedsize
        else:
            itempos -= roundedsize + 1

        imap.setdefault(page, [])
        pagelen = len(imap[page])
        if realsize > pagelen:
            imap[page] += [None] * ((realsize - pagelen) + 1)

        if imap[page][itempos] == None:
            imap[page][itempos] = item
        else:
            overlapped = imap[page][itempos]
            if overlapped.get("id") > item.get("id"):
                imap[page][itempos] = item
                displaced.append(overlapped)
            else:
                displaced.append(item)

    mkeys = sorted(imap.keys())
    mapkeys = set(mkeys)
    for key in mapkeys: del imap[key][0]

    try:
        if imap:
            lastpage = mkeys[-1]
            secrange = set(range(1, lastpage + 1))
            diff = secrange - mapkeys
            for key in diff: imap[key] = [None] * pagesize
    except TypeError:
        pass

    return imap, displaced

def sort(items, sortby):
    if not items:
        return []

    itemcmp = None

    if sortby == "id" or sortby == "time":
        itemcmp = lambda o: o.get("id", o.get("sid"))
    elif sortby == "level":
        def levelcmp(obj):
            level = obj.get("level")

            if level != None:
                try:
                    return int(level)
                except ValueError:
                    return level
        itemcmp = levelcmp
    elif sortby == "name":
        def namecmp(obj):
            if obj.get("cname"):
                return obj.get("mainname")
            else:
                return obj.get("basename")
        itemcmp = namecmp
    elif sortby == "slot":
        itemcmp = lambda o: o.get("slot", sorted(o.get("equipped", {}).values()))
    elif sortby == "class":
        itemcmp = lambda o: sorted(o.get("equipable", []))
    elif sortby == "schemaid":
        itemcmp = operator.itemgetter("sid")
    else:
        return items

    solid_items = items

    if itemcmp:
        solid_items = list(items)
        solid_items.sort(key = itemcmp)

        # TODO: For some reason some item systems don't have sequential IDs
        if sortby == "time":
            solid_items.reverse()

    return solid_items

def filter_by_class(items, theclass):
    return [item for item in items if item and theclass in item.get("equipable", [])]

def filter_by_quality(items, thequality):
    return [item for item in items if item and str(item.get("quality")) == str(thequality)]

def get_stats(items):
    """ Returns a dict of various backpack stats """
    stats = {"total": 0}
    merged = {
        "weapons": ["primary", "secondary", "melee", "weapon"],
        "hats": ["hat", "head"],
        "misc": ["misc"],
        "pda": ["pda", "pda2"],
        "other": ["none"]
        }

    for item in items:
        if not item: continue
        slot = item.get("slot", "none")

        stats["total"] += 1

        ismerged = False

        for label, slots in merged.iteritems():
            if slot.lower() in slots:
                stats.setdefault(label, 0)
                stats[label] += 1
                ismerged = True

        if not ismerged:
            stats.setdefault(slot, 0)
            stats[slot] += 1

    # Redundancy check
    othercount = stats.get("other")
    if othercount and othercount == stats["total"]:
        del stats["other"]

    return stats

def get_equippable_classes(items, cache):
    """ Returns a set of classes that can equip the listed items """
    if not items: return []
    classes = set()

    for item in items:
        if not item: continue
        classes |= set(item.get("equipable", []))

    return classes

def get_present_capabilities(items):
    """ Returns a sorted list of capabilities in this set of items,
    uses the capabilitydict """

    caps = set()
    for item in items:
        if not item: continue
        caps |= set(item.get("caps", []))

    return sorted(caps)

def get_present_qualities(items):
    """ Returns a sorted list of qualities that are in this set
    of items """

    qualities = set(map(operator.itemgetter("quality"), items))

    return sorted(qualities)

def filter_by_capability(items, capability):
    return [item for item in items if item and capability in item.get("caps", [])]

def get_price_stats(items, cache):
    try:
        assets = cache.get_assets()
    except database.CacheEmptyError:
        assets = {}

    stats = {"assets": assets, "sym": currencysymbols, "worth": {}, "most-expensive": [], "avg": {}}

    if not assets:
        return stats

    worth = stats["worth"]
    costs = []
    count = 0

    for item in items:
        if not item: continue
        # TODO? Checking origin string directly may cause problems for non-english origins
        origin = item.get("origin", '')
        if "id" in item and origin.lower() != "purchased":
            continue # Not explicit purchase
        try:
            asset = assets[item.get("sid")]
            count += 1
        except KeyError: continue
        costs.append((item, asset))
        for k, v in asset.iteritems():
            if k not in worth:
                worth[k] = v
            else:
                worth[k] += v

    stats["most-expensive"] = [item for item in sorted(costs, reverse = True, key = operator.itemgetter(1))[:10]]

    if count != 0:
        for k, v in worth.iteritems():
            stats["avg"][k] = round((v / count), 2)

    return stats
