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

# Built in python libs
import os
import traceback
import urllib
from urlparse import urlparse

# Third party libs
from pyzotero import zotero
from bs4 import BeautifulSoup, Tag
from PIL import Image
import jinja2

# My libs
from zotero_reader import get_collection

# ================================================================================================
# The main classes to make the website.
# ================================================================================================


class TabbedWebsite(object):
    """A web page with a list of tabs. The data for the web page is saved in one zotero collection,
    with each item representing a tab on the web page. For each tab, an instance of
    WebPageTab is created.
    """
    def __init__(self, group_path):
        self.group_path = group_path
        self.html_str = None

    def initialize_data(self):
        """Get the data from the zotero database.
        """
        info_str = "Creating data for the " + self.group_path + " website.\n"
        try:
            coll = get_collection(self.group_path)
            items = coll.get_items()
            image_attachments = coll.get_image_attachments()
            html_attachments = coll.get_html_attachments()
        except Exception:
            info_str += "ERROR: could not get sub-collections: '" + self.group_path + "'.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str
        # Check we have the right stuff to make a website
        if not items:
            info_str += "ERROR: could not find any items to create tabs from.\n"
            self.html = "No tabs were found."
            return info_str
        if not html_attachments:
            info_str += "ERROR: could not find an html template file.\n"
            self.html = "No html template was found."
            return info_str
        # Get the template (i.e. the first html in the list of html attachments)
        template_str = html_attachments[0].get_file_data()
        # Get the head item and create the tabs from the other items
        head = None
        tabs = []
        for item in items:
            if item.title == 'Head':
                head = item
            else:
                tab = WebTab(item, image_attachments)
                info_str += tab.initialize_data()
                tabs.append(tab)
        if not head or not tabs:
            info_str += "ERROR: could not get head and/or tabs.\n"
            self.html = "No html content was found."
        else:
            tabs.sort(key=lambda item: item.sort_key)
            self.html_str = self._get_html(template_str, head, tabs)
        return info_str

    def _get_buttons_html(self, tabs):
        """Get an html string for the tab buttons. The html is encoded as utf-8.
        """
        return "".join([tab.get_tab_button() for tab in tabs])

    def _get_content_html(self, tabs):
        """Get an html string for the content of all the tabs. The html is encoded as utf-8.
        """
        return "".join([tab.get_tab_content() for tab in tabs])

    def _get_html(self, template_str, head, tabs):
        """Returns the full html for a web page with tabs. The template is a jinja2 template that 
        is attached to the item called Head (should be only one). The html is encoded as utf-8.
        """
        tabs_buttons = self._get_buttons_html(tabs).decode('utf-8')
        tabs_content = self._get_content_html(tabs).decode('utf-8')
        jinja_template = jinja2.Template(template_str.decode('utf-8'))
        return jinja_template.render(
            head=head, tabs_buttons=tabs_buttons, tabs_content=tabs_content).encode('utf-8')

    def create_html_file(self, filename):
        """Create an html file. Filename includes the full path to the file. Any folders must
        exist. The html is encoded as utf-8.
        """
        info_str = "Writing html file to disk: " + filename + "\n"
        try:
            with open(filename, "w") as html_file:
                html_file.write(self.html_str)
        except Exception:
            info_str += "ERROR: could not write html file to disk. Maybe the path is wrong.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
        return info_str


class WebTab(object):
    """A tab on a web page, consisting of html and images. In the zotero collection, the html is
    saved in notes, and images are saved as attachments.
    """
    def __init__(self, item, images):
        # The item that represents this tab
        self.item = item
        self.images = images
        self.name = item.title
        self.sort_key = None
        self.html_id = None
        self.html = None

    def initialize_data(self):
        """Add items based on data from zotero. Currently only three types of items are considered
        as being part of the web page: imagea are assumed to be attachments and artworks, and
        html is assumed to be standalone notes.
        """
        info_str = "  Creating data for '" + self.name + "' tab.\n"
        try:
            self.sort_key = int(self.item.callNumber)
            self.html_id = self.item.title.lower().replace(' ', '-')
        except Exception:
            info_str += "  ERROR: Failed to set data for this web tabs.\n"
            info_str += "  EXCEPTION: \n" + traceback.format_exc() + "\n"
        try:
            htmls = self.item.get_html_attachments()
            if not htmls:
                self.html = "No html content was found."
                info_str += "  No html content was found."
            else:
                if len(htmls) == 1:
                    self.html = HtmlContent(htmls[0], self.images)
                elif len(htmls) > 1:
                    for html in htmls:
                        if html.has_tag('html-content'):
                            self.html = HtmlContent(html, self.images)
                            break
                    if not self.html:
                        self.html = HtmlContent(htmls[0], self.images)
                info_str += self.html.initialize_data()
        except Exception:
            info_str += "  ERROR: Failed to get data from the zotero database.\n"
            info_str += "  EXCEPTION: \n" + traceback.format_exc() + "\n"
        return info_str

    def get_tab_button(self):
        """Return the tab button, an <a> inside an <li>.
        """
        soup = BeautifulSoup()
        li_tag = soup.new_tag('li')
        a_tag = soup.new_tag('a')
        a_tag['href'] = '#' + self.html_id
        a_tag.string = self.name
        soup.append(li_tag)
        li_tag.append(a_tag)
        return str(soup)

    def get_tab_content(self):
        """Returns the html content of the tab, i.e. the note. If there is only one note, then the 
        content is assumed to be that note. if there is more than one note, then then one of the
        notes must have the 'main-text' tag.
        """
        # Create wrapper
        soup = BeautifulSoup()
        div_tag = soup.new_tag('div')
        div_tag['id'] = self.html_id
        div_tag.append(BeautifulSoup(self.html.html_str))
        div_tag.append(BeautifulSoup(self.html.toc_str))
        soup.append(div_tag)
        return str(soup)

    def __str__(self):
        return self.name


class HtmlContent(object):
    """An html page created from a zotero collection. The standalone notes in the collection are
    assumed to be the html content of a page. The attachments in the collection are assumed to be
    the images.

    The list of missing images looks something like this:
    [(img_zot_title, (img_loc, width, height), (img_loc, width, height)), ...]
    """
    def __init__(self, html, images):
        # The parent objects
        self.html = html
        self.images = images
        # The data
        self.html_str = None
        self.script_str = None
        self.toc_str = None
        self.missing_images = []

    def initialize_data(self):
        """Get images and replace <img> and <pre> tags.
        """
        info_str = "    Creating data for html content.\n"
        try:
            soup = BeautifulSoup(self.html.get_file_data())
            # Get the script
            script_tag = soup.find('script')
            if script_tag:
                self.script_str = script_tag.string
            # Get the body and wrap it in a div
            div_tag = soup.new_tag('div')
            div_tag['class'] = 'html-content'
            body_tag = soup.find('body')
            div_tag.contents = body_tag.contents
            self.html_str = str(div_tag)
            # Process the html str
            self._process_jinja2()
            self._process_img_tags()     
            self._process_h_tags()
        except Exception:
            info_str += "    Failed to find any html content (i.e. notes tagged 'html-content').\n"
            info_str += "    EXCEPTION: \n" + traceback.format_exc() + "\n"
            self.html_str = "<p>No content found.</p>"
            self.toc_str = "<p>No content found.</p>"
        return info_str

    def _process_jinja2(self):
        """Process html assuming it is a jinja2 template.
        """
        if not self.script_str:
            return info_str
        # Create template
        jinja_template = jinja2.Template(self.html_str.decode('utf-8'))
        exec(self.script_str)
        self.html_str = jinja_template.render(**kwargs).encode('utf-8')

    def _process_img_tags(self):
        """Process img tags in the html: replace the src attribute.
        """
        # Create soup
        soup = BeautifulSoup(self.html_str)
        for old_img_soup in soup.find_all('img'):
            image = HtmlImage(str(old_img_soup), self.images)
            image.initialize_data()
            new_img = image.get_html()
            new_img_soup = BeautifulSoup(new_img).contents[0]
            old_img_soup.replace_with(new_img_soup)
        self.html_str = str(soup)

    def _process_h_tags(self):
        """Process h tags in the html: add a unique index to each h.
        """
        # Create soup
        soup = BeautifulSoup(self.html_str)
        for i, soup_h in enumerate(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
            soup_h['id'] = "head_" + str(i)
        self.html_str = str(soup)
        # Create the toc
        self._make_toc()

    def _make_toc(self):
        """Creates a toc based on the headings, h1 to h6.
        """
        # Create soups
        soup = BeautifulSoup(self.html_str)
        toc_soup = BeautifulSoup()
        # Create the new tags for toc
        div_tag = toc_soup.new_tag('div')
        div_tag['class'] = 'toc'
        h2_tag = toc_soup.new_tag('h2')
        a_tag = toc_soup.new_tag('a')
        a_tag['href'] = '#top'
        a_tag.string = 'Contents'
        ul_tag = toc_soup.new_tag('ul')
        h2_tag.append(a_tag)
        toc_soup.append(div_tag)
        div_tag.append(h2_tag)
        div_tag.append(ul_tag)
        # For each heading, add an li
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            li_tag = toc_soup.new_tag('li')
            li_tag['class'] = heading.name
            a_tag = toc_soup.new_tag('a')
            a_tag.string = heading.string
            a_tag['href'] = '#' + heading['id']
            li_tag.append(a_tag)
            ul_tag.append(li_tag)
        self.toc_str = str(toc_soup)


class HtmlImage(object):
    """An image in an html page
    """
    def __init__(self, tag, images):
        # The parent objects
        self.tag = tag
        self.images = images
        # The data
        self.html_str = None

    def initialize_data(self):
        """Init the image data.
        """
        info_str = "    Creating data for images.\n"
        soup = BeautifulSoup(self.tag)
        soup_img = soup.find('img')
        print str(soup_img)
        src = soup_img.get('src')
        width = soup_img.get('width')
        height = soup_img.get('height')
        print "IMAGE", self.tag, src, width, height


        info_str = "    Creating data for images.\n"
        return info_str

    def get_html(self):
        """Get the html for this image tag.
        """
        return "<p>This is a test.</p>"

# ================================================================================================
# Testing
# ================================================================================================

def test_tabs():
    """Simple test for tabs.
    Make sure there is a sub-folder called "test".
    """
    print "Starting..."
    from zotero_auth import ZOT_ID, ZOT_KEY

    CURR_DIR = os.path.dirname(os.path.abspath(__file__))
    IMG_DIR = CURR_DIR + "/test/index.html"

    twp = TabbedWebsite("Patrick Janssen Websites/Dexen") 
    print twp.initialize_data()
    print twp.create_html_file(CURR_DIR + "/test/index.html")
    print "Finished..."


if __name__ == "__main__":
    print "Running tests"
    test_tabs()