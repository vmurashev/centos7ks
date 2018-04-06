from __future__ import print_function
import atexit
import urwid
import os.path
import signal
import subprocess
import sys


TEXT_MAIN_CAPTION = 'CentOS-7 initial setup'
TEXT_OPERATION_IS_PROGRESS = 'Please wait, operation is in progress ...'
TEXT_OPERATION_DONE = "Done, press 'ESC' to exit"


class AppDisplay(urwid.WidgetPlaceholder):
    def __init__(self, py_script):
        title = TEXT_MAIN_CAPTION
        self.done = False
        self.term = urwid.Terminal([sys.executable, '-u', py_script])
        self.status_bar = urwid.Text(TEXT_OPERATION_IS_PROGRESS)
        self.view = urwid.LineBox(urwid.Frame(self.term, footer=self.status_bar), title=title)

        urwid.WidgetPlaceholder.__init__(self, self.view)

    def on_done(self, *args):
        self.done = True
        self.status_bar.set_text(TEXT_OPERATION_DONE)

    def main(self):
        loop = urwid.MainLoop(self)
        self.term.main_loop = loop
        urwid.connect_signal(self.term, 'closed', self.on_done)
        loop.run()

    def keypress(self, size, key):
        if key == 'esc':
            if self.done:
                raise urwid.ExitMainLoop()
        else:
            return self.__super.keypress(size, key)


def clear_screen():
    print('\x1b\x5b\x33\x4a\x1b\x5b\x48\x1b\x5b\x32\x4a')


def main(py_script):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if not '--debug' in sys.argv:
        atexit.register(clear_screen)
    try:
        AppDisplay(py_script).main()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main(sys.argv[1])
