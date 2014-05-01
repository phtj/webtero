#!/usr/local/bin/python2.7

#HTML templates

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>$title</title>
    <script src="js/jquery-1.11.0.min.js"></script>
    <script src="js/jquery-ui-1.10.4.custom.min.js"></script>
    <script src="js/webtero.js"></script>
    <link rel="stylesheet" type="text/css" href="css/webtero.css">
</head>
<body>
    <div id="content">
        <select id="website-selector">
            <option value="http://www.patrick.janssen.name">Patrick Janssen</option>
            <option value="http://lab.patrick.janssen.name/">Research: Design Automation Lab</option>
            <option value="http://students.patrick.janssen.name">Teaching: Urban Reboot Studio</option>
            <option value="http://eddex.evo-devo-design.net">Software: Eddex</option>
            <option value="http://houdarcs.evo-devo-design.net">Software: Houdarcs</option>
            <option value="http://vidamo.evo-devo-design.net">Software: Vidamo</option>
            <option value="http://dexen.evo-devo-design.net">Software: Dexen</option>

        </select>
        <div id="header"><h1>$title</h1></div>
            <div id="tabs-area">
                    <div id="tabs-buttons">
                        <ul>
                            $tabs_buttons
                        </ul>
                    </div> <!-- tabs-buttons -->
                    <div id="tabs-content">
                        $tabs_content
                    </div> <!-- tabs-content -->
            </div> <!-- tabs-area -->
        <div id="footer"><a href='http://webtero.evo-devo-design.net/'>Auto-generated from Zotero database. </a> Patrick Janssen (c) 2008</div>
    </div> <!-- content -->
</body>
</html>
""".encode('UTF-8')
