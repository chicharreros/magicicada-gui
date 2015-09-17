# -*- coding: utf-8 -*-

# Author: Natalia Bidart <nataliabidart@gmail.com>
#
# Copyright 2010-2011 Chicharreros
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""User Defined Folders UI."""

import logging

# pylint: disable=E0611
from gi.repository import Gtk
# pylint: enable=E0611

from twisted.internet import defer

from magicicada import syncdaemon
from magicicada.helpers import humanize_bytes
from magicicada.gui.gtk.helpers import Buildable

logger = logging.getLogger('magicicada.gui.gtk.volumes')

# pylint: disable=E0602

ADD_NEW_FOLDER = _(u'Add a new folder')
ARE_YOU_SURE = _(u'Are you sure?')
ARE_YOU_SURE_REMOVE_FOLDER = _(u'Are you sure you want to stop syncing '
                               u'the folder %s?')
ARE_YOU_SURE_REMOVE_FOLDER_SECONDARY_TEXT = _(
    u'You will not loose any local '
    u' data, but the contents of this folder will no longer be synced to/from '
    u' your cloud in any of your registered devices.'
)
ERROR_MESSAGE_MARKUP = u'<span foreground="red" font_weight="bold">%s</span>'
ERROR_MESSAGE = _(u'Oops! Something went wrong%(details)s')


class ListingDialog(Buildable, Gtk.Dialog):
    """A generic dialog to show info as a tree list."""

    data_fields = None  # list of tuples (field name, transformer function)
    default_size = (500, 400)
    filename = None  # .ui filename to load the inner widget from
    sd_attr = None  # name of the syncdaemon attribute to load the info from
    title = u''  # title of this Dialog
    logger = logger

    def __init__(self, syncdaemon_instance=None, builder=None, **kwargs):
        Buildable.__init__(self, builder=builder)

        assert self.root is not None
        assert self.store is not None
        assert self.view is not None

        flags = Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
        _kwargs = dict(
            flags=flags,
            buttons=((Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE))
        )
        Gtk.Dialog.__init__(self, **_kwargs)
        self.set_title(self.title)
        self.close_button = self.get_action_area().get_children()[0]

        kwargs = dict(parent=self,
                      flags=flags,
                      type=Gtk.MessageType.QUESTION,
                      buttons=Gtk.ButtonsType.YES_NO)
        self.confirm_dialog = Gtk.MessageDialog(**kwargs)
        self.confirm_dialog.set_title(ARE_YOU_SURE)

        self.warning_label = Gtk.Label()
        self.warning_label.set_selectable(True)
        self.warning_label.set_line_wrap(True)
        self.warning_label.show()
        self.get_content_area().pack_start(self.warning_label, expand=False,
                                           fill=True, padding=0)
        self.get_content_area().pack_start(self.root, expand=True,
                                           fill=True, padding=0)

        self.set_size_request(*self.default_size)

        if syncdaemon_instance is not None:
            self.sd = syncdaemon_instance
        else:
            self.sd = syncdaemon.SyncDaemon()
        self._sorting_order = {}
        self._make_view_sortable(self.view)

    def _make_view_sortable(self, view_name):
        """Set up view so columns are sortable."""
        store = self.store
        view = self.view
        self._sorting_order[store] = {}
        # this enforces that the order that columns will be shown and sorted
        # matches the order in the underlying model
        for i, col in enumerate(view.get_columns()):
            col.set_clickable(True)
            col.connect('clicked', self.on_store_sort_column_changed, i, store)
            self._sorting_order[store][i] = Gtk.SortType.ASCENDING

    def _value_toggled(self, path, column_id, column_value,
                       activate_op, deactivate_op):
        """Handle the toggling of a value."""
        tree_iter = self.store.get_iter_from_string(path)
        item_id = self.store.get_value(tree_iter, column_id)
        active = not self.store.get_value(tree_iter, column_value)
        if active:
            activate_op(item_id)
        else:
            deactivate_op(item_id)
        self.store.set(tree_iter, column_value, active)

    def on_store_sort_column_changed(self, column, col_index, store):
        """Store sort requested."""
        order = self._sorting_order[store][col_index]
        last_col = self._sorting_order[store].get('last_col')
        if last_col is not None:
            last_col.set_sort_indicator(False)

        store.set_sort_column_id(col_index, order)
        column.set_sort_indicator(True)
        column.set_sort_order(order)
        self._sorting_order[store]['last_col'] = column

        # change order
        if order == Gtk.SortType.ASCENDING:
            order = Gtk.SortType.DESCENDING
        else:
            order = Gtk.SortType.ASCENDING
        self._sorting_order[store][col_index] = order

    def load(self):
        """Populate store with info."""
        items = getattr(self.sd, self.sd_attr)
        if items is None:
            items = []

        self.store.clear()
        for item in items:
            row = []
            for field, transformer in self.data_fields:
                value = getattr(item, field)
                if transformer is not None:
                    value = transformer(value)
                row.append(value)
            self.store.append(row)

    def run(self):
        """Run this dialog."""
        self.load()
        Gtk.Dialog.run(self)

    def on_error(self, error):
        """An error ocurred."""
        msg = ERROR_MESSAGE % dict(details=u' (%s)' % error)
        self.warning_label.set_markup(ERROR_MESSAGE_MARKUP % msg)

    @defer.inlineCallbacks
    def call_async(self, operation, *args, **kwargs):
        """Call 'operation(*args, **kwargs)' while disabling the ui.

        The result of calling 'operation' is returned.

        All errors are catched and logged, and shown to the user as a red
        warning.

        """
        self.warning_label.set_text(u'')
        result = None
        self.set_sensitive(False)
        logger.debug('call_async: executing %r with args %r and %r',
                     operation.__name__, args, kwargs)
        try:
            result = yield operation(*args, **kwargs)
        except Exception, e:  # pylint: disable=W0703
            logger.exception('call_async: %r failed with:',
                             operation.__name__)
            self.on_error(e)
        self.load()
        self.set_sensitive(True)
        defer.returnValue(result)


class FoldersDialog(ListingDialog):
    """The list of operations over files/folders."""

    title = u'Folders'
    filename = 'folders.ui'
    sd_attr = 'folders'
    data_fields = ((u'suggested_path', None), (u'subscribed', None),
                   (u'volume', None))

    def __init__(self, *args, **kwargs):
        super(FoldersDialog, self).__init__(*args, **kwargs)
        self.remove_folder_button.set_sensitive(False)
        action_area = self.get_action_area()
        action_area.pack_start(self.add_folder_button, expand=True,
                               fill=True, padding=0)
        action_area.pack_start(self.remove_folder_button, expand=True,
                               fill=True, padding=0)
        action_area.reorder_child(self.close_button, 0)

        kwargs = dict(title=ADD_NEW_FOLDER, parent=None,
                      action=Gtk.FileChooserAction.SELECT_FOLDER,
                      buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                               Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT))
        self.file_chooser = Gtk.FileChooserDialog(**kwargs)

        self.sd.on_folder_op_error_callback = self.on_error

    def on_subscribed_renderer_toggled(self, renderer, path, *args, **kwargs):
        """The subscribed flag was toggled."""
        self._value_toggled(
            path, column_id=2, column_value=1,
            activate_op=self.sd.subscribe_folder,
            deactivate_op=self.sd.unsubscribe_folder)

    @defer.inlineCallbacks
    def on_add_folder_button_clicked(self, button, *args, **kwargs):
        """The add_folder button was clicked."""
        # open the file chooser
        response = self.file_chooser.run()
        self.file_chooser.hide()
        if response == Gtk.ResponseType.ACCEPT:
            path = self.file_chooser.get_filename()
            # validate path?
            yield self.call_async(self.sd.create_folder, path)

    def on_view_cursor_changed(self, view=None):
        """Enable the remove button if there's a row selected."""
        selection = self.view.get_selection()
        can_remove = selection.count_selected_rows() > 0
        self.remove_folder_button.set_sensitive(can_remove)

    @defer.inlineCallbacks
    def on_remove_folder_button_clicked(self, button, *args, **kwargs):
        """The remove_folder button was clicked."""
        selection = self.view.get_selection()
        model, tree_iter = selection.get_selected()
        path = model.get_value(tree_iter, 0)
        self.confirm_dialog.set_markup(ARE_YOU_SURE_REMOVE_FOLDER % path)
        msg = ARE_YOU_SURE_REMOVE_FOLDER_SECONDARY_TEXT
        self.confirm_dialog.format_secondary_text(msg)
        response = self.confirm_dialog.run()
        self.confirm_dialog.hide()

        if response == Gtk.ResponseType.YES:
            volume_id = model.get_value(tree_iter, 2)
            yield self.call_async(self.sd.delete_folder, volume_id)


class SharesToMeDialog(ListingDialog):
    """The list of shares to me."""

    humanize_string = \
        lambda bytes_str: humanize_bytes(int(bytes_str), precision=2)

    title = u'Shares to me'
    filename = 'shares_to_me.ui'
    sd_attr = u'shares_to_me'
    data_fields = ((u'name', None), (u'other_visible_name', None),
                   (u'accepted', None), (u'subscribed', None),
                   (u'access_level', None),
                   (u'free_bytes', humanize_string), (u'path', None),
                   (u'volume_id', None))

    def on_accepted_renderer_toggled(self, renderer, path, *args, **kwargs):
        """The accepted flag was toggled."""
        self._value_toggled(
            path, column_id=7, column_value=2,
            activate_op=self.sd.accept_share,
            deactivate_op=self.sd.reject_share)

    def on_subscribed_renderer_toggled(self, renderer, path, *args, **kwargs):
        """The subscribed flag was toggled."""
        self._value_toggled(
            path, column_id=7, column_value=3,
            activate_op=self.sd.subscribe_share,
            deactivate_op=self.sd.unsubscribe_share)


class SharesToOthersDialog(ListingDialog):
    """The list of shares to others."""

    title = u'Shares to others'
    filename = 'shares_to_others.ui'
    sd_attr = u'shares_to_others'
    data_fields = ((u'name', None), (u'other_visible_name', None),
                   (u'accepted', None), (u'access_level', None),
                   (u'path', None), (u'volume_id', None))


class PublicFilesDialog(ListingDialog):
    """The list of operations over files/folders."""

    title = u'Public files'
    filename = 'public_files.ui'
    sd_attr = u'public_files'
    data_fields = ((u'path', None), (u'public_url', None), (u'node', None))


class ListingButton(Gtk.ToolButton):
    """A toolbar button that lists some info."""

    dialog_class = None
    label = None
    stock_id = None

    def __init__(self, syncdaemon_instance=None, *args, **kwargs):
        Gtk.ToolButton.__init__(self, *args, **kwargs)
        self.connect('clicked', self.on_clicked)
        self.set_label(self.label)
        self.set_stock_id(self.stock_id)
        # self.dialog_class is not callable
        # pylint: disable=E1102
        if syncdaemon_instance is None:
            syncdaemon_instance = syncdaemon.SyncDaemon()
        self.dialog = self.dialog_class(syncdaemon_instance)
        self.show()

    def on_clicked(self, widget=None, data=None):
        """List user folders."""
        self.dialog.run()
        self.dialog.hide()


class FoldersButton(ListingButton):
    """The button to open the listing of folders."""

    dialog_class = FoldersDialog
    label = u'Folders'
    stock_id = u'gtk-directory'


class SharesToMeButton(ListingButton):
    """The button to open the listing of shares to me."""

    dialog_class = SharesToMeDialog
    label = u'Shares to Me'
    stock_id = u'gtk-network'


class SharesToOthersButton(ListingButton):
    """The button to open the listing of shares to others."""

    dialog_class = SharesToOthersDialog
    label = u'Shares to Others'
    stock_id = u'gtk-network'


class PublicFilesButton(ListingButton):
    """The button to open the listing of public files."""

    dialog_class = PublicFilesDialog
    label = u'Public Files'
    stock_id = u'gtk-file'
