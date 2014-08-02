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
    """A web page with a list of tabs. The data for the web page is saved in one zotero collection.
    In the typical case, this will be as folows:
    - each item (usually a Document) represents a tab on the web page.
    - the item named 'Head' (usually a Web Page) contains some general html header info.
    - the hmtl file called 'template.html' is the tempalte to be used for inserting tabs data.
    - images ???

    The parameters are as follows:
    website_coll: The zotero path to the collection that holds all the data.
    template_coll: The zotero path to the collcetion hat holds the template file (template.html).
    images_coll: The zotero path to the collection that holds the images.
    website_filepath: The location on disk where to save html file (including the filename).
    images_dirpath: The location on disk where to save downloaded images.
    images_url: The url to use for images.
    
    """
    def __init__(self, website_coll, template_coll, images_coll):
        #Zotero collections
        self.website_coll = website_coll
        self.template_coll = template_coll
        self.images_coll = images_coll
        #The data
        self.template_str = None
        self.head = None
        self.tabs = []
        self.zot_images = None

    def initialize_data(self):
        """Get the data from the zotero database.
        """
        info_str = "Creating data for the " + self.website_coll + " website.\n"

        # Get the content
        try:
            coll = get_collection(self.website_coll)
            items = coll.get_items() #various items, e.g. documents
        except Exception:
            info_str += "ERROR: could not get sub-collections: '" + self.website_coll + "'.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str
        if not items:
            info_str += "ERROR: could not find any items to create tabs from.\n"
            return info_str

        # Get the images
        try:
            img_coll = get_collection(self.images_coll)
            self.zot_images = img_coll.get_image_attachments()
            for i in self.zot_images:
                print i.__dict__
        except Exception:
            info_str += "ERROR: could not get sub-collections: '" + self.images_coll + "'.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str

        # Get the template (i.e. the first html in the list of html attachments)
        try:
            files_coll = get_collection(self.template_coll)
            html_files = files_coll.get_html_attachments()
            self.template_str = html_files[0].get_file_data() # The template is assumed to be the first html file
        except Exception:
            info_str += "ERROR: could not get sub-collections: '" + self.template_coll + "'.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str
        if not html_files:
            info_str += "ERROR: could not find an html template file.\n"
            return info_str

        # Get the head item and create the tabs from the other items
        for item in items:
            if item.title == 'Head':
                self.head = item
            else:
                tab = WebTab(item)
                info_str += tab.initialize_data()
                self.tabs.append(tab)
        self.tabs.sort(key=lambda item: item.sort_key) # sort key is the Call Number
        if not self.head:
            info_str += "ERROR: Head was not found.\n"
            self.html_str = "No Head was found."
        if not self.tabs:
            info_str += "ERROR: no tabs were found.\n"
            self.html_str = "No html tabs were found."
        return info_str

    def _get_buttons_html(self):
        """Get an html string for the tab buttons. The html is encoded as utf-8.
        """
        return "".join([tab.get_button_html() for tab in self.tabs])

    def _get_content_html(self, images_url):
        """Get an html string for the content of all the tabs. The html is encoded as utf-8.
        """
        return "".join([tab.get_content_html(images_url) for tab in self.tabs])

    def _get_html(self, images_url):
        """Returns the full html for a web page with tabs. The template is a jinja2 template that 
        is attached to the item called Head (should be only one). The html is encoded as utf-8.
        """
        tabs_buttons = self._get_buttons_html().decode('utf-8')
        tabs_content = self._get_content_html(images_url).decode('utf-8')
        jinja_template = jinja2.Template(self.template_str.decode('utf-8'))
        return jinja_template.render(
            head=self.head, buttons=tabs_buttons, content=tabs_content).encode('utf-8')
    
    def _create_image_files(self, images_dirpath):
        """Create the image files for the website.
        """
        info_str = "  Creating image files.\n"
        # Get all the images in all web page tabs
        all_image_tags = []
        for tab in self.tabs:
            all_image_tags.extend(tab.html_content.image_tags.values())
        # Create the image object and ask it to generate the files
        images = Images(all_image_tags, images_dirpath, self.zot_images)
        info_str += images.create_image_files()
        return info_str

    def _create_html_file(self, website_filepath, images_url):
        """Create an html file. Filename includes the full path to the file. Any folders must
        exist. The html is encoded as utf-8.
        """
        info_str = "  Creating html file.\n"
        with open(website_filepath, 'w') as html_file:
            html_file.write(self._get_html(images_url))
        return info_str

    def create_website(self, website_filepath, images_url, images_dirpath):
        """Create all the files for the website.
        """
        info_str = "Writing files to disk: " + website_filepath + "\n"
        try:
            info_str += self._create_image_files(images_dirpath)
            info_str += self._create_html_file(website_filepath, images_url)
        except Exception:
            info_str += "ERROR: could not write files to disk. \n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
        return info_str




class Images(object):
    """A class for writing the image files. 
    """
    def __init__(self, image_tags, images_dirpath, zot_attachments):
        # The item that represents this tab
        self.image_tags = image_tags
        self.images_dirpath = images_dirpath
        self.zot_attachments = zot_attachments

    def _image_in_zotero(self, image_name):
        """Returns true if the image_name is in the list of attachments.
        """
        print sum([[att.filename, att.title] for att in self.zot_attachments], [])
        return image_name in sum([[att.filename, att.title] for att in self.zot_attachments], [])

    def _get_attachment_from_zotero(self, image_name):
        """Gets the attachment object from zotero that matches this image name. Note that the name
        will first try tomatch the filename, and if that fails it will try to match the title. This
        means that in zotero you can use either the fileame or the title to refer to the image.
        """
        att = [att for att in self.zot_attachments if att.filename == image_name]
        if not att:
            att = [att for att in self.zot_attachments if att.title == image_name]
        if not att:
            raise
        return att

    def _get_image_from_zotero(self, image_name):
        """Gets the image from zotero
        """
        att = self._get_attachment_from_zotero(image_name)
        image_data = att[0].get_file_data(binary=True)
        with open(os.path.join(self.images_dirpath, image_name), 'wb') as img_file:
            img_file.write(image_data)

    def _get_and_resize_image_from_zotero(self, original_name, new_name, width, height):
        """Resize the image according to the width and height.
        """
        att = self._get_attachment_from_zotero(image_name)
        image_filepath = att[0].get_file()
        #TODO: reszie the image

    def _image_in_dirpath(self, image_name):
        """Returns true if teh image_name is in the dirpath.
        """
        return os.path.isfile(os.path.join(self.images_dirpath, image_name))

    def _create_original_image(self, image_tag):
        """Create the original image.
        """
        if self._image_in_dirpath(image_tag.original_name):
            return "Image was in dirpath."
        if not self._image_in_zotero(image_tag.original_name):
            return "Image was not found in zotero."
        self._get_image_from_zotero(image_tag.original_name) 
        return "Image was created."

    def _create_new_image(self, image_tag):
        """Create the new image.
        """
        if self._image_in_dirpath(image_tag.new_name):
            return "Image was in dirpath."
        if not self._image_in_zotero(image_tag.original_name):
            return "Image was not found in zotero."
        self._get_and_resize_image_from_zotero(image_tag.original_name, image_tag.new_name, 
                                                image_tag.width, image_tag.height) 
        return "Image was created."

    def create_image_files(self):
        """Creates the images as follows. For each image tag, there are 2 images: the original 
        and the resized.
        """
        info_str = ""
        for image_tag in self.image_tags:
            try:
                info_str += "  Image name: " + image_tag.original_name + "\n"
                info_str += "  " + self._create_original_image(image_tag) + "\n"
                info_str += "  Image name: " + image_tag.new_name + "\n"
                info_str += "  " + self._create_new_image(image_tag) + "\n"
            except:
                #print "ERROR: could not create image file."
                info_str += "  EXCEPTION: \n" + traceback.format_exc() + "\n"
        return info_str



class WebTab(object):
    """A tab on a web page, consisting of html and images. In the zotero collection, the html is
    saved in notes, and images are saved as attachments.
    """
    def __init__(self, item):
        # The item that represents this tab
        self.item = item
        self.name = item.title
        self.sort_key = None
        self.html_id = None
        self.html_attachments = None
        self.html_content = None

    def initialize_data(self):
        """Add items based on data from zotero. Currently only three types of items are considered
        as being part of the web page: imagea are assumed to be attachments and artworks, and
        html is assumed to be an html attachment.

        If there is only one html attachment, then the 
        content is assumed to be that one. if there is more than one, then selects the one 
        with the 'html-content' tag. If that does not exist, the choose the first attachment.
        """
        info_str = "  Creating data for '" + self.name + "' tab.\n"
        try:
            self.sort_key = int(self.item.callNumber)
            self.html_id = self.item.title.lower().replace(' ', '-')
        except Exception:
            info_str += "  ERROR: Failed to set data for this web tabs.\n"
            info_str += "  EXCEPTION: \n" + traceback.format_exc() + "\n"
        try:
            self.html_attachments = self.item.get_html_attachments()
            if self.html_attachments:
                # Select the correct attachment
                info_str += "  Html content was found: " + str(len(self.html_attachments)) + " files.\n"
                if len(self.html_attachments) == 1:
                    selected = self.html_attachments[0]
                elif len(self.html_attachments) > 1:
                    for html_attachment in self.html_attachments:
                        if html_attachment.has_tag('html-content'):
                            selected = html_attachment
                            break
                    if not selected:
                        selected = self.html_attachments[0]
                # Create the HtmlContent object
                self.html_content = HtmlContent(self.html_id, selected)
                info_str += self.html_content.initialize_data()
            else:
                info_str += "  No html content was found."
        except Exception:
            info_str += "  ERROR: Failed to get data from the zotero database.\n"
            info_str += "  EXCEPTION: \n" + traceback.format_exc() + "\n"
        return info_str

    def get_button_html(self):
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

    def get_content_html(self, images_url):
        """Returns the html content of the tab, inside a <div> with an id attibute.
        """
        # Create wrapper
        soup = BeautifulSoup()
        div_tag = soup.new_tag('div')
        div_tag['id'] = self.html_id
        div_tag.append(BeautifulSoup(self.html_content.get_html(images_url)))
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
    def __init__(self, html_id, html_attachment):
        # The parent objects
        self.html_id = html_id
        self.html_attachment = html_attachment
        # The data
        self.html_str = None
        self.script_str = None
        self.image_tags = {}

    def initialize_data(self):
        """Get images and replace <img> and <pre> tags.
        """
        info_str = "    Creating data for html content.\n"
        try:
            html_str = self.html_attachment.get_file_data()
            soup = BeautifulSoup(html_str)
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
            # Create image tag objects
            for img_tag in soup.find_all('img'):
                image_tag = HtmlImageTag(str(img_tag))
                info_str += image_tag.initialize_data()
                self.image_tags[self._image_key(str(img_tag))] = image_tag
        except Exception:
            info_str += "    Failed to create html content.\n"
            info_str += "    EXCEPTION: \n" + traceback.format_exc() + "\n"
            self.html_str = "<p>No content found.</p>"
            self.toc_str = "<p>No content found.</p>"
        return info_str

    def _image_key(self, tag):
        """Creates a uniques key for image image, used as the key for the dict.
        """
        soup = BeautifulSoup(tag)
        soup_img = soup.find('img')
        src = soup_img.get('src')
        width = soup_img.get('width')
        height = soup_img.get('height')
        return str(src) + "_" + str(width) + "_" + str(height)

    def get_html(self, images_url):
        """Returns the html for the html content for this web page tab. 
        """
        # Process the html str
        self._process_jinja2()
        self._process_img_tags(images_url)
        self._process_h_tags()
        self._process_toc()
        return self.html_str

    def _process_jinja2(self):
        """Process html assuming it is a jinja2 template.
        The script can set the kwargs variable.
        """
        # Create template
        jinja_template = jinja2.Template(self.html_str.decode('utf-8'))
        if self.script_str:
            exec(self.script_str)
        try:
            kwargs
        except NameError:
            kwargs = {}
        self.html_str = jinja_template.render(**kwargs).encode('utf-8')

    def _process_img_tags(self, images_url):
        """Process img tags in the html: replace the src attribute.
        """
        # Create soup
        soup = BeautifulSoup(self.html_str)
        for old_img_soup in soup.find_all('img'):
            # Find the right tag
            image_tag = self.image_tags[self._image_key(str(old_img_soup))]
            # Update the html
            new_img = image_tag.get_html(images_url)
            new_img_soup = BeautifulSoup(new_img).contents[0]
            old_img_soup.replace_with(new_img_soup)
        self.html_str = str(soup)

    def _process_h_tags(self):
        """Process h tags in the html: add a unique index to each h.
        """
        # Create soup
        soup = BeautifulSoup(self.html_str)
        for i, soup_h in enumerate(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
            soup_h['id'] = "h_" + str(self.html_id) + "_" + str(i)
        self.html_str = str(soup)

    def _process_toc(self):
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
        #Add the toc to the end of the content
        toc_soup.append(soup)
        self.html_str = str(toc_soup)

class HtmlImageTag(object):
    """An image in an html page. 
    """
    def __init__(self, tag):
        # The args
        self.original_tag = tag
        # The data
        self.original_name = None
        self.height = None
        self.width = None
        self.new_name = None

    def initialize_data(self):
        """Init the image data. First, check if the image exists in the images folder. If not, then 
        create the image.
        """
        info_str = "      Creating image tag.\n"
        soup = BeautifulSoup(self.original_tag)
        soup_img = soup.find('img')
        self.original_name = soup_img.get('src')
        # Create the image urls
        width = soup_img.get('width')
        height = soup_img.get('height')
        self.new_name = self.original_name.split('.')[0]
        if width:
            self.width = width
            self.new_name += '_w' + str(width)
        if height:
            self.height = height
            self.new_name += '_h' + str(height)
        self.new_name += '.' + self.original_name.split('.')[1]
        info_str += "      Image names:" + self.original_name + ", " + self.new_name + "\n"
        return info_str

    def get_html(self, images_url):
        """Get the html for this image tag. When you click on the image, it links to a big version
        of the image.
        """
        img_original_url = images_url + self.original_name
        img_resized_url = images_url + self.new_name 
        # Create the new image tag
        a_img_soup = BeautifulSoup()
        a_tag = a_img_soup.new_tag('a')
        a_tag['href'] = img_original_url
        img_tag = a_img_soup.new_tag('img')
        img_tag['src'] = img_resized_url
        a_img_soup.append(a_tag)
        a_tag.append(img_tag)
        new_tag = str(a_img_soup)
        # Return
        return new_tag

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

    WEBSITE_COLL = "Patrick Janssen Websites/Dexen"
    FILES_COLL = "Patrick Janssen Websites/_Files"
    IMGS_COLL = "Patrick Janssen Websites/_Images"

    twp = TabbedWebsite(WEBSITE_COLL, FILES_COLL, IMGS_COLL) 
    print twp.initialize_data()

    WEBSITE_FILEPATH = CURR_DIR + "/test/index.html"
    IMAGES_DIRPATH = CURR_DIR + "/test/img/"
    IMAGES_URL = "./img/"

    print twp.create_website(WEBSITE_FILEPATH, IMAGES_URL, IMAGES_DIRPATH)
    print "Finished..."


if __name__ == "__main__":
    print "Generating website"
    test_tabs()