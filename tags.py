#!/usr/bin/python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import sys, os, enum
import subprocess as sp

class Tmsu:
    def __init__(self, tmsu):
        self.tmsu = tmsu

    def info(self):
        try:
            r = self._cmd('info')
        except sp.CalledProcessError as e:
            if e.returncode == 1: # database doesn't exist
                return None
        lines = r.splitlines()
        def psplit(l): return map(lambda x: x.strip(), l.split(':'))
        d = dict(map(psplit, lines))

        return {'root': d['Root path'],
                'size': d['Size'],
                'database':d['Database']}

    def tags(self, fileName=None):
        """Returns a list of tags. If fileName is provided, list item is a tuple of
        (tagname, value) pair."""
        if fileName:
            # Note: tmsu behaves differently for 'tags' command when used
            # interactively and called from scripts. That's why we add '-n'.
            r = self._cmd('tags -n "{}"'.format(fileName))
            tag_value = []
            for tag in r.split(':')[1].split():
                tv = tag.split("=")
                if len(tv) > 1:
                    tag_value.append((tv[0], tv[1]))
                else:
                    tag_value.append((tv[0], ""))
            return tag_value
        else:
            return self._cmd('tags').splitlines()

    def tag(self, fileName, tagName):
        try:
            self._cmd('tag "{}" {}'.format(fileName, tagName))
            return True
        except sp.CalledProcessError as e:
            print("Failed to tag file.")
            return False

    def untag(self, fileName, tagName, value=None):
        try:
            self._cmd('untag "{}" {}{}'.format(fileName, tagName,
                                               "="+value if value else ""))
            return True
        except sp.CalledProcessError as e:
            print("Failed to untag file.")
            return False

    def _cmd(self, cmd):
        return sp.check_output('tmsu ' + cmd, shell=True).decode('utf-8')

    @staticmethod
    def findTmsu():
        import shutil
        tmsu =  shutil.which("tmsu")
        if tmsu:
            return Tmsu(tmsu)
        else:
            return None

@enum.unique
class TagCol(enum.IntEnum):
    TAGGED = 0
    NAME = 1
    VALUE = 2

class MyWindow(Gtk.Window):
    def __init__(self, tmsu, fileName):
        Gtk.Window.__init__(self, title="Tags")

        self.tmsu = tmsu
        self.fileName = fileName

        self.set_size_request(300, 400)
        self.vbox = Gtk.Box(parent = self,
                            orientation = Gtk.Orientation.VERTICAL)
        self.store = Gtk.ListStore(bool, str, str)
        self.list_widget = Gtk.TreeView(self.store)
        self.vbox.pack_start(self.list_widget, True, True, 0)

        # 'tagged' checkbox column
        cell = Gtk.CellRendererToggle()
        cell.connect("toggled", self.on_cell_toggled)
        col = Gtk.TreeViewColumn("", cell, active=TagCol.TAGGED)
        col.set_sort_column_id(TagCol.TAGGED)
        self.list_widget.append_column(col)

        # tag name column
        # TODO: ability to 'rename' tag
        col = Gtk.TreeViewColumn("Tag", Gtk.CellRendererText(editable=True),
                                 text=TagCol.NAME)
        col.set_expand(True)
        col.set_sort_column_id(TagCol.NAME)
        self.list_widget.append_column(col)

        # tag value column
        col = Gtk.TreeViewColumn("Value", Gtk.CellRendererText(editable=True),
                                 text=TagCol.VALUE)
        col.set_expand(True)
        col.set_sort_column_id(TagCol.VALUE)
        self.list_widget.append_column(col)

        hbox = Gtk.Box(orientation = Gtk.Orientation.HORIZONTAL)
        self.tag_edit = Gtk.Entry()
        self.tag_edit.connect('activate', self.on_add_clicked)
        completion = Gtk.EntryCompletion(model=self.store)
        completion.set_text_column(TagCol.NAME)
        completion.set_inline_completion(True)
        self.tag_edit.set_completion(completion)

        self.add_button = Gtk.Button(label = "Add")
        self.add_button.connect('clicked', self.on_add_clicked)
        hbox.pack_start(self.tag_edit, True, True, 0)
        hbox.pack_end(self.add_button, False, False, 0)
        self.vbox.pack_end(hbox, False, False, 0)

        self.loadTags()

    def on_cell_toggled(self, widget, path):
        tagName = self.store[path][TagCol.NAME]
        isTagged = self.store[path][TagCol.TAGGED]
        if not isTagged:
            r = self.tagFile(tagName)
        else:
            tagValue = self.store[path][TagCol.VALUE]
            r = self.untagFile(tagName, tagValue)

        # toggle
        if r:
            self.store[path][TagCol.TAGGED] = not self.store[path][TagCol.TAGGED]
            if isTagged: self.store[path][TagCol.VALUE] = ""

    def on_add_clicked(self, widget):
        tagName = self.tag_edit.get_text().strip()
        if len(tagName) == 0:
            self.displayError("Enter a tag name!")
            return

        tagRow = self.findTag(tagName)

        if tagRow and tagRow[TagCol.TAGGED]: # already tagged
            self.tag_edit.set_text("")
            return

        if self.tagFile(tagName):
            self.tag_edit.set_text("")
            if tagRow:              # tag already exists
                tagRow[TagCol.TAGGED] = True
            else:                   # new tag
                self.store.append([True, tagName])

    def findTag(self, tagName):
        """Find a tag in current listing."""
        for row in self.store:
            if row[TagCol.NAME] == tagName:
                return row
        return None

    def tagFile(self, tagName):
        """Tags a file and shows error message if fails."""
        if not self.tmsu.tag(self.fileName, tagName):
            self.displayError("Failed to tag file.")
            return False
        return True

    def untagFile(self, tagName, tagValue):
        """Untags a file and shows error message if fails."""
        if not self.tmsu.untag(self.fileName, tagName, tagValue):
            self.displayError("Failed to untag file.")
            return False
        return True

    def loadTags(self):
        """Loads tags for the first time."""
        allTags = self.tmsu.tags()
        fileTags = self.tmsu.tags(self.fileName)
        fileTagNames=[]
        for tag in fileTags:
            self.store.append([True, tag[0], tag[1]])
            fileTagNames.append(tag[0])
        for tag in allTags:
            if not tag in fileTagNames:
                self.store.append([False, tag, ""])

    def displayError(self, msg):
        """Display given error message in a message box."""
        dialog = Gtk.MessageDialog(
            self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE, msg)
        dialog.run()
        dialog.destroy()

if __name__ == "__main__":
    err = None
    tmsu = Tmsu.findTmsu()
    if not tmsu:
        err = "tmsu executable not found!"
    elif len(sys.argv) !=2:
        err = "Invalid arguments."
    else:
        fileName = sys.argv[1]
        os.chdir(os.path.dirname(fileName))
        if tmsu.info() == None:
            err = "No tmsu database is found."


    if err:
        dialog = Gtk.MessageDialog(
            None, 0, Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK, err)
        dialog.run()
    else:

        win = MyWindow(tmsu, sys.argv[1])
        win.connect('delete-event', Gtk.main_quit)
        win.show_all()
        Gtk.main()
