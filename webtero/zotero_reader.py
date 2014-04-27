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
"""Allows websites to be automatically generated based on data in a Zotero database. 
"""

from pyzotero import zotero
from BeautifulSoup import BeautifulSoup
import urllib
import os
from urlparse import urlparse

class Attachment(object):
    """Wraps the data for zotero attachment.
    """
    def __init__(self, group_reader, data):
        self.group_reader = group_reader
        self.zid = data[u'key'].encode('utf-8')
        self.note = data[u'note'].encode('utf-8')
        self.title = data[u'title'].encode('utf-8')
        self.filename = data[u'filename'].encode('utf-8')
        self.link_mode = data[u'linkMode'].encode('utf-8')
        self.tags = data[u'tags']
        # extract the tags
        if self.tags:
            self.tags = [tag.values()[0].encode('utf-8') for tag in self.tags]
        # cerate a url
        self.url = "https://api.zotero.org/groups/" + self.group_reader.group_id + \
            "/items/" + self.zid + "/file?key=" + self.group_reader.zot_key


class Note(object):
    """Wraps the data for a zotero note.
    """
    def __init__(self, group_reader, data):
        self.group_reader = group_reader
        self.zid = data[u'key'].encode('utf-8')
        self.note = data[u'note'].encode('utf-8')
        self.tags = data[u'tags']
        self.img_srcs = []
        self.process_tags()
        print self.img_srcs

    def process_tags(self):
        """Process img tags in html and download missing images.
        """
        soup = BeautifulSoup(self.note)
        for img in soup.findAll('img'):
            self.replace_img_tags(soup, img)
        for pre in soup.findAll('pre'):
            self.replace_pre_tags(soup, pre)
        self.note = str(soup)

    def replace_img_tags(self, soup, img):
        """Replace an img tag with a new one that points to a local image. If the img tag has no 
        src, then remove the tag.
        """
        # get the src
        if not img.has_key('src'):
            img.extract()
            return
        url = img['src']
        # see if the img has width or height
        width = None
        height = None
        if img.has_key('width'):
            width = img['width']
        if img.has_key('height'):
            height = img['height']
        new_url = self.create_img_src(url, width, height)
        img['src'] = new_url

    def create_img_src(self, url, width=None, height=None):
        """If the image does not ecist in the img folder, then copy the image. Also, the image may 
        need to be resized.
        """
        parsed_url = urlparse(url)
        netloc = parsed_url.netloc
        path, basename = os.path.split(parsed_url.path)
        img_name, img_ext = basename.split('.')
        # create the image name
        new_img_name = self.zid + "_" + img_name
        if width:
            new_img_name += "_w" + str(width)
        if height:
            new_img_name += "_h" + str(height)
        new_img_src = "/img/" + new_img_name + ".jpg"
        self.img_srcs.append(new_img_src)
        """
        new_img_loc = os.getcwd() + new_img_src
        print new_img_loc
        # see if this image exists, if not then create it
        if not os.path.isfile(new_img_loc):
            print "copy image"

            img_data = self.group_reader.get_attachment()
        return "test"
        """

    def replace_pre_tags(self, soup, pre):
        """Process pre tags in html and execute the instructions.
        """
        pass


class TabbedWebPage(object):
    """A web page with a list of tabs. Each tab is an instance of WebPageTab.
    """
    def __init__(self, group_reader, coll_name):
        self.group_reader = group_reader
        self.tabs = []
        tabs_data = self.group_reader.get_coll_subs(coll_name)
        for data in tabs_data:
            tab = WebPageTab(group_reader, data)
            self.tabs.append(tab)
        self.tabs.sort(key=lambda item: item.sort_key)


class WebPageTab(object):
    """A tab on a web page.
    """
    def __init__(self, group_reader, data):
        self.group_reader = group_reader
        # Get the  name and id
        coll_name = data[u'name'].encode('utf-8').split('_')
        coll_id = data[u'collectionKey'].encode('utf-8')
        if len(coll_name) != 2:
            raise Exception()
        # Set attributes
        self.sort_key = int(coll_name[0])
        self.name = coll_name[1]
        self.html_id = coll_name[1].lower().replace(' ', '-')
        self.notes = []
        self.attachments = []
        self.add_items(self.group_reader.get_coll_items_by_id(coll_id))

    def add_items(self, data):
        """Add items based on data from zotero.
        """
        for item in data:
            item_type = item[u'itemType'].encode('utf-8')
            if item_type == 'note':
                self.notes.append(Note(self.group_reader, item))
            elif item_type == 'attachment':
                self.attachments.append(Attachment(self.group_reader, item))
            elif item_type == "webpage":
                pass
            elif item_type == "artwork":
                pass

    def get_tab_button(self):
        """Return the tab button, an <a> inside an <li>.
        """
        return """
            <li>
                <a href='#{0}'>{1}</a>
            </li>""".format(self.html_id, self.name)

    def get_tab_content(self):
        """Returns the html content of the tab, i.e. the first note.
        """
        if len(self.notes):
            return """
            <div id='{0}'>
                <div class="left-col">
                    {1}
                </div>
                <div class="right-col">
                    <p>Images go here</p>
                </div>
            </div>
            """.format(self.html_id, self.notes[0])
        else:
            return """
            <div id="home">
                <p>Under construction...</p>
            </div>
            """

    def __str__(self):
        return self.name


class Paper(object):
    """Any type of paper. Superclass of ConferencePapaer and JournalPaper.
    """
    def __init__(self, uid, data):
        self.uid = uid
        self.authors = []
        self.title = data[u'title'].encode('utf-8')
        self.year = data[u'date'].encode('utf-8')[-4:]
        self.pages = data[u'pages'].encode('utf-8')
        self.abstract = data[u'abstractNote'].encode('utf-8')
        self.set_authors(data)
        # print data

    def check_keys(self, dictionary, keys):
        """ Check that the dict contains the list of keys.
        """
        for k in keys:
            if k not in dictionary.keys():
                print "Missing key: ", k
                return False
        return True

    def set_authors(self, data):
        """Set the paper authors.
        """
        creators = data[u'creators']
        for author in creators:
            if self.check_keys(author, [u'firstName', u'lastName']):
                first = author[u'firstName'].encode('utf-8')
                first = "".join([word[:1] for word in first.split()])
                last = author[u'lastName'].encode('utf-8')
                self.authors.append(last + ", " + first)

    def get_authors(self):
        "Get a string representing the authors."
        if len(self.authors) == 1:
            return self.authors[0]
        elif len(self.authors) == 2:
            return self.authors[0] + " and " + self.authors[1]
        else:
            return "; ".join(self.authors[:-1]) + " and " + self.authors[-1]

    def get_abstract_para(self):
        """Get the abstract wrapped in <p> and with an id.
        """
        return "<p class='abstract' id='"+self.uid+"'>" + self.abstract + "</p>"

    def get_list_item(self):
        """The paper as a list item. (Can be used in publication lists.)
        To be overridden in subclass.
        """
        pass

    def get_blog_post(self):
        """The paper as blog_post.
        To be overridden in subclass.
        """
        pass


class ConferencePaper(Paper):
    """ Adds proceedings title.
    """
    def __init__(self, uid, data):
        super(ConferencePaper, self).__init__(uid, data)
        self.conference = data[u'proceedingsTitle'].encode('utf-8')

    def get_list_item(self):
        author_str = "<button class='toggle' target='#"+self.uid+"'>+</button>"
        author_str += "<p class=publication>"
        author_str += "<pa>" + self.get_authors() + "</pa> "
        author_str += "<py>(" + self.year + ")</py> "
        author_str += "<pt>" + self.title + "</pt>, "
        author_str += "<pc>" + self.conference + "</pc>, "
        author_str += "<pp>pp. " + self.pages + "</pp>."
        author_str += "</p>"
        return "<li>" + author_str + "\n" + self.get_abstract_para() + "</li>\n"


class JournalPaper(Paper):
    """Adds journal title and volume/issue.
    """
    def __init__(self, uid, data):
        super(JournalPaper, self).__init__(uid, data)
        self.journal = data[u'publicationTitle'].encode('utf-8')
        self.volume = data[u'volume'].encode('utf-8')
        self.issue = data[u'issue'].encode('utf-8')

    def get_list_item(self):
        author_str = "<button class='toggle' target='#"+self.uid+"'>+</button>"
        author_str += "<p class=publication>"
        author_str += "<pa>" + self.get_authors() + "</pa> "
        author_str += "<py>(" + self.year + ")</py> "
        author_str += "<pt>" + self.title + "</pt>, "
        author_str += "<pj>" + self.journal + " " + self.volume + "(" + self.issue + ")" + "</pj>, "
        author_str += "<pp>pp. " + self.pages + "</pp>."
        author_str += "</p>"
        return "<li>" + author_str + "\n" + self.get_abstract_para() + "</li>\n"

# ================================================================================================
# Main Reader
# ================================================================================================


class ZoteroGroupReader(object):
    """ Reads a group in zotero database.
    """

    def __init__(self, zot_id, zot_key, group_name):
        """Make the connection to a group.
        """
        # login
        self.zot_id = zot_id
        self.zot_key = zot_key
        # get the groups
        user_connection = zotero.Zotero(zot_id, 'user', zot_key)
        if not user_connection:
            print "Cannot connect"
            raise Exception()
        groups = user_connection.groups()
        self.group_id = None
        for group in groups:
            if group[u'name'] == group_name:
                self.group_id = group[u'group_id']
        if not self.group_id:
            print "Can not find group '", group_name, "'\n\n"
            raise Exception()
        # get the data from the group
        group_conn = zotero.Zotero(self.group_id, 'group', zot_key)
        self.group_conn = group_conn

    def get_coll_id(self, coll_name):
        """Return the ID of a collection.
        """
        for coll in self.group_conn.collections():
            if coll[u'name'] == coll_name:
                return coll[u'collectionKey']
        print "Can not find collection '", coll_name, "'\n\n"
        raise Exception()

    def get_coll_items_by_name(self, coll_name, item_type=None):
        """Return the items in a collection, giving he name of the collection.
        """
        coll_id = self.get_coll_id(coll_name)
        return self.get_coll_items_by_id(coll_id, item_type)

    def get_coll_items_by_id(self, coll_id, item_type=None):
        """Return the items in a collection.
        """
        if item_type:
            items = self.group_conn.collection_items(coll_id, itemType=unicode(item_type))
        else:
            items = self.group_conn.collection_items(coll_id)
        return items

    def get_item_by_id(self, item_id):
        """Return a single item.
        """
        return self.group_conn.item(item_id)

    def get_children_by_id(self, item_id):
        """Return a single item.
        """
        return self.group_conn.children(item_id)

    def get_coll_subs(self, coll_name):
        """Return the sub collections in a collection.
        """
        coll_id = self.get_coll_id(coll_name)
        return self.group_conn.collections_sub(coll_id)

    def get_attachment(self, item_id):
        """Get the actual file attachment from zotero db.
        """
        url = "https://api.zotero.org/groups/"
        url += self.group_id 
        url += "/items/"
        url += item_id
        url += "/file?key="
        url += self.zot_key
        return urllib.retrieve(url)
# ================================================================================================
# Testing
# ================================================================================================

ZOT_ID = "xxx"
ZOT_KEY = "xxx"


def test_tabs():
    """Simple test for tabs"
    """
    print "Start testing..."
    group_reader = ZoteroGroupReader(ZOT_ID, ZOT_KEY, "Patrick Janssen Software")
    TabbedWebPage(group_reader, "Web_Dexen")
    print "Stop testing..."


if __name__ == "__main__":
    print "Running tests"
    test_tabs()
