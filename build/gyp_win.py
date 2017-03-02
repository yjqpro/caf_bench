# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script is wrapper for Chromium that adds some support for how GYP
is invoked by Chromium beyond what can be done in the gclient hooks.
"""

import argparse
import gc
import glob
import gyp_environment
import os
import re
import shlex
import subprocess
import string
import sys
import vs_toolchain

script_dir = os.path.dirname(os.path.realpath(__file__))
chrome_src = os.path.abspath(os.path.join(script_dir, os.pardir))

sys.path.insert(0, os.path.join(chrome_src, 'tools', 'gyp', 'pylib'))
import gyp

def main():
  args = sys.argv[1:]
  gyp_rc = gyp.main(args)

  sys.exit(gyp_rc)

if __name__ == '__main__':
  sys.exit(main())
