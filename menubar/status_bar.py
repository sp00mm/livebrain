import os
from typing import Callable, Optional

from AppKit import (
    NSStatusBar, NSVariableStatusItemLength, NSImage,
    NSMenu, NSMenuItem, NSApp, NSLeftMouseUpMask,
    NSRightMouseUpMask
)
from Foundation import NSObject
from objc import super as objc_super

NSEVENT_RIGHT_MOUSE_UP = 3


class StatusBarDelegate(NSObject):
    def initWithCallbacks_quit_(self, on_click: Callable, on_quit: Callable):
        self = objc_super(StatusBarDelegate, self).init()
        if self is None:
            return None
        self._on_click = on_click
        self._on_quit = on_quit
        self._quit_menu = None
        return self

    def statusItemClicked_(self, sender):
        event = NSApp.currentEvent()
        if event and event.type() == NSEVENT_RIGHT_MOUSE_UP:
            self._show_quit_menu(sender)
        else:
            self._on_click()

    def _show_quit_menu(self, sender):
        if not self._quit_menu:
            self._quit_menu = NSMenu.alloc().init()
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                'Quit LiveBrain', 'quitClicked:', 'q'
            )
            quit_item.setTarget_(self)
            self._quit_menu.addItem_(quit_item)

        button = sender
        self._quit_menu.popUpMenuPositioningItem_atLocation_inView_(
            None, button.bounds().origin, button
        )

    def quitClicked_(self, sender):
        self._on_quit()


class StatusBarController:
    def __init__(self, on_click: Callable, on_quit: Callable):
        self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )

        self._delegate = StatusBarDelegate.alloc().initWithCallbacks_quit_(on_click, on_quit)

        button = self._status_item.button()
        button.setAction_('statusItemClicked:')
        button.setTarget_(self._delegate)
        button.sendActionOn_(NSLeftMouseUpMask | NSRightMouseUpMask)

        self._load_icons()
        self._set_icon(self._icon_normal)
        self._recording = False

    def _load_icons(self):
        resources_dir = os.path.join(os.path.dirname(__file__), '..', 'resources')

        icon_path = os.path.join(resources_dir, 'icon.png')
        icon_recording_path = os.path.join(resources_dir, 'icon_recording.png')

        self._icon_normal = self._load_template_image(icon_path)
        self._icon_recording = self._load_template_image(icon_recording_path, is_template=False)

    def _load_template_image(self, path: str, is_template: bool = True) -> Optional[NSImage]:
        if not os.path.exists(path):
            return None
        image = NSImage.alloc().initWithContentsOfFile_(path)
        if image:
            image.setSize_((18, 18))
            image.setTemplate_(is_template)
        return image

    def _set_icon(self, image: Optional[NSImage]):
        button = self._status_item.button()
        if image:
            button.setImage_(image)
            button.setTitle_('')
        else:
            button.setTitle_('🧠')
            button.setImage_(None)

    def set_recording(self, recording: bool):
        self._recording = recording
        if recording and self._icon_recording:
            self._set_icon(self._icon_recording)
        else:
            self._set_icon(self._icon_normal)

    def get_button_frame(self):
        button = self._status_item.button()
        window = button.window()
        if window:
            return window.frame()
        return None
