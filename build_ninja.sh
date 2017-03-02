#!/bin/bash

#export GYP_DEFINES="OS=ios chromium_ios_signing=0 clang_xcode=1 use_system_libcxx=1 target_subarch=both enable_protobuf_log=0"
#export GYP_DEFINES="OS=ios chromium_ios_signing=0 clang_xcode=1 use_system_libcxx=1"
#export GYP_DEFINES="OS=ios chromium_ios_signing=0 clang_xcode=1"
export GYP_GENERATORS=ninja
python build/gyp_win.py --depth=. --no-circular-check -Ibuild\common.gypi geek_quant\geek_quant.gyp
