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
"""Creates websites based on data in a Zotero collection.
"""

from pyzotero import zotero
from BeautifulSoup import BeautifulSoup, Tag
import urllib
import os
from urlparse import urlparse
from PIL import Image


class TabbedWebPage(object):
    """A web page with a list of tabs. The data for the web page is saved in one zotero collection,
    with each sub-collection representing a tab on the web page. For each tab, an instance of
    WebPageTab is created.
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
    """A tab on a web page, consisting of html and images. In the zotero collection, the html is
    saved in notes, and images are saved as attachments.
    """
    def __init__(self, group_reader, data):
        self.group_reader = group_reader
        self.coll_id = data[u'collectionKey'].encode('utf-8')
        # Get the name, which should be in the form "1_My Page"
        name_parts = data[u'name'].encode('utf-8').split('_')
        assert len(name_parts) == 2
        # Set attributes
        self.sort_key = int(name_parts[0])
        self.name = name_parts[1]
        self.html_id = name_parts[1].lower().replace(' ', '-')
        self.html_contet = []
        # Get notes from zotero and add to html_contet
        self.add_html_pages()

    def add_html_pages(self):
        """Add items based on data from zotero. Currently only three types of items are considered
        as being part of the web page: imagea are assumed to be attachments and artworks, and
        html is assumed to be standalone notes.
        """
        # Get the notes
        notes = self.group_reader.get_coll_items_by_id(coll_id=self.coll_id, item_type="note")
        # Add the notes
        for note in notes:
            self.html_contet.append(HtmlContent(self.group_reader, self.coll_id, note))

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

        if not self.html_contet:
            return """
            <div id="home">
                <p>Under construction...</p>
            </div>
            """
        # Is this one column or two columns
        one_column = None
        two_columns = [None, None]
        for page in self.html_contet:
            if 'left-col' in page.ztags:
                two_columns[0] = page
            elif 'right-col' in page.ztags:
                two_columns[1] = page
            else:  # assume 'single-col'
                one_column = page
        if two_columns[0] and two_columns[1]:
            if self.html_contet:
                return """
                <div id='{0}'>
                    <div class="left-col">
                        {1}
                    </div>
                    <div class="right-col">
                         {2}
                    </div>
                </div>
                """.format(self.html_id, two_columns[0].html, two_columns[1].html)
        elif one_column:
            if self.html_contet:
                return """
                <div id='{0}'>
                    <div class="single-col">
                        {1}
                    </div>
                </div>
                """.format(self.html_id, one_column.html)

    def __str__(self):
        return self.name


class HtmlContent(object):
    """An html page created from a zotero collection. The standalone notes in the collection are
    assumed to be the html content of a page. The attachments in the collection are assumed to be
    the images.
    """
    def __init__(self, group_reader, coll_id, data):
        assert data[u'itemType'].encode('utf-8') == 'note'
        self.group_reader = group_reader
        self.coll_id = coll_id  # This is the parent of this note
        self.zid = data[u'key'].encode('utf-8')
        self.ztags = [i.values()[0].encode('utf-8') for i in data[u'tags']]
        self.html = data[u'note'].encode('utf-8')
        self.missing_images = []
        self.process_html_tags()
        self.get_images_from_zotero()

    def process_html_tags(self):
        """Process img tags in html and download missing images.
        """
        # BeautifulSoup 3.2 code
        soup = BeautifulSoup(self.html)
        for soup_img in soup.findAll('img'):
            self.replace_img_src(soup_img)
        for soup_pre in soup.findAll('pre'):
            self.replace_pre(soup, soup_pre)
        self.html = str(soup)

    def replace_img_src(self, soup_img):
        """Replace an img tag with a new one that points to a local image. If the img tag has no
        src, then remove the tag.
        """
        # BeautifulSoup 3.2 code
        # Get the src attribute and convert to str
        src = soup_img.get('src').encode('utf-8')
        # Create the new src
        parsed_url = urlparse(src)
        _, img_filename = os.path.split(parsed_url.path)
        soup_img['src'] = "img/" + img_filename
        # Extract width and height from image name
        self.discover_missing_images(img_filename)

    def discover_missing_images(self, img_filename):
        """The name of the image may contain the required
        size constraints, for example 'my-image_w300_h200.png'. Underscores should only be used for
        seperating width and height parameters, otherwise errors will occur. Return the new img src.
        """
        img_name, img_extension = img_filename.split('.')
        # Check if the image file exists. If not, add this img to self.missing_images
        img_loc = os.path.join(os.getcwd(), "img", img_filename)
        if not os.path.isfile(img_loc):
            # See if the name contains _w? or_h? which are the max width and max height
            name_parts = img_name.split('_')
            width, height = None, None
            if len(name_parts) > 1:
                if name_parts[1].startswith('h'):
                    height = int(name_parts[1][1:])
                elif name_parts[1].startswith('w'):
                    width = int(name_parts[1][1:])
            if len(name_parts) == 3:
                if name_parts[2].startswith('h'):
                    height = int(name_parts[2][1:])
                elif name_parts[2].startswith('w'):
                    width = int(name_parts[2][1:])
            # Create the zotero title for the image (i.e. the filename without the _w? and _h?)
            img_zot_title = name_parts[0] + '.' + img_extension
            self.missing_images.append((img_zot_title, img_loc, width, height))

    def get_images_from_zotero(self):
        """Tries to find the images in self.missing_images as attachments in the zotero collection
        for this page. If the attachment is found, it then downloads the attachment, resizes it
        with PIL, and the saves the image to the img folder.
        """
        # Check we have some missing images
        if not self.missing_images:
            return
        # Get all attachments
        attachments = self.group_reader.get_coll_items_by_id(
            coll_id=self.coll_id, item_type="attachment")
        # Creat a dict to store images
        images = {}
        # Create the Image objects
        for attachment in attachments:
            image = HtmlImage(self.group_reader, self.coll_id, attachment)
            images[image.title] = image
        # For each img, try to find it in attachments
        for missing_img in self.missing_images:
            img_zot_title, new_img_loc, width, height = missing_img
            if img_zot_title in images:
                image = images[img_zot_title]
                image.create_image_file(new_img_loc, width, height)
            else:
                print "Could not find image: ", img_zot_title

    def replace_pre(self, soup, soup_pre):
        """Process pre tags in html and execute the instructions.
        """
        # BeautifulSoup 3.2 code
        result = eval(soup_pre.string)
        group = result['group']
        coll = result['coll']
        item_type = result['item_type']
        tag = result['tag']
        style = result['style']
        # Create a reader and download data
        reader = ZoteroGroupReader(self.group_reader.zot_id, self.group_reader.zot_key, group)
        items = reader.get_coll_items_by_name(coll, item_type, tag)
        # print result
        # print items
        # Create an html string
        html_string = ""
        for i, item in enumerate(items):
            # print "item in pubs"
            if style == "conference_paper":
                # print "make conf paper"
                paper = ConferencePaper(str(i), item)
                html_string += paper.get_list_item() + "\n\n"
        # Create a new tag with html_string as content
        print html_string
        html_soup = BeautifulSoup(html_string)
        new_tag = Tag(soup, 'ul')
        new_tag.contents = html_soup  # ------------------------------------------------------- TODO
        soup_pre.replaceWith(new_tag)


class HtmlImage(object):
    """An html image created from a zotero attachment. We assume that the src for this image uses
    the 'title' attribute for linking to images, since in zotero this is more logical and flexible
    for the user.
    """
    def __init__(self, group_reader, coll_id, data):
        assert data[u'itemType'].encode('utf-8') == 'attachment'
        self.group_reader = group_reader
        self.coll_id = coll_id
        self.zid = data[u'key'].encode('utf-8')
        self.note = data[u'note'].encode('utf-8')
        self.title = data[u'title'].encode('utf-8')
        self.filename = data[u'filename'].encode('utf-8')
        # self.link_mode = data[u'linkMode'].encode('utf-8')
        self.tags = data[u'tags']
        # extract the tags
        if self.tags:
            self.tags = [tag.values()[0].encode('utf-8') for tag in self.tags]
        # cerate a url
        self.url = "https://api.zotero.org/groups/" + self.group_reader.group_id + \
            "/items/" + self.zid + "/file?key=" + self.group_reader.zot_key

    def create_image_file(self, img_path_filename, width=None, height=None):
        """Downloads the image, resizes it, and saves it in the '/img' folder.
        """
        # Get the image
        tmp_img = self.group_reader.get_attachment_file(self.zid)
        print tmp_img
        pil_img = Image.open(tmp_img)
        # Resize the image
        img_w, img_h = pil_img.size
        size_1 = (img_w, img_h)
        size_2 = (img_w, img_h)
        if width:
            size_1 = (width, int((width/float(img_w)) * img_h))
        if height:
            size_2 = (int((height/float(img_h)) * img_w), height)
        if size_1[0] > size_2[0]:
            size = size_2
        else:
            size = size_1
        pil_img_resized = pil_img.resize(size, Image.ANTIALIAS)
        # Save the image
        pil_img_resized.save(img_path_filename, quality=100)


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
        # Login
        self.zot_id = zot_id
        self.zot_key = zot_key
        # Get the groups
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
        # Get the data from the group
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

    def get_coll_items_by_name(self, coll_name, item_type=None, tag=None):
        """Return the items in a collection, giving the name of the collection.

        item_type can be Note, Attachment, ConferencePaper
        """
        coll_id = self.get_coll_id(coll_name)
        return self.get_coll_items_by_id(coll_id, item_type, tag)

    def get_coll_items_by_id(self, coll_id, item_type=None, tag=None):
        """Return the items in a collection.
        """
        search_params = {}
        if item_type:
            search_params['itemType'] = unicode(item_type)
        if tag:
            search_params['tag'] = unicode(tag)
        return self.group_conn.collection_items(coll_id, **search_params)

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

    def get_attachment_file(self, item_id):
        """Get the actual file attachment from zotero db. Returns a local path where the image was
        written to.
        """
        url = "https://api.zotero.org/groups/"
        url += self.group_id
        url += "/items/"
        url += item_id
        url += "/file?key="
        url += self.zot_key
        result = urllib.urlretrieve(url)
        if result:
            return result[0]
        else:
            return None  # Something went wrong

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
