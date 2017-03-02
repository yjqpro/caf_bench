# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
{
  'targets': [
    {
      'target_name': 'some',
      'type': 'none',
      'dependencies': [
        # This file is intended to be locally modified. List the targets you use
        # regularly. The generated some.sln will contains projects for only
        # those targets and the targets they are transitively dependent on. This
        # can result in a solution that loads and unloads faster in Visual
        # Studio.
        #
        # Tip: Create a dummy CL to hold your local edits to this file, so they
        # don't accidentally get added to another CL that you are editing.
        #
        # Example:
        #'../base/base.gyp:base',
        #'../ios/content_controler/content_controler.gyp:*',
        #'../ios/content_controler/content_controler.gyp:content_controler',
        #'../t0_trader/t0_trader/t0_trader.gyp:*',
        '../caf_demo/caf_demo.gyp:*',
        #'../third_party/actor-framework/libcaf_io/libcaf_io.gyp:*',
        #'../third_party/hanz-2piny/hanz2piny/hanz2piny.gyp:*',
        #'../demo/demo.gyp:*',
        #'../lhscontent/lhscontent.gyp:*',
        #'../lhsnet/lhsnet.gyp:*',
        #'../lhscontent/lhscontent.gyp:*',
        #'../lhscontent/lhscontent.gyp:lhscontent_unittests',
        #'../third_party/websocketpp/websocketpp.gyp:*',
        #'../lhsnet_tester/lhsnet_tester.gyp:*',
        #'../lhscontent_demo/lhscontent_demo.gyp:*',
        #'../ispread/ispreader.gyp:*',
        #'../ios/content_controller_mfc_tester/content_controller_mfc_demo.gyp:*',
      ],
    },
  ],
}
