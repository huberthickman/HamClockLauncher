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
from pathlib import Path
from queue import Queue, Empty


class HamClockLauncher(wx.Frame):
    # Backend server presets
    BACKEND_OHB = 'ohb'
    BACKEND_HAMCLOCK_COM = 'hamclock_com'
    BACKEND_CUSTOM = 'custom'

    BACKEND_HOSTS = {
        BACKEND_OHB: 'ohb.hamclock.app:80',
        BACKEND_HAMCLOCK_COM: 'hamclock.com:80',
    }

    def __init__(self):
        super().__init__(parent=None, title='HamClock Launcher', size=(800, 650))

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

        # Persistent config
        self.config = wx.Config('HamClockLauncher')

        self.create_menu_bar()
        self.init_ui()
        self.migrate_config_v13()
        self.load_config()
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

        # Tools menu
        tools_menu = wx.Menu()

        self.clear_cache_item = tools_menu.Append(wx.ID_ANY, 'Clear HamClock &Cache',
                                                   'Delete cached map, TLE, and other data files (preserves settings)')
        self.Bind(wx.EVT_MENU, self.on_clear_cache, self.clear_cache_item)

        menu_bar.Append(tools_menu, '&Tools')

        # Help menu
        help_menu = wx.Menu()

        user_guide_item = help_menu.Append(wx.ID_ANY, 'HamClock &User Guide', 'Open HamClock User Guide PDF')
        self.Bind(wx.EVT_MENU, self.on_user_guide, user_guide_item)

        release_notes_item = help_menu.Append(wx.ID_ANY, '&Release Notes', 'View release notes and version history')
        self.Bind(wx.EVT_MENU, self.on_release_notes, release_notes_item)

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

        # Backend server selection section
        backend_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Backend Server")
        backend_parent = backend_box.GetStaticBox()

        # Row 1: Open HamClock Backend (default)
        row1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_ohb = wx.RadioButton(backend_parent, label='Open HamClock Backend (ohb.hamclock.app:80)',
                                     style=wx.RB_GROUP)
        self.rb_ohb.SetValue(True)
        self.rb_ohb.Bind(wx.EVT_RADIOBUTTON, self.on_server_selected)
        row1_sizer.Add(self.rb_ohb, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        backend_box.Add(row1_sizer, 0, wx.ALL | wx.EXPAND, 2)

        # Row 2: hamclock.com
        row2_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_hamclock_com = wx.RadioButton(backend_parent, label='hamclock.com (hamclock.com:80)')
        self.rb_hamclock_com.SetValue(False)
        self.rb_hamclock_com.Bind(wx.EVT_RADIOBUTTON, self.on_server_selected)
        row2_sizer.Add(self.rb_hamclock_com, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        backend_box.Add(row2_sizer, 0, wx.ALL | wx.EXPAND, 2)

        # Row 3: Custom Open HamClock Backend radio button + host:port label + input
        row3_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.rb_custom = wx.RadioButton(backend_parent, label='Custom Open HamClock Backend')
        self.rb_custom.SetValue(False)
        self.rb_custom.Bind(wx.EVT_RADIOBUTTON, self.on_server_selected)
        row3_sizer.Add(self.rb_custom, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.host_label = wx.StaticText(backend_parent, label='Host:Port:')
        row3_sizer.Add(self.host_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.host_input = wx.TextCtrl(backend_parent, value='', size=(220, -1))
        self.host_input.SetHint('e.g. anopenhamclockserver.com:80')
        row3_sizer.Add(self.host_input, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        backend_box.Add(row3_sizer, 0, wx.ALL | wx.EXPAND, 2)

        # Start with Custom host:port controls disabled
        self.host_label.Enable(False)
        self.host_input.Enable(False)

        main_sizer.Add(backend_box, 0, wx.ALL | wx.EXPAND, 10)

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

    def set_backend_controls_enabled(self, enabled):
        """Enable or disable all backend server controls"""
        self.rb_ohb.Enable(enabled)
        self.rb_hamclock_com.Enable(enabled)
        self.rb_custom.Enable(enabled)
        # Host:port only enabled when Custom is selected AND not running
        if enabled and self.rb_custom.GetValue():
            self.host_label.Enable(True)
            self.host_input.Enable(True)
        else:
            self.host_label.Enable(False)
            self.host_input.Enable(False)

    def migrate_config_v13(self):
        """One-shot migration from 1.2 config schema to 1.3 schema.

        1.2 schema: use_openhamclock (bool), openhamclock_host_port (str)
        1.3 schema: backend_choice (str: 'ohb' | 'hamclock_com' | 'custom'),
                    openhamclock_host_port (str, only meaningful for 'custom')

        Runs exactly once, gated by the 'migrated_v13' flag. The old
        'use_openhamclock' key is left in place for safety.
        """
        if self.config.ReadBool('migrated_v13', defaultVal=False):
            return

        # If there's no prior config at all, just mark migration done
        # and let defaults apply via load_config.
        has_old_flag = self.config.HasEntry('use_openhamclock')
        has_host = self.config.HasEntry('openhamclock_host_port')

        if not has_old_flag and not has_host:
            self.config.WriteBool('migrated_v13', True)
            self.config.Flush()
            return

        old_use_ohc = self.config.ReadBool('use_openhamclock', defaultVal=False)
        old_host_port = self.config.Read('openhamclock_host_port', defaultVal='').strip()

        if not old_use_ohc:
            # Legacy Clear Sky Institute user → new default (OHB).
            # Leave openhamclock_host_port untouched.
            self.config.Write('backend_choice', self.BACKEND_OHB)
        else:
            # User was on an OpenHamClock host:port. Map presets to their
            # new radio buttons and clear the custom field for those;
            # anything else becomes 'custom' with the host:port preserved.
            if old_host_port == self.BACKEND_HOSTS[self.BACKEND_OHB]:
                self.config.Write('backend_choice', self.BACKEND_OHB)
                self.config.Write('openhamclock_host_port', '')
            elif old_host_port == self.BACKEND_HOSTS[self.BACKEND_HAMCLOCK_COM]:
                self.config.Write('backend_choice', self.BACKEND_HAMCLOCK_COM)
                self.config.Write('openhamclock_host_port', '')
            else:
                self.config.Write('backend_choice', self.BACKEND_CUSTOM)
                # Keep openhamclock_host_port as-is

        self.config.WriteBool('migrated_v13', True)
        self.config.Flush()

    def load_config(self):
        """Load saved server settings from wx.Config"""
        backend_choice = self.config.Read('backend_choice',
                                          defaultVal=self.BACKEND_OHB)
        host_port = self.config.Read('openhamclock_host_port', defaultVal='')

        # Guard against an unknown value in the stored config
        if backend_choice not in (self.BACKEND_OHB,
                                  self.BACKEND_HAMCLOCK_COM,
                                  self.BACKEND_CUSTOM):
            backend_choice = self.BACKEND_OHB

        self.rb_ohb.SetValue(backend_choice == self.BACKEND_OHB)
        self.rb_hamclock_com.SetValue(backend_choice == self.BACKEND_HAMCLOCK_COM)
        self.rb_custom.SetValue(backend_choice == self.BACKEND_CUSTOM)

        if host_port:
            self.host_input.SetValue(host_port)

        # Sync enabled state to loaded values
        is_custom = (backend_choice == self.BACKEND_CUSTOM)
        self.host_label.Enable(is_custom)
        self.host_input.Enable(is_custom)

    def save_config(self):
        """Save current server settings to wx.Config"""
        self.config.Write('backend_choice', self.get_backend_choice())
        self.config.Write('openhamclock_host_port', self.host_input.GetValue().strip())
        self.config.Flush()

    def get_backend_choice(self):
        """Return the currently selected backend choice constant"""
        if self.rb_ohb.GetValue():
            return self.BACKEND_OHB
        if self.rb_hamclock_com.GetValue():
            return self.BACKEND_HAMCLOCK_COM
        return self.BACKEND_CUSTOM

    def on_server_selected(self, event):
        """Handle backend server radio button selection"""
        is_custom = self.rb_custom.GetValue()
        self.host_label.Enable(is_custom)
        self.host_input.Enable(is_custom)
        # Retain whatever is in the host_input field when switching away
        # from Custom - do not clear it.
        if is_custom:
            self.host_input.SetFocus()

    def on_clear_cache(self, event):
        """Delete all cached files in ~/.hamclock except the eeprom settings file"""
        hamclock_dir = Path.home() / '.hamclock'

        if not hamclock_dir.is_dir():
            wx.MessageBox('No HamClock cache directory found.\n\n'
                          f'Expected: {hamclock_dir}',
                          'Nothing to Clear', wx.OK | wx.ICON_INFORMATION)
            return

        # Collect files to delete (everything except 'eeprom')
        files_to_delete = [f for f in hamclock_dir.iterdir()
                           if f.is_file() and f.name != 'eeprom']

        if not files_to_delete:
            wx.MessageBox('Cache is already empty (only the eeprom settings file remains).',
                          'Nothing to Clear', wx.OK | wx.ICON_INFORMATION)
            return

        # Confirm with the user
        response = wx.MessageBox(
            f'This will delete {len(files_to_delete)} cached file(s) from:\n'
            f'{hamclock_dir}\n\n'
            'Your HamClock settings (eeprom) will be preserved.\n\n'
            'HamClock will re-download these files on its next start.\n\n'
            'Continue?',
            'Clear HamClock Cache',
            wx.YES_NO | wx.ICON_QUESTION
        )

        if response != wx.YES:
            return

        deleted = 0
        errors = []
        for f in files_to_delete:
            try:
                f.unlink()
                deleted += 1
            except OSError as e:
                errors.append(f'{f.name}: {e}')

        # Report results
        if errors:
            wx.MessageBox(
                f'Deleted {deleted} file(s).\n\n'
                f'Failed to delete {len(errors)} file(s):\n' + '\n'.join(errors),
                'Cache Partially Cleared', wx.OK | wx.ICON_WARNING)
        else:
            wx.MessageBox(f'Successfully deleted {deleted} cached file(s).',
                          'Cache Cleared', wx.OK | wx.ICON_INFORMATION)

        self.append_output(f'\n=== Cleared HamClock cache: {deleted} file(s) deleted ===\n')

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

        # Resolve backend host:port from the selected radio button.
        # -b is always passed in 1.3; there is no longer a "no backend" default.
        backend_choice = self.get_backend_choice()
        if backend_choice == self.BACKEND_CUSTOM:
            host_port = self.host_input.GetValue().strip()
            if not host_port:
                wx.MessageBox('Please enter a Host:Port for the Custom Open HamClock Backend.\n\n'
                              'Example: anopenhamclockserver.com:80',
                              'Missing Host:Port', wx.OK | wx.ICON_WARNING)
                self.host_input.SetFocus()
                return
            if ':' not in host_port:
                wx.MessageBox('Host:Port must be in the format host:port\n\n'
                              'Example: anopenhamclockserver.com:80',
                              'Invalid Host:Port', wx.OK | wx.ICON_WARNING)
                self.host_input.SetFocus()
                return
            backend_host_port = host_port
        else:
            backend_host_port = self.BACKEND_HOSTS[backend_choice]

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
            # Build command: always pass -o and -b host:port
            cmd = [binary_path, '-o', '-b', backend_host_port]

            # Save config now that we have a valid, confirmed start
            self.save_config()

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                cwd=os.getcwd()
            )

            # Disable backend controls while running
            self.set_backend_controls_enabled(False)

            # Start reader thread
            self.reader_thread = threading.Thread(target=self.read_output, daemon=True)
            self.reader_thread.start()

            # Update UI
            self.start_btn.Enable(False)
            self.stop_btn.Enable(True)
            self.clear_cache_item.Enable(False)

            if backend_choice == self.BACKEND_OHB:
                server_label = 'Open HamClock Backend'
            elif backend_choice == self.BACKEND_HAMCLOCK_COM:
                server_label = 'hamclock.com'
            else:
                server_label = f'Custom ({backend_host_port})'
            self.status_text.SetLabel(f'Status: Running {binary_name} [{server_label}]')

            cmd_display = ' '.join(cmd)
            self.append_output(f'=== Started {binary_name} (PID {self.process.pid}) ===\n')
            self.append_output(f'=== Command: {cmd_display} ===\n')

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
            self.set_backend_controls_enabled(True)
            self.clear_cache_item.Enable(True)

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
        """Open the bundled HamClockKey.pdf in the user's default PDF viewer"""
        # Look for HamClockKey.pdf next to the executable, then next to the script
        pdf_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'HamClockKey.pdf')
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'HamClockKey.pdf')

        if not os.path.exists(pdf_path):
            wx.MessageBox('HamClockKey.pdf not found.', 'Not Found', wx.OK | wx.ICON_INFORMATION)
            return

        try:
            # Use macOS `open` so the user's default PDF viewer handles it
            subprocess.run(['open', pdf_path], check=True)
        except Exception as e:
            wx.MessageBox(f'Error opening user guide: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)

    def on_release_notes(self, event):
        """Open release_notes.html in the user's default browser"""
        # Look for release_notes.html next to the executable, then next to the script
        rn_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'release_notes.html')
        if not os.path.exists(rn_path):
            rn_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'release_notes.html')

        if os.path.exists(rn_path):
            try:
                webbrowser.open('file://'+rn_path)
            except Exception as e:
                wx.MessageBox(f'Could not open release notes: {str(e)}', 'Error', wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox('release_notes.html not found.', 'Not Found', wx.OK | wx.ICON_INFORMATION)

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

Copyright (c) 2025-2026 Hubert Hickman

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
        <p><b>Version:</b> 1.3</p>
        <p><b>Developer:</b> Hubert Hickman<br>
        <b>Email:</b> hubert.hickman@gmail.com</p>

        <p>A wxPython launcher for HamClock</p>

        <p><b>HamClock Website:</b> <a href="https://github.com/openhamclock/hamclock">
        https://github.com/openhamclock/hamclock</a></p>

        <hr>

        <h3>HamClock Launcher License</h3>
        <pre>{launcher_license}</pre>

        <hr>

        <h3>HamClock License</h3>
        <pre>{hamclock_license}</pre>

        <hr>

        <p><i>HamClock was originally developed by Elwood Charles Downey (SK, 2020&ndash;2025) and is now maintained by Dave Koberstein.</i></p>

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
        self.set_backend_controls_enabled(True)
        self.clear_cache_item.Enable(True)

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
    app = HamClockApp()
    app.MainLoop()


class HamClockApp(wx.App):
    def OnInit(self):
        self.SetAppName("HamClockLauncher")
        frame = HamClockLauncher()
        frame.Show()
        return True


if __name__ == '__main__':
    main()