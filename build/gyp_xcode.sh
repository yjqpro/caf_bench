#!/bin/sh

export GYP_DEFINES="OS=ios"
export GYP_GENERATORS="ninja"

python gyp_chromium_ios.py --depth=.. ../ispreader_ios/ispreader_ios.gyp
