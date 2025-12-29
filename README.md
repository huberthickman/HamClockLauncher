# HamClock Launcher

A wxPython-based GUI launcher for [HamClock](https://www.clearskyinstitute.com/ham/HamClock/), providing an easy-to-use interface for running and monitoring HamClock web applications.  It is distributed as a self-contained .app, this requiring no installation of any software to use the HamClock.

![HamClockLauncher](readme_images/HamClockLauncher.png)

## Overview

HamClock Launcher is a macos desktop application that simplifies launching and managing HamClock instances. It captures and displays HamClock's output in real-time, making it easy to monitor the application's status and debug any issues.

## Features

- **Easy Version Selection**: Choose from four HamClock display resolutions via a simple radio button interface:
  - 800x480
  - 1600x960
  - 2400x1440
  - 3200x1920

- **Real-time Output Monitoring**: View HamClock's stdout output as it runs
- **Output Management**: 
  - Automatic line limiting (5000 lines max) to prevent memory issues
  - Clear output button
  - Copy and select all functionality via Edit menu
- **Browser Integration**: One-click button to open HamClock in your default web browser
- **Process Control**: Start and stop HamClock with visual status indicators
- **Safe Shutdown**: Prompts before closing if HamClock is still running
- **Help Resources**: Quick access to HamClock User Guide PDF from the Help menu



## License

This project is licensed under the MIT License.

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
SOFTWARE.

## About HamClock

HamClock is developed by Elwood Downey and is available at:
https://www.clearskyinstitute.com/ham/HamClock/

HamClock is licensed under the MIT License. See the LICENSE file in the `hamclock_bin` directory for details.

#
## Acknowledgments

- Thanks to Elwood Downey for creating the HamClock software - and to having it available to the amateur radio community.  
- HamClockLauncher uses the cross-platform GUI library [wxPython](https://www.wxpython.org/)
