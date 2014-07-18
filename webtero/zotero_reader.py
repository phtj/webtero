#!/usr/local/bin/python2.7
# ================================================================================================
#
#    Copyright (c) 2008, Patrick Janssen (patrick@janssen.name)
#
#    This file is part of Webtero.
#
#    Webtero is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Webtero is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Webtero.  If not, see <http://www.gnu.org/licenses/>.
#
# ================================================================================================
"""Reads data from a zotero group.
"""

from pyzotero import zotero
import urllib
import os
import traceback

# ================================================================================================
# Main Reader
# ================================================================================================

class ZoteroGroup(object):
    """ Reads a group in zotero database.
    """

    def __init__(self, group_name, zot_id, zot_key):
        """Make the connection to a group.
        """
        # Login
        self.name = group_name
        self.zot_id = zot_id
        self.zot_key = zot_key
        self.uid = None
        self.group_conn = None
        self.collections = {}

    def initialize_connection(self):
        """Tries to create a connection with the zotero database.
        """
        info_str = "Creating connection with zotero database using user id.\n"
        # Get the groups
        user_connection = zotero.Zotero(self.zot_id, 'user', self.zot_key)
        if not user_connection:
            info_str += "ERROR: Cannot connect to zotero user level database.\n"
            return info_str
        groups = user_connection.groups()
        # Find the right group
        group_id = None
        for group in groups:
            if group[u'name'] == self.name:
                group_id = group[u'group_id']
        if not group_id:
            info_str += "Can not find group '", self.name, "'\n"
            return info_str
        # Create a connection to that group
        info_str += self._initialize_conn_by_uid(group_id)
        # Return the info
        return info_str

    def _initialize_conn_by_uid(self, group_uid):
        """Tries to create a connection with the zotero database.
        """
        info_str = "Creating connection with zotero database using group id.\n"
        self.uid = group_uid
        # Create a connection to that group
        self.group_conn = zotero.Zotero(group_uid, 'group', self.zot_key)
        if not self.group_conn:
            info_str += "ERROR: Cannot connect to zotero group level database.\n"
        # Get the collections
        info_str += self._initialize_collections()
        # Return the info
        return info_str

    def _initialize_collections(self):
        """The path specifies the collection where to get the items from. The root is the group 
        root. The path looks like '/coll1/coll2/coll3'. If the collection does not exist, returns
        None. The other two args are used to filter the items that are returned.
        """
        info_str = "Initializing all the collections in this group from zotero.\n"
        try:
            colls = self.group_conn.collections()
            for coll in colls:
                coll_id = coll[u'collectionKey']
                coll_path = self._get_coll_path(colls, coll_id)
                self.collections[coll_path] = ZoteroCollection(self, coll_path, coll_id)
        except Exception:
            info_str += "ERROR: something went wrong trying to initializing collections."
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
        # Return the info
        return info_str

    def _get_coll_path(self, colls_data, coll_id):
        """Recursive method that gets the parent and adds it to the start of the path.
        """
        parent_id = True
        for a_coll in colls_data:
            a_coll_id = a_coll[u'collectionKey']
            if coll_id == a_coll_id:
                parent_id = a_coll[u'parent']
                coll_name = a_coll[u'name'].encode('utf-8')
                break
        if parent_id is True:
            raise Exception()
        elif parent_id is False:
            return '/' + coll_name
        else:
            return self._get_coll_path(colls_data, parent_id) + '/' + coll_name

    def get_collection(self, path):
        """Returns a collection in this group. If the collection does not exist, returns None.
        """
        if path in self.collections:
            return self.collections[path]
        return None


class ZoteroCollection(object):
    """Represents a zotero nested collection. Retrival of data from zotero is lazy - the data is 
    only downloaded the first time it is requiested.
    """
    def __init__(self, group, path, uid):
        self.group = group
        self.path = path
        self.uid = uid
        self.attachments = None
        self.items = None

    def initialize_data(self):
        """Get the data from zotero. Note that the root '/' contains everything, but at the moment 
        this method actually return nothing. 
        """
        coll_items_data = self.group.group_conn.collection_items(self.uid)
        self.attachments = []
        self.items = []
        for coll_item_data in coll_items_data:
            if coll_item_data[u'itemType'] == 'attachment':
                self.attachments.append(ZoteroAttachment(self.group, coll_item_data))
            else:
                self.items.append(ZoteroItem(self.group, coll_item_data))

    def get_attachments(self, tag=None):
        """Returns a list of ZoteroAttachment objects. If the data does not exist, it gets it from 
        zotero. 
        """
        if self.attachments is None:
            self.initialize_data()
        if tag:
            return [att for att in self.attachments if att.has_tag(tag)]
        return self.attachments

    def get_html_attachments(self, tag=None):
        """Returns a list of ZoteroAttachment objects. If the data does not exist, it gets it from 
        zotero. 
        """
        if self.attachments is None:
            self.initialize_data()
        if tag:
            return [att for att in self.attachments if att.has_tag(tag) and att.is_html()]
        return [att for att in self.attachments if att.is_html()]

    def get_image_attachments(self, tag=None):
        """Returns a list of ZoteroAttachment objects. If the data does not exist, it gets it from 
        zotero. 
        """
        if self.attachments is None:
            self.initialize_data()
        if tag:
            return [att for att in self.attachments if att.has_tag(tag) and att.is_image()]
        return [att for att in self.attachments if att.is_image()]

    def get_items(self, tag=None):
        """Returns a list of ZoteroItem objects. If the data does not exist, it gets it from 
        zotero. 
        """
        if self.items is None:
            self.initialize_data()
        if tag:
            return [item for item in self.items if item.has_tag(tag)]
        return self.items

    def get_subcollections(self):
        """Returns a list of paths to subcollections."
        """
        if path == '/':
            path_list = ['',]
        else:
            path_list = path.split('/')
        subcollections = []
        for coll_path in self.group.collections.keys():
            coll_path_list = coll_path.split('/')
            if len(coll_path_list) == len(path_list) + 1:
                if coll_path_list[:len(path_list)] == path_list:
                    subcollections.append(self.group.collections[coll_path])
        subcollections.sort(key=lambda coll: coll.path)
        return subcollections


class ZoteroItem(object):
    """A zotero Item. It has a unique id called 'uid'. Retrival of data from zotero is lazy - the 
    data is only downloaded the first time it is requiested.
    """
    def __init__(self, group, data):
        self.group = group
        self.attachments = None
        self.tags = []
        # Extract items out of the data
        for key, value in data.iteritems():
            if key == u'tags':
                for i in value:
                    self.tags.append(i[u'tag'].encode('utf-8'))
            elif key == u'key':
                self.uid = value.encode('utf-8')
            elif type(value) == unicode:
                if value != u'':
                    setattr(self, key.encode('utf-8'), value.encode('utf-8'))
            else:
                if value:
                    setattr(self, key.encode('utf-8'), value)

    def initialize_data(self):
        """Get the data from zotero.
        """
        self.attachments = []
        items_data = self.group.group_conn.children(self.uid)
        for item_data in items_data:
            item = ZoteroAttachment(self.group, item_data)
            self.attachments.append(item)

    def has_tag(self, tag):
        """Check is this item has a specified tag.
        """
        if tag in self.tags:
            return True
        return False

    def get_attachments(self, tag=None):
        """Return the children of this item.
        """
        if self.attachments is None:
            self.initialize_data()
        if tag:
            return [att for att in self.attachments if att.has_tag(tag)]
        return self.attachments

    def get_html_attachments(self, tag=None):
        """Return the children of this item that are contentType=text/html.
        """
        if self.attachments is None:
            self.initialize_data()
        if tag:
            return [att for att in self.attachments if att.is_html() and att.has_tag(tag)]
        return [att for att in self.attachments if att.is_html()]

    def get_image_attachments(self, tag=None):
        """Return the children of this item that are contentType=image/????.
        """
        if self.attachments is None:
            self.initialize_data()
        if tag:
            return [att for att in self.attachments if att.is_image() and att.has_tag(tag)]
        return [att for att in self.attachments if att.is_image()]

    def get_authors(self):
        "Get a string representing the authors."
        if not hasattr(self, 'creators') or not self.creators:
            return ""
        authors = []
        for creator in self.creators:
            if u'firstName' in creator.keys() and u'lastName' in creator.keys():
                if creator[u'creatorType'] == u'author':
                    first = creator[u'firstName'].encode('utf-8')
                    first = "".join([word[:1] for word in first.split()])
                    last = creator[u'lastName'].encode('utf-8')
                    authors.append(last + ", " + first)
        if len(authors) == 1:
            return authors[0]
        elif len(authors) == 2:
            return authors[0] + " and " + authors[1]
        else:
            return "; ".join(authors[:-1]) + " and " + authors[-1]

    def get_year(self):
        """Get the year - assumed to be the last 4 chars of the date.
        """
        if not hasattr(self, 'date') or not self.date or len(self.date) < 4:
            return ""
        return self.date[-4:]

    def __str__(self):
        """An str representation.
        """
        return str(self.__dict__)


class ZoteroAttachment(ZoteroItem):
    """A zotero attachment. It is the same an an item, except you can download the file. Retrival 
    of data from zotero is lazy - the data is only downloaded the first time it is requested.
    """
    def __init__(self, group, data):
        super(ZoteroAttachment, self).__init__(group, data)
        self.filepath = None
        self._is_html = self.contentType == 'text/html'
        self._is_image = self.contentType.startswith('image')

    def is_image(self):
        """Check if this attachemnt is an image.
        """
        return self._is_image

    def is_html(self):
        """Check if this attachemnt is an image.
        """
        return self._is_html

    def get_file(self):
        """Get the actual file attachment from zotero db. Returns a local path where the image was
        written to. Returns the temp file location.
        """
        if self.filepath is None:
            url = "https://api.zotero.org/groups/"
            url += self.group.uid
            url += "/items/"
            url += self.uid
            url += "/file?key="
            url += self.group.zot_key
            result = urllib.urlretrieve(url)
            if result:
                self.filepath = result[0]
            else:
                raise Exception()
        return self.filepath

    def get_file_data(self):
        path = self.get_file()
        with open(path, 'r') as attached_file:
            data = attached_file.read()
        return data


# ================================================================================================
# Utility Function to get items froma collection
# ================================================================================================

def get_collection(group_path):
    """Get the items from the collection.
    """
    parts = group_path.split('/')
    if len(parts) < 2:
        raise Exception()
    group_name = parts[0]
    coll_path = '/' + '/'.join(parts[1:])
    from zotero_auth import ZOT_ID, ZOT_KEY
    group = ZoteroGroup(group_name, ZOT_ID, ZOT_KEY)
    group.initialize_connection()
    return group.get_collection(coll_path)

# ================================================================================================
# Testing
# ================================================================================================

def test_get_data():
    """Simple test for getting data from zotero.
    """
    print "Starting..."
    from zotero_auth import ZOT_ID, ZOT_KEY
    group = ZoteroGroup("Patrick Janssen Websites", ZOT_ID, ZOT_KEY)
    print group.initialize_connection()
    coll = group.get_collection('/Dexen')
    print coll
    items = coll.get_items()
    for item in items:
        print "ITEM", item
        attachments = item.get_attachments()
        for attachment in attachments:
            print "ATTACH", attachment
            if attachment.is_html():
                print "======================================"
                print attachment.get_file_data()
                print "======================================"


def test_get_from_zot():
    items = test_get_data('Patrick Janssen/Conference Papers', 'dexen')
    #for item in items:
    #    print "ITEM", item


if __name__ == "__main__":
    print "Running tests"
    test_get_data()
