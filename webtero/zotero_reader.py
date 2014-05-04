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

Many things TODO:
- when getting zot notes from the db for a tabbed web page, we should filter with tag 'main-text'
- at the moment, it is creating html content for all tabs it finds. maybe only the first is 
necessary
- the info_str should be a nested list
"""

from pyzotero import zotero
from bs4 import BeautifulSoup, Tag
import urllib
import os
from urlparse import urlparse
from PIL import Image
from string import Template
import traceback

# ================================================================================================
# A BeautifulSoup helper func
# ================================================================================================

def bs_create_tag(soup, parent, name, attribs=None, string=None):
    """A helper func to create a tag.
    """
    tag = soup.new_tag(name)
    if attribs:
        for key in attribs:
            tag[key] = attribs[key]
    if string:
        tag.string = string
    parent.append(tag)
    return tag

# ================================================================================================
# The main classes to make the website.
# ================================================================================================

class TabbedWebsite(object):
    """A web page with a list of tabs. The data for the web page is saved in one zotero collection,
    with each sub-collection representing a tab on the web page. For each tab, an instance of
    WebPageTab is created.
    """
    def __init__(self, group_reader, coll_name):
        self.group_reader = group_reader
        self.coll_name = coll_name
        self.img_dir = os.path.join(os.getcwd(), 'img')
        self.tabs = []

    def initialize_data(self, img_dir=None):
        """Get the data from the zotero database.
        """
        info_str = "Initializing data for the " + self.coll_name + " website.\n"
        if img_dir:
            self.img_dir = img_dir
            info_str += "Updated the image dir to " + img_dir + "\n"
        try:
            info_str += "Getting data for sub-collections for collection '" \
                + self.coll_name + "'.\n"
            tabs_data = self.group_reader.get_coll_subs(self.coll_name)
        except Exception:
            info_str += "ERROR: could not get sub-collections for collection '" \
                + self.coll_name + "'.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str
        for data in tabs_data:
            tab = WebPageTab(self, data)
            info_str += tab.initialize_data()
            self.tabs.append(tab)
        self.tabs.sort(key=lambda item: item.sort_key)
        return info_str

    def _get_buttons_html(self):
        """Get an html string for the tab buttons. The html is encoded as utf-8.
        Make sure _initialize_data() has been called first.
        """
        return "".join([tab.get_tab_button() for tab in self.tabs])

    def _get_content_html(self):
        """Get an html string for the content of all the tabs. The html is encoded as utf-8.
        Make sure _initialize_data() has been called first.
        """
        return "".join([tab.get_tab_content() for tab in self.tabs])

    def _get_html(self, template):
        """Returns the full html for a web page with tabs. The template is a plain string, and
        is expected to have three variables: $title, $tabs_buttons, $tabs_content. The html is
        encoded as utf-8.
        Make sure _initialize_data() has been called first.
        """
        template = Template(template)
        page_html = template.substitute(
            title=self.coll_name,
            tabs_buttons=self._get_buttons_html(),
            tabs_content=self._get_content_html())
        return page_html
        # Seems to affect scrollbar so prettify disabeled for the moment
        # soup = BeautifulSoup(page_html)
        # soup = soup.prettify().encode('UTF-8')
        # return str(soup)

    def create_html_file(self, template, filename):
        """Create an html file. Filename includes the full path to the file. The html is
        encoded as utf-8.
        """
        info_str = "Writing html file to disk: " + filename + "\n"
        try:
            with open(filename, "w") as html_file:
                html_file.write(self._get_html(template))
        except Exception:
            info_str += "ERROR: could not write html file to disk. Maybe the path is wrong.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
        return info_str

class WebPageTab(object):
    """A tab on a web page, consisting of html and images. In the zotero collection, the html is
    saved in notes, and images are saved as attachments.
    """
    def __init__(self, tabbed_website, data):
        # The parent
        self.tabbed_website = tabbed_website
        # The data
        self.coll_id = data[u'collectionKey'].encode('utf-8')
        name_parts = data[u'name'].encode('utf-8').split('_')  # e.g. "1_My Page"
        assert len(name_parts) == 2
        # Set attributes
        self.sort_key = int(name_parts[0])
        self.name = name_parts[1]
        self.html_id = name_parts[1].lower().replace(' ', '-')
        self.html_content = []

    def initialize_data(self):
        """Add items based on data from zotero. Currently only three types of items are considered
        as being part of the web page: imagea are assumed to be attachments and artworks, and
        html is assumed to be standalone notes.
        """
        # Get the notes
        info_str = "Initializing data for '" + self.name + "' tab.\n"
        group_reader = self.tabbed_website.group_reader
        try:
            notes = group_reader.get_coll_items_by_id(coll_id=self.coll_id, item_type="note")
            info_str += "Found " + str(len(notes)) + " notes in the zotero database.\n"
        except Exception:
            info_str += "ERROR: Failed to get data from the zotero database.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return
        # Add the notes
        for note in notes:
            info_str += "Creating HTML content from note.\n"
            try:
                html_content = HtmlContent(self.tabbed_website, self, note)
                info_str += html_content.initialize_data()
                self.html_content.append(html_content)
            except Exception:
                info_str += "Error: Failed to create HTML content from note.\n"
                info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
        # Return the info
        return info_str

    def get_tab_button(self):
        """Return the tab button, an <a> inside an <li>.
        """
        return """
            <li>
                <a href='#{0}'>{1}</a>
            </li>""".format(self.html_id, self.name)

    def get_tab_content(self):
        """Returns the html content of the tab, i.e. the note. If there is only one note, then the 
        content is assumed to be that note. if there is more than one note, then then one of the
        notes must have the 'main-text' tag.
        """
        # Get the html
        main_text = None
        if len(self.html_content) == 1:
            main_text = self.html_content[0]
        else:
            for page in self.html_content:
                if 'main-text' in page.ztags:
                    main_text = page
        # Create the template
        template = """
            <div id='{0}'>
                <div class="main-text">
                    {1}
                </div>
                <div class="toc">
                     {2}
                </div>
            </div>
            """
        # Return the html text
        if main_text:
            return template.format(self.html_id, main_text.html, main_text.make_toc())
        else:
            return template.format(self.html_id, "Under construction...", "Under construction...")

    def __str__(self):
        return self.name


class HtmlContent(object):
    """An html page created from a zotero collection. The standalone notes in the collection are
    assumed to be the html content of a page. The attachments in the collection are assumed to be
    the images.

    The list of missing images looks something like this:
    [(img_zot_title, (img_loc, width, height), (img_loc, width, height)), ...]
    """
    def __init__(self, tabbed_website, web_page_tab, data):
        assert data[u'itemType'].encode('utf-8') == 'note'
        # The parent objects
        self.tabbed_website = tabbed_website
        self.web_page_tab = web_page_tab
        # The data
        self.zid = data[u'key'].encode('utf-8')
        self.ztags = [i.values()[0].encode('utf-8') for i in data[u'tags']]
        self.html = data[u'note'].encode('utf-8')
        self.images = {}
        self.missing_images = []

    def initialize_data(self):
        """Get images and replace <img> and <pre> tags.
        """
        info_str = "Initializing data for html content.\n"
        info_str += self.process_html_tags()
        info_str += self.get_attachments_from_zotero()        
        info_str += self.get_images_from_zotero()
        return info_str

    def process_html_tags(self):
        """Process img tags in html and download missing images.
        """
        info_str = "Looking for img,  pre, and h? tags.\n"
        # BeautifulSoup 4 code
        soup = BeautifulSoup(self.html)
        for soup_img in soup.find_all('img'):
            self.replace_img(soup, soup_img)
            info_str += "Found img tag.\n"
        for soup_pre in soup.find_all('pre'):
            info_str += self.replace_pre(soup, soup_pre)
            info_str += "Found pre tag.\n"
        for i, soup_h in enumerate(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
            soup_h['id'] = "head_" + str(i)
            info_str += "Found h? tag.\n"
        self.html = str(soup)
        return info_str

    def replace_img(self, soup, soup_img):
        """Replace an img tag with a new one that points to a local image. If the img tag has no
        src, then remove the tag. Also, add a link and point to the big image.
        """
        # Get the src attribute and convert to str
        src = soup_img.get('src').encode('utf-8')
        # Go see if the images exist, if not add them to the missing list
        sml_img_href, big_img_href = self.discover_missing_images(src)
        # Create the new html nodes, an <a><img /></a>
        soup_img['src'] = sml_img_href
        a_tag = soup.new_tag('a')
        a_tag['href'] = big_img_href
        soup_img.wrap(a_tag)

    def discover_missing_images(self, src):
        """The name of the image may contain the required
        size constraints, for example 'my-image_w300_h200.png'. Underscores should only be used for
        seperating width and height parameters, otherwise errors will occur. Return the new img
        hrefs for the small and big versions of the image.
        """
        image_details = []
        # Get the filename
        parsed_url = urlparse(src)
        _, img_filename = os.path.split(parsed_url.path)
        # Create the various names
        img_name, img_extension = img_filename.split('.')
        name_parts = img_name.split('_')
        big_img_filename = name_parts[0] + '_w1200_h1200.' + img_extension
        img_zot_title = name_parts[0] + '.' + img_extension
        img_dir = self.tabbed_website.img_dir
        sml_img_loc = os.path.join(img_dir, img_filename)
        big_img_loc = os.path.join(img_dir, big_img_filename)
        sml_img_href = 'img/' + img_filename
        big_img_href = 'img/' + big_img_filename
        if not os.path.isfile(sml_img_loc):
            # See if the name contains _w? or_h? which are the max width and max height
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
            image_details.append((sml_img_loc, width, height))
        # Check if the big image exists.
        if not os.path.isfile(big_img_loc):
            image_details.append((big_img_loc, 1200, 1200))
        # Append the missing images to the list
        if image_details:
            self.missing_images.append((img_zot_title, image_details))
        # Return the hrefs
        return sml_img_href, big_img_href

    def get_attachments_from_zotero(self):
        """Gets all the attachments, and assumes they are all images.
        """
        info_str = "Getting image attachments from zotero.\n"
        # Get the reader and coll id from the parents
        group_reader = self.tabbed_website.group_reader
        coll_id = self.web_page_tab.coll_id
        # Get all attachments
        try:
            attachments = group_reader.get_coll_items_by_id(coll_id=coll_id, item_type="attachment")
        except Exception:
            info_str = "ERROR: something went wrong when getting image attachments.\n"
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str
        # Create the Image objects
        for attachment in attachments:
            info_str = "Found attachment: " + image.title + ".\n"
            image = HtmlImage(group_reader, coll_id, attachment)
            self.images[image.title] = image
        # return the info string
        return info_str

    def get_images_from_zotero(self):
        """Tries to find the images in self.missing_images as attachments in the zotero collection
        for this page. If the attachment is found, it then downloads the attachment, resizes it
        with PIL, and the saves the image to the img folder.
        """
        info_str = "Getting images from zotero.\n"
        # Check we have some missing images
        if not self.missing_images:
            info_str += "No missing images were found.\n"
            return info_str
        # For each img, try to find it in attachments
        for missing_img in self.missing_images:
            info_str += "Getting missing image: " + str(missing_img) + ".\n"
            img_zot_title, image_details = missing_img
            if img_zot_title in self.images:
                image = self.images[img_zot_title]
                image.download_image()  # This way we only download the image once
                for image_detail in image_details:
                    img_loc, width, height = image_detail
                    image.create_image_file(img_loc, width, height)
            else:
                info_str += "Could not find image: "
        return info_str

    def replace_pre(self, soup, soup_pre):
        """Process pre tags in html and execute the instructions.
        The instructions are assumed to be in the form of a python dict, with the following key 
        value pairs:
        group: the group name
        coll: the collection name
        item_type: the type of item that is expected (e.g. ConferencePaper, JournalArticle, etc)
        style: the style to use to format the result
        tag: an optional tag to pass to the zotero query as a filter
        """
        info_str = "Replacing the pre tag.\n"
        # Evaluate the pre tag
        try:
            result = eval(soup_pre.string)
        except Exception:
            info_str += "ERROR: could not evaluate the contents of the pre tag.\n"
            return info_str
        # Get the settings
        group_name = result['group']
        coll = result['coll']
        item_type = result['item_type']
        style = result['style']
        # Check if there is a tag
        tag = None
        if result.has_key('tag'):
            tag = result['tag']
        # Create a reader and download data
        zot_id = self.tabbed_website.group_reader.zot_id
        zot_key = self.tabbed_website.group_reader.zot_key
        data_group_reader = ZoteroGroupReader(zot_id, zot_key)
        info_str += data_group_reader.initialize_conn_group_name(group_name)
        try:
            items = data_group_reader.get_coll_items_by_name(coll, item_type, tag)
        except Exception:
            info_str += "ERROR: Something went getting items from collection."
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
            return info_str
        # Create an html soup
        soup_pre_rep = self.create_pre_replacement(items, style)
        soup_pre.replace_with(soup_pre_rep.contents[0])
        # Return the info str
        return info_str


        """
        # Create an html string
        html_tag = None
        if style == "conference_paper":
            papers = []
            for i, item in enumerate(items):
                paper = ConferencePaper(str(i), item)
                papers.append(paper)
            papers.sort(key=lambda paper: paper.year, reverse=True)
            html_string = ""
            for paper in papers:
                html_string += paper.get_list_item()  #TODO: change to soup
            # Wrap in ul
            html_string = "<ul class='publications-list'>" + html_string + "</ul>"
            html_soup = BeautifulSoup(html_string)
            html_tag = html_soup.contents[0]
        elif style == "journal_paper":
            papers = []
            for i, item in enumerate(items):
                paper = JournalPaper(str(i), item)
                papers.append(paper)
            papers.sort(key=lambda paper: paper.year, reverse=True)
            html_string = ""
            for paper in papers:
                html_string += paper.get_list_item()  #TODO: change to soup
            # Wrap in ul
            html_string = "<ul class='publications-list'>" + html_string + "</ul>"
            html_soup = BeautifulSoup(html_string)
            html_tag = html_soup.contents[0]
        else:
            raise Exception()
        soup_pre.replace_with(html_tag)"""

    def create_pre_replacement(self, items, style):
        """Converts this list of items into an html soup
        """
        # Create the list of objects
        mapping = {
            "conference_paper": ConferencePaper,
            "journal_paper": JournalPaper,
            "research_project": ResearchProject
        }
        objects = []
        for i, item in enumerate(items):
            _class = mapping[style]
            obj = _class(str(i), item)
            objects.append(obj)
        objects.sort(key=lambda paper: obj.sort_key, reverse=True)
        # Create the soup
        html_string = ""
        html_soup = BeautifulSoup(html_string)
        ul_tag = html_soup.new_tag("ul")
        ul_tag['class'] = 'publications-list'
        html_soup.append(ul_tag)
        for obj in objects:
            ul_tag.append(obj.get_list_item())
        # Return the soup
        return html_soup

    def make_toc(self):
        """Creates a toc based on the headings, h1 to h6.
        """
        # BeautifulSoup 4 code
        soup = BeautifulSoup(self.html)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        toc_soup = BeautifulSoup()
        h2_tag = toc_soup.new_tag("h2")
        a_tag = toc_soup.new_tag("a")
        a_tag['href'] = "#top"
        a_tag.string = "Contents"
        h2_tag.append(a_tag)
        toc_soup.append(h2_tag)
        ul_tag = toc_soup.new_tag("ul")
        toc_soup.append(ul_tag)
        for heading in headings:
            li_tag = toc_soup.new_tag("li")
            li_tag['class'] = heading.name
            a_tag = toc_soup.new_tag("a")
            a_tag.string = heading.string
            a_tag['href'] = '#' + heading['id']
            li_tag.append(a_tag)
            ul_tag.append(li_tag)
        return str(toc_soup)


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
        # The location where the temporary downloaded image is saved on disk
        self.temp_img_filepath = None
        self.tags = data[u'tags']
        # The zotero tags
        if self.tags:
            self.tags = [tag.values()[0].encode('utf-8') for tag in self.tags]
        # cerate a url
        self.url = "https://api.zotero.org/groups/" + self.group_reader.group_id + \
            "/items/" + self.zid + "/file?key=" + self.group_reader.zot_key

    def download_image(self):
        """Downloads the image to a temporary location.
        """
        # Get the image
        if not self.temp_img_filepath:
            self.temp_img_filepath = self.group_reader.get_attachment_file(self.zid)

    def create_image_file(self, img_path_filename, width=None, height=None):
        """Resizes the image, and saves it in the '/img' folder.
        """
        info_str = "Creating image: " + \
            img_path_filename + ", " + str(width) + ", " + str(height) + ".\n"
        # Download the image
        self.download_image()
        # Resize the image using PIL
        info_str += "Resizing using PIL.\n"
        pil_img = Image.open(self.temp_img_filepath)
        img_w, img_h = pil_img.size
        size_1 = (img_w, img_h)
        size_2 = (img_w, img_h)
        if width and width < img_w:
            size_1 = (width, int((width/float(img_w)) * img_h))
        if height and height < img_h:
            size_2 = (int((height/float(img_h)) * img_w), height)
        if size_1[0] > size_2[0]:
            size = size_2
        else:
            size = size_1
        try:
            if size != (img_w, img_h):
                # This might fail if the PIL binary module called _imaging could not be loaded.
                pil_img_resized = pil_img.resize(size, Image.ANTIALIAS)
                # Save the image
                pil_img_resized.save(img_path_filename, quality=100)
            else:
                pil_img.save(img_path_filename, quality=100)
        except Exception:
            info_str += "Problem with PIL. Images could not be resized."
            info_str += "EXCEPTION: \n" + traceback.format_exc() + "\n"
        # Return the info string
        return info_str

# ================================================================================================
# Items from Zotero
# ================================================================================================

class Item(object):
    """Any type of paper. Superclass of ConferencePapaer and JournalPaper.
    """
    def __init__(self, uid, data):
        self.uid = uid
        self.authors = []
        self.title = data[u'title'].encode('utf-8')
        self.date = data[u'date'].encode('utf-8')[-4:]
        self.pages = data[u'pages'].encode('utf-8')
        self.abstract = data[u'abstractNote'].encode('utf-8')
        self.set_authors(data)
        self.sort_key = ""

    def check_keys(self, dictionary, keys):
        """ Check that the dict contains the list of keys.
        """
        for k in keys:
            if k not in dictionary.keys():
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

    def get_abstract_para(self):  # TODO: change to soup
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



class ResearchProject(Item):
    """A research project. The expected Zoter item is a Report.
    """
    def __init__(self, uid, data):
        super(ResearchProject, self).__init__(uid, data)
        self.place = data[u'place'].encode('utf-8')
        self.institution = data[u'institution'].encode('utf-8')
        self.type = data[u'reportType'].encode('utf-8')
        self.funding = data[u'rights'].encode('utf-8')
        self.project_number = data[u'reportNumber'].encode('utf-8')
        self.pi = "--"
        self.copis = "--"
        self.collabs = "--"
        self.duration = "--"

    def get_list_item(self): 
        """ Create a single li item.
        """
        soup = BeautifulSoup()
        li_tag = bs_create_tag(soup, soup, 'li')
        bs_create_tag(soup, li_tag, 'button', {'class':'toggle', 'target':'#'+self.uid})
        p_tag = bs_create_tag(soup, li_tag, 'p', {'class':'publication'})
        bs_create_tag(soup, p_tag, 'phtj-rp-title', attribs=None, string=self.title)
        bs_create_tag(soup, p_tag, 'phtj-rp-pi', attribs=None, string=self.pi)
        bs_create_tag(soup, p_tag, 'phtj-rp-copis', attribs=None, string=self.copis)
        bs_create_tag(soup, p_tag, 'phtj-rp-collabs', attribs=None, string=self.collabs)
        bs_create_tag(soup, p_tag, 'phtj-rp-duration', attribs=None, string=self.duration)
        bs_create_tag(soup, p_tag, 'phtj-rp-place', attribs=None, string=self.place)
        bs_create_tag(soup, p_tag, 'phtj-rp-institution', attribs=None, string=self.institution)
        bs_create_tag(soup, p_tag, 'phtj-rp-type', attribs=None, string=self.type)
        bs_create_tag(soup, p_tag, 'phtj-rp-funding', attribs=None, string=self.funding)
        bs_create_tag(soup, p_tag, 'phtj-rp-abstract', attribs=None, string=self.abstract)
        return soup


class ConferencePaper(Item):
    """ A conference paper. The expected zotero item type is a Conference Paper.
    """
    def __init__(self, uid, data):
        super(ConferencePaper, self).__init__(uid, data)
        self.conference = data[u'proceedingsTitle'].encode('utf-8')
        self.year = self.date[:-4]

    def get_list_item(self):  # TODO: change to soup
        author_str = "<button class='toggle' target='#"+self.uid+"'>+</button>"
        author_str += "<p class=publication>"
        author_str += "<pa>" + self.get_authors() + "</pa> "
        author_str += "<py>(" + self.year + ")</py> "
        author_str += "<pt>" + self.title + "</pt>, "
        author_str += "<pc>" + self.conference + "</pc>, "
        author_str += "<pp>pp. " + self.pages + "</pp>."
        author_str += "</p>"
        return "<li>" + author_str + "\n" + self.get_abstract_para() + "</li>\n"


class JournalPaper(Item):
    """A Journal paper. The expected zotero item type is a Journal Article.
    """
    def __init__(self, uid, data):
        super(JournalPaper, self).__init__(uid, data)
        self.journal = data[u'publicationTitle'].encode('utf-8')
        self.year = self.date[:-4]
        self.volume = data[u'volume'].encode('utf-8')
        self.issue = data[u'issue'].encode('utf-8')

    def get_list_item(self):  # TODO: change to soup
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

    def __init__(self, zot_id, zot_key):
        """Make the connection to a group.
        """
        # Login
        self.zot_id = zot_id
        self.zot_key = zot_key
        self.group_name = None
        self.group_id = None
        self.group_conn = None

    def initialize_conn_group_name(self, group_name):
        """Tries to create a connection with the zotero database.
        """
        info_str = "Creating connection with zotero database using user id.\n"
        self.group_name = group_name
        # Get the groups
        user_connection = zotero.Zotero(self.zot_id, 'user', self.zot_key)
        if not user_connection:
            info_str += "ERROR: Cannot connect to zotero user level database.\n"
            return info_str
        groups = user_connection.groups()
        # Find the right group
        group_id = None
        for group in groups:
            if group[u'name'] == group_name:
                group_id = group[u'group_id']
        if not group_id:
            info_str += "Can not find group '", group_name, "'\n"
            return info_str
        # Create a connection to that group
        info_str += self.initialize_conn_group_id(group_id)
        # Return the info
        return info_str

    def initialize_conn_group_id(self, group_id):
        """Tries to create a connection with the zotero database.
        """
        info_str = "Creating connection with zotero database using group id.\n"
        self.group_id = group_id
        # Create a connection to that group
        self.group_conn = zotero.Zotero(group_id, 'group', self.zot_key)
        if not self.group_conn:
            info_str += "ERROR: Cannot connect to zotero group level database.\n"
        # Return the info
        return info_str

    def get_group_items(self):
        """Return all items in this group
        """
        return self.group_conn.items()

    def get_group_colls(self):
        """Return all collections in this group
        """
        return self.group_conn.collections()

    def get_coll_id(self, coll_name):
        """Return the ID of a collection. If the name does not exist, raise an exception.
        """
        for coll in self.group_conn.collections():
            if coll[u'name'] == coll_name:
                return coll[u'collectionKey']
        raise Exception()

    def get_coll_items_by_name(self, coll_name, item_type=None, tag=None):
        """Return the items in a collection, giving the name of the collection.

        item_type can be Note, Attachment, ConferencePaper, JournalArticle, etc
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

def test_tabs():
    """Simple test for tabs.
    You need to make sure there is a sub-folder called "test".
    """
    print "Starting..."
    from zotero_auth import ZOT_ID, ZOT_KEY
    import templates
    CURR_DIR = os.path.dirname(os.path.abspath(__file__))
    group_reader = ZoteroGroupReader(ZOT_ID, ZOT_KEY)
    print group_reader.initialize_conn_group_name("Patrick Janssen Websites")
    twp = TabbedWebsite(group_reader, "Patrick Janssen")
    print twp.initialize_data(CURR_DIR + '/test')
    print twp.create_html_file(templates.HTML_TEMPLATE, CURR_DIR + "/test/index.html")
    print "Finished..."

def test_get_data():
    """Simple test for getting data from zotero.
    """
    print "Starting..."
    from zotero_auth import ZOT_ID, ZOT_KEY
    group_reader = ZoteroGroupReader(ZOT_ID, ZOT_KEY)
    print group_reader.initialize_conn_group_name("Patrick Janssen Websites")
    print "\nITEMS\n"
    for item in group_reader.get_group_items():
        print item, '\n'
    print "\nCOLLECTIONS\n"
    for coll in group_reader.get_group_colls():
        print coll, '\n'

    #print group_reader.get_coll_subs("Eddex")

if __name__ == "__main__":
    print "Running tests"
    test_tabs()
