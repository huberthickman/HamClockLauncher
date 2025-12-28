#!/usr/bin/env python3
"""
HamClock Launcher - A wxPython GUI for launching and monitoring hamclock binaries
"""

import wx
import wx.html
import subprocess
import threading
import os
import sys
import webbrowser
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

        # Bind the macOS Quit menu item (automatically added by macOS)
        self.Bind(wx.EVT_MENU, self.on_close, id=wx.ID_EXIT)

        # Edit menu
        edit_menu = wx.Menu()

        copy_item = edit_menu.Append(wx.ID_COPY, '&Copy\tCtrl+C', 'Copy selected text')
        self.Bind(wx.EVT_MENU, self.on_copy, copy_item)

        select_all_item = edit_menu.Append(wx.ID_SELECTALL, 'Select &All\tCtrl+A', 'Select all text')
        self.Bind(wx.EVT_MENU, self.on_select_all, select_all_item)

        menu_bar.Append(edit_menu, '&Edit')

        # Help menu
        help_menu = wx.Menu()

        user_guide_item = help_menu.Append(wx.ID_ANY, 'HamClock &User Guide', 'Open HamClock User Guide PDF')
        self.Bind(wx.EVT_MENU, self.on_user_guide, user_guide_item)

        help_menu.AppendSeparator()

        about_item = help_menu.Append(wx.ID_ABOUT, '&About', 'About HamClock Launcher')
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

        menu_bar.Append(help_menu, '&Help')

        self.SetMenuBar(menu_bar)

    def init_ui(self):
        """Initialize the user interface"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Selection section
        selection_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Select HamClock Version")

        # Create a 2x2 grid for radio buttons
        grid_sizer = wx.GridSizer(rows=2, cols=2, hgap=10, vgap=10)

        self.radio_buttons = []
        for i, binary in enumerate(self.binaries):
            rb = wx.RadioButton(selection_box.GetStaticBox(), label=binary,
                                style=wx.RB_GROUP if i == 0 else 0)
            rb.SetValue(False)  # Start with no selection
            rb.Bind(wx.EVT_RADIOBUTTON, self.on_radio_selected)
            self.radio_buttons.append(rb)
            grid_sizer.Add(rb, 0, wx.ALL, 5)

        selection_box.Add(grid_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(selection_box, 0, wx.ALL | wx.EXPAND, 10)

        # Control buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.start_btn = wx.Button(panel, label='Start HamClock')
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start)
        self.start_btn.Enable(False)  # Disabled until version is selected
        button_sizer.Add(self.start_btn, 0, wx.ALL, 5)

        self.stop_btn = wx.Button(panel, label='Stop HamClock')
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        self.stop_btn.Enable(False)
        button_sizer.Add(self.stop_btn, 0, wx.ALL, 5)

        self.browser_btn = wx.Button(panel, label='Open in Browser')
        self.browser_btn.Bind(wx.EVT_BUTTON, self.on_open_browser)
        button_sizer.Add(self.browser_btn, 0, wx.ALL, 5)

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
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.output_ctrl.SetFont(font)

        output_box.Add(self.output_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(output_box, 1, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(main_sizer)

    def get_selected_binary(self):
        """Get the selected binary name"""
        for i, rb in enumerate(self.radio_buttons):
            if rb.GetValue():
                return self.binaries[i]
        return None

    def on_radio_selected(self, event):
        """Handle radio button selection"""
        # Enable Start button when a version is selected
        if not self.process or self.process.poll() is not None:
            self.start_btn.Enable(True)

    def on_start(self, event):
        """Start the hamclock process"""
        if self.process and self.process.poll() is None:
            wx.MessageBox('HamClock is already running!', 'Warning', wx.OK | wx.ICON_WARNING)
            return

        binary_name = self.get_selected_binary()
        if binary_name is None:
            wx.MessageBox('Please select a HamClock version first!', 'Warning', wx.OK | wx.ICON_WARNING)
            return

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

    def on_open_browser(self, event):
        """Open HamClock in the default web browser"""
        url = "http://localhost:8081/live.html"
        try:
            webbrowser.open(url)
            self.append_output(f'\n=== Opened browser to {url} ===\n')
        except Exception as e:
            wx.MessageBox(f'Error opening browser: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

    def on_copy(self, event):
        """Copy selected text to clipboard"""
        self.output_ctrl.Copy()

    def on_select_all(self, event):
        """Select all text in output window"""
        self.output_ctrl.SetSelection(-1, -1)

    def on_user_guide(self, event):
        """Open HamClock User Guide in browser"""
        url = "https://www.clearskyinstitute.com/ham/HamClock/HamClockKey.pdf"
        try:
            webbrowser.open(url)
        except Exception as e:
            wx.MessageBox(f'Error opening user guide: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

    def on_about(self, event):
        """Display About dialog"""
        # Read HamClock LICENSE file if it exists
        hamclock_license = ""
        license_path = os.path.join('hamclock_bin', 'LICENSE')
        if os.path.exists(license_path):
            try:
                with open(license_path, 'r') as f:
                    hamclock_license = f.read()
            except Exception as e:
                hamclock_license = f"[Could not read LICENSE file: {str(e)}]"
        else:
            hamclock_license = "[LICENSE file not found in hamclock_bin directory]"

        # Launcher MIT License
        launcher_license = """MIT License

Copyright (c) 2025 Hubert Hickman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

        # Create HTML content
        html_content = f"""
        <html>
        <body>
        <h2>HamClock Launcher</h2>
        <p><b>Version:</b> 1.0</p>
        <p><b>Developer:</b> Hubert Hickman<br>
        <b>Email:</b> hubert.hickman@gmail.com</p>

        <p>A wxPython launcher for HamClock</p>

        <p><b>HamClock Website:</b> <a href="https://www.clearskyinstitute.com/ham/HamClock/">
        https://www.clearskyinstitute.com/ham/HamClock/</a></p>

        <hr>

        <h3>HamClock Launcher License</h3>
        <pre>{launcher_license}</pre>

        <hr>

        <h3>HamClock License</h3>
        <pre>{hamclock_license}</pre>

        <hr>

        <p><i>HamClock is developed by Elwood Downey</i></p>

        </body>
        </html>
        """

        # Create dialog with HTML window
        dlg = wx.Dialog(self, title="About HamClock Launcher", size=(700, 600))

        html = wx.html.HtmlWindow(dlg)
        html.SetPage(html_content)

        # Create OK button
        ok_btn = wx.Button(dlg, wx.ID_OK, "OK")

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(html, 1, wx.EXPAND | wx.ALL, 10)
        sizer.Add(ok_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        dlg.SetSizer(sizer)
        dlg.ShowModal()
        dlg.Destroy()

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