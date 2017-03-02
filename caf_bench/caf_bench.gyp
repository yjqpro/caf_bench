{
  'targets' : [
    {
      'target_name' : 'scheduling',
      'type' : 'executable',
      'variables' : {
      },
      'sources' : [
        './scheduling.cpp',
      ],
      'dependencies' : [
        '../third_party/actor-framework/libcaf_io/libcaf_io.gyp:*',
      ],
      'defines' : [
      ],
      'includes' : [
      ],
      'include_dirs' : [
      ],
    },
  ]
}
