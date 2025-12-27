#!/usr/bin/env python3
"""
HamClock Launcher - A wxPython GUI for launching and monitoring hamclock binaries
"""

import wx
import subprocess
import threading
import os
import sys
from queue import Queue, Empty


class HamClockLauncher(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='HamClock Launcher', size=(800, 600))

        self.process = None
        self.output_queue = Queue()
        self.reader_thread = None
        self.max_lines = 5000  # Maximum lines in output window

        # Available hamclock binaries
        self.binaries = [
            'hamclock-web-800x480',
            'hamclock-web-1600x960',
            'hamclock-web-2400x1440',
            'hamclock-web-3200x1920'
        ]

        self.create_menu_bar()
        self.init_ui()
        self.Centre()

        # Timer to check for output updates
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.timer.Start(100)  # Check every 100ms

        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def create_menu_bar(self):
        """Create the menu bar"""
        menu_bar = wx.MenuBar()

        # Edit menu
        edit_menu = wx.Menu()

        copy_item = edit_menu.Append(wx.ID_COPY, '&Copy\tCtrl+C', 'Copy selected text')
        self.Bind(wx.EVT_MENU, self.on_copy, copy_item)

        select_all_item = edit_menu.Append(wx.ID_SELECTALL, 'Select &All\tCtrl+A', 'Select all text')
        self.Bind(wx.EVT_MENU, self.on_select_all, select_all_item)

        menu_bar.Append(edit_menu, '&Edit')

        self.SetMenuBar(menu_bar)

    def init_ui(self):
        """Initialize the user interface"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Selection section
        selection_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Select HamClock Version")

        self.radio_buttons = []
        for binary in self.binaries:
            rb = wx.RadioButton(selection_box.GetStaticBox(), label=binary,
                                style=wx.RB_GROUP if binary == self.binaries[0] else 0)
            self.radio_buttons.append(rb)
            selection_box.Add(rb, 0, wx.ALL, 5)

        main_sizer.Add(selection_box, 0, wx.ALL | wx.EXPAND, 10)

        # Control buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.start_btn = wx.Button(panel, label='Start HamClock')
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start)
        button_sizer.Add(self.start_btn, 0, wx.ALL, 5)

        self.stop_btn = wx.Button(panel, label='Stop HamClock')
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        self.stop_btn.Enable(False)
        button_sizer.Add(self.stop_btn, 0, wx.ALL, 5)

        self.clear_btn = wx.Button(panel, label='Clear Output')
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        button_sizer.Add(self.clear_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.CENTER, 5)

        # Status text
        self.status_text = wx.StaticText(panel, label='Status: Ready')
        main_sizer.Add(self.status_text, 0, wx.ALL | wx.EXPAND, 10)

        # Output display
        output_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "HamClock Output")

        self.output_ctrl = wx.TextCtrl(output_box.GetStaticBox(),
                                       style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.output_ctrl.SetFont(font)

        output_box.Add(self.output_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(output_box, 1, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(main_sizer)

    def get_selected_binary(self):
        """Get the selected binary name"""
        for i, rb in enumerate(self.radio_buttons):
            if rb.GetValue():
                return self.binaries[i]
        return self.binaries[0]

    def on_start(self, event):
        """Start the hamclock process"""
        if self.process and self.process.poll() is None:
            wx.MessageBox('HamClock is already running!', 'Warning', wx.OK | wx.ICON_WARNING)
            return

        binary_name = self.get_selected_binary()
        binary_path = os.path.join('hamclock_bin', binary_name)

        # Check if binary exists
        if not os.path.exists(binary_path):
            wx.MessageBox(
                f'Binary not found: {binary_path}\n\nPlease ensure the hamclock_bin directory exists with the binaries.',
                'Error', wx.OK | wx.ICON_ERROR)
            return

        # Check if binary is executable
        if not os.access(binary_path, os.X_OK):
            wx.MessageBox(f'Binary is not executable: {binary_path}\n\nYou may need to run: chmod +x {binary_path}',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        try:
            # Start the process with -o option
            self.process = subprocess.Popen(
                [binary_path, '-o'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                cwd=os.getcwd()
            )

            # Start reader thread
            self.reader_thread = threading.Thread(target=self.read_output, daemon=True)
            self.reader_thread.start()

            # Update UI
            self.start_btn.Enable(False)
            self.stop_btn.Enable(True)
            self.status_text.SetLabel(f'Status: Running {binary_name}')
            self.append_output(f'=== Started {binary_name} with PID {self.process.pid} ===\n')

        except Exception as e:
            wx.MessageBox(f'Error starting HamClock: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

    def on_stop(self, event):
        """Stop the hamclock process"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

            self.append_output('\n=== HamClock stopped ===\n')
            self.status_text.SetLabel('Status: Stopped')
            self.start_btn.Enable(True)
            self.stop_btn.Enable(False)

    def on_clear(self, event):
        """Clear the output display"""
        self.output_ctrl.Clear()

    def on_copy(self, event):
        """Copy selected text to clipboard"""
        self.output_ctrl.Copy()

    def on_select_all(self, event):
        """Select all text in output window"""
        self.output_ctrl.SetSelection(-1, -1)

    def read_output(self):
        """Read output from the process (runs in separate thread)"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.output_queue.put(line)
        except Exception as e:
            self.output_queue.put(f'[Error reading output: {str(e)}]\n')
        finally:
            # Process has ended
            if self.process:
                self.process.stdout.close()
                returncode = self.process.wait()
                self.output_queue.put(f'\n=== Process exited with code {returncode} ===\n')
                self.output_queue.put('PROCESS_ENDED')

    def on_timer(self, event):
        """Check for new output and update the display"""
        updated = False
        while True:
            try:
                line = self.output_queue.get_nowait()
                if line == 'PROCESS_ENDED':
                    wx.CallAfter(self.on_process_ended)
                    break
                else:
                    self.append_output(line)
                    updated = True
            except Empty:
                break

        # Auto-scroll to bottom if updated
        if updated:
            self.output_ctrl.SetInsertionPointEnd()

    def on_process_ended(self):
        """Handle process ending naturally"""
        self.status_text.SetLabel('Status: Process ended')
        self.start_btn.Enable(True)
        self.stop_btn.Enable(False)

    def append_output(self, text):
        """Append text to the output control and limit to max_lines"""
        self.output_ctrl.AppendText(text)

        # Check if we need to trim old lines
        num_lines = self.output_ctrl.GetNumberOfLines()
        if num_lines > self.max_lines:
            # Calculate how many lines to remove
            lines_to_remove = num_lines - self.max_lines

            # Find the position of the end of the line we want to remove up to
            pos = 0
            for i in range(lines_to_remove):
                pos = self.output_ctrl.XYToPosition(0, i)

            # Get position of end of last line to remove
            end_pos = self.output_ctrl.XYToPosition(0, lines_to_remove)

            # Remove the old lines
            self.output_ctrl.Remove(0, end_pos)

    def on_close(self, event):
        """Handle window close event"""
        # Stop the timer
        self.timer.Stop()

        # Terminate the process if running
        if self.process and self.process.poll() is None:
            response = wx.MessageBox(
                'HamClock is still running. Do you want to stop it and exit?',
                'Confirm Exit',
                wx.YES_NO | wx.ICON_QUESTION
            )
            if response == wx.YES:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            else:
                return

        self.Destroy()


def main():
    app = wx.App()
    frame = HamClockLauncher()
    frame.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()