# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run specific test on specific environment."""

import json
import logging
import os
import re
import shutil
import string
import tempfile
import time
import zipfile


from pylib.base import base_test_result
from pylib.base import test_run
from pylib.remote.device import appurify_constants
from pylib.remote.device import appurify_sanitized
from pylib.remote.device import remote_device_helper
from pylib.utils import zip_utils

_DEVICE_OFFLINE_RE = re.compile('error: device not found')
_LONG_MSG_RE = re.compile('longMsg=')
_SHORT_MSG_RE = re.compile('shortMsg=')


class RemoteDeviceTestRun(test_run.TestRun):
  """Run tests on a remote device."""

  _TEST_RUN_KEY = 'test_run'
  _TEST_RUN_ID_KEY = 'test_run_id'

  WAIT_TIME = 5
  COMPLETE = 'complete'
  HEARTBEAT_INTERVAL = 300

  def __init__(self, env, test_instance):
    """Constructor.

    Args:
      env: Environment the tests will run in.
      test_instance: The test that will be run.
    """
    super(RemoteDeviceTestRun, self).__init__(env, test_instance)
    self._env = env
    self._test_instance = test_instance
    self._app_id = ''
    self._test_id = ''
    self._results = ''
    self._test_run_id = ''
    self._results_temp_dir = None

  #override
  def SetUp(self):
    """Set up a test run."""
    if self._env.trigger:
      self._TriggerSetUp()
    elif self._env.collect:
      assert isinstance(self._env.collect, basestring), (
                        'File for storing test_run_id must be a string.')
      with open(self._env.collect, 'r') as persisted_data_file:
        persisted_data = json.loads(persisted_data_file.read())
        self._env.LoadFrom(persisted_data)
        self.LoadFrom(persisted_data)

  def _TriggerSetUp(self):
    """Set up the triggering of a test run."""
    raise NotImplementedError

  #override
  def RunTests(self):
    """Run the test."""
    if self._env.trigger:
      with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                              logging.WARNING):
        test_start_res = appurify_sanitized.api.tests_run(
            self._env.token, self._env.device_type_id, self._app_id,
            self._test_id)
      remote_device_helper.TestHttpResponse(
        test_start_res, 'Unable to run test.')
      self._test_run_id = test_start_res.json()['response']['test_run_id']
      logging.info('Test run id: %s' % self._test_run_id)

    if self._env.collect:
      current_status = ''
      timeout_counter = 0
      heartbeat_counter = 0
      while self._GetTestStatus(self._test_run_id) != self.COMPLETE:
        if self._results['detailed_status'] != current_status:
          logging.info('Test status: %s', self._results['detailed_status'])
          current_status = self._results['detailed_status']
          timeout_counter = 0
          heartbeat_counter = 0
        if heartbeat_counter > self.HEARTBEAT_INTERVAL:
          logging.info('Test status: %s', self._results['detailed_status'])
          heartbeat_counter = 0

        timeout = self._env.timeouts.get(
            current_status, self._env.timeouts['unknown'])
        if timeout_counter > timeout:
          raise remote_device_helper.RemoteDeviceError(
              'Timeout while in %s state for %s seconds'
              % (current_status, timeout),
              is_infra_error=True)
        time.sleep(self.WAIT_TIME)
        timeout_counter += self.WAIT_TIME
        heartbeat_counter += self.WAIT_TIME
      self._DownloadTestResults(self._env.results_path)

      if self._results['results']['exception']:
        raise remote_device_helper.RemoteDeviceError(
            self._results['results']['exception'], is_infra_error=True)

      return self._ParseTestResults()

  #override
  def TearDown(self):
    """Tear down the test run."""
    if self._env.collect:
      self._CollectTearDown()
    elif self._env.trigger:
      assert isinstance(self._env.trigger, basestring), (
                        'File for storing test_run_id must be a string.')
      with open(self._env.trigger, 'w') as persisted_data_file:
        persisted_data = {}
        self.DumpTo(persisted_data)
        self._env.DumpTo(persisted_data)
        persisted_data_file.write(json.dumps(persisted_data))

  def _CollectTearDown(self):
    if self._GetTestStatus(self._test_run_id) != self.COMPLETE:
      with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                              logging.WARNING):
        test_abort_res = appurify_sanitized.api.tests_abort(
            self._env.token, self._test_run_id, reason='Test runner exiting.')
      remote_device_helper.TestHttpResponse(test_abort_res,
                                            'Unable to abort test.')
    if self._results_temp_dir:
      shutil.rmtree(self._results_temp_dir)

  def __enter__(self):
    """Set up the test run when used as a context manager."""
    self.SetUp()
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    """Tear down the test run when used as a context manager."""
    self.TearDown()

  def DumpTo(self, persisted_data):
    test_run_data = {
      self._TEST_RUN_ID_KEY: self._test_run_id,
    }
    persisted_data[self._TEST_RUN_KEY] = test_run_data

  def LoadFrom(self, persisted_data):
    test_run_data = persisted_data[self._TEST_RUN_KEY]
    self._test_run_id = test_run_data[self._TEST_RUN_ID_KEY]

  def _ParseTestResults(self):
    raise NotImplementedError

  def _GetTestByName(self, test_name):
    """Gets test_id for specific test.

    Args:
      test_name: Test to find the ID of.
    """
    with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                            logging.WARNING):
      test_list_res = appurify_sanitized.api.tests_list(self._env.token)
    remote_device_helper.TestHttpResponse(test_list_res,
                                          'Unable to get tests list.')
    for test in test_list_res.json()['response']:
      if test['test_type'] == test_name:
        return test['test_id']
    raise remote_device_helper.RemoteDeviceError(
        'No test found with name %s' % (test_name))

  def _DownloadTestResults(self, results_path):
    """Download the test results from remote device service.

    Downloads results in temporary location, and then copys results
    to results_path if results_path is not set to None.

    Args:
      results_path: Path to download appurify results zipfile.

    Returns:
      Path to downloaded file.
    """

    if self._results_temp_dir is None:
      self._results_temp_dir = tempfile.mkdtemp()
      logging.info('Downloading results to %s.' % self._results_temp_dir)
      with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                              logging.WARNING):
        appurify_sanitized.utils.wget(self._results['results']['url'],
                                      self._results_temp_dir + '/results')
    if results_path:
      logging.info('Copying results to %s', results_path)
      if not os.path.exists(os.path.dirname(results_path)):
        os.makedirs(os.path.dirname(results_path))
      shutil.copy(self._results_temp_dir + '/results', results_path)
    return self._results_temp_dir + '/results'

  def _GetTestStatus(self, test_run_id):
    """Checks the state of the test, and sets self._results

    Args:
      test_run_id: Id of test on on remote service.
    """

    with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                            logging.WARNING):
      test_check_res = appurify_sanitized.api.tests_check_result(
          self._env.token, test_run_id)
    remote_device_helper.TestHttpResponse(test_check_res,
                                          'Unable to get test status.')
    self._results = test_check_res.json()['response']
    return self._results['status']

  def _AmInstrumentTestSetup(self, app_path, test_path, runner_package,
                             environment_variables, extra_apks=None):
    config = {'runner': runner_package}
    if environment_variables:
      config['environment_vars'] = ','.join(
          '%s=%s' % (k, v) for k, v in environment_variables.iteritems())

    self._app_id = self._UploadAppToDevice(app_path)

    data_deps = self._test_instance.GetDataDependencies()
    if data_deps:
      with tempfile.NamedTemporaryFile(suffix='.zip') as test_with_deps:
        sdcard_files = []
        additional_apks = []
        host_test = os.path.basename(test_path)
        with zipfile.ZipFile(test_with_deps.name, 'w') as zip_file:
          zip_file.write(test_path, host_test, zipfile.ZIP_DEFLATED)
          for h, _ in data_deps:
            if os.path.isdir(h):
              zip_utils.WriteToZipFile(zip_file, h, '.')
              sdcard_files.extend(os.listdir(h))
            else:
              zip_utils.WriteToZipFile(zip_file, h, os.path.basename(h))
              sdcard_files.append(os.path.basename(h))
          for a in extra_apks or ():
            zip_utils.WriteToZipFile(zip_file, a, os.path.basename(a));
            additional_apks.append(os.path.basename(a))

        config['sdcard_files'] = ','.join(sdcard_files)
        config['host_test'] = host_test
        if additional_apks:
          config['additional_apks'] = ','.join(additional_apks)
        self._test_id = self._UploadTestToDevice(
            'robotium', test_with_deps.name, app_id=self._app_id)
    else:
      self._test_id = self._UploadTestToDevice('robotium', test_path)

    logging.info('Setting config: %s' % config)
    appurify_configs = {}
    if self._env.network_config:
      appurify_configs['network'] = self._env.network_config
    self._SetTestConfig('robotium', config, **appurify_configs)

  def _UploadAppToDevice(self, app_path):
    """Upload app to device."""
    logging.info('Uploading %s to remote service as %s.', app_path,
                 self._test_instance.suite)
    with open(app_path, 'rb') as apk_src:
      with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                              logging.WARNING):
        upload_results = appurify_sanitized.api.apps_upload(
            self._env.token, apk_src, 'raw', name=self._test_instance.suite)
      remote_device_helper.TestHttpResponse(
          upload_results, 'Unable to upload %s.' % app_path)
      return upload_results.json()['response']['app_id']

  def _UploadTestToDevice(self, test_type, test_path, app_id=None):
    """Upload test to device
    Args:
      test_type: Type of test that is being uploaded. Ex. uirobot, gtest..
    """
    logging.info('Uploading %s to remote service.' % test_path)
    with open(test_path, 'rb') as test_src:
      with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                              logging.WARNING):
        upload_results = appurify_sanitized.api.tests_upload(
            self._env.token, test_src, 'raw', test_type, app_id=app_id)
      remote_device_helper.TestHttpResponse(upload_results,
          'Unable to upload %s.' % test_path)
      return upload_results.json()['response']['test_id']

  def _SetTestConfig(self, runner_type, runner_configs,
                     network=appurify_constants.NETWORK.WIFI_1_BAR,
                     pcap=0, profiler=0, videocapture=0):
    """Generates and uploads config file for test.
    Args:
      runner_configs: Configs specific to the runner you are using.
      network: Config to specify the network environment the devices running
          the tests will be in.
      pcap: Option to set the recording the of network traffic from the device.
      profiler: Option to set the recording of CPU, memory, and network
          transfer usage in the tests.
      videocapture: Option to set video capture during the tests.

    """
    logging.info('Generating config file for test.')
    with tempfile.TemporaryFile() as config:
      config_data = [
          '[appurify]',
          'network=%s' % network,
          'pcap=%s' % pcap,
          'profiler=%s' % profiler,
          'videocapture=%s' % videocapture,
          '[%s]' % runner_type
      ]
      config_data.extend(
          '%s=%s' % (k, v) for k, v in runner_configs.iteritems())
      config.write(''.join('%s\n' % l for l in config_data))
      config.flush()
      config.seek(0)
      with appurify_sanitized.SanitizeLogging(self._env.verbose_count,
                                              logging.WARNING):
        config_response = appurify_sanitized.api.config_upload(
            self._env.token, config, self._test_id)
      remote_device_helper.TestHttpResponse(
          config_response, 'Unable to upload test config.')

  def _LogLogcat(self, level=logging.CRITICAL):
    """Prints out logcat downloaded from remote service.
    Args:
      level: logging level to print at.

    Raises:
      KeyError: If appurify_results/logcat.txt file cannot be found in
                downloaded zip.
    """
    zip_file = self._DownloadTestResults(None)
    with zipfile.ZipFile(zip_file) as z:
      try:
        logcat = z.read('appurify_results/logcat.txt')
        printable_logcat = ''.join(c for c in logcat if c in string.printable)
        for line in printable_logcat.splitlines():
          logging.log(level, line)
      except KeyError:
        logging.error('No logcat found.')

  def _LogAdbTraceLog(self):
    zip_file = self._DownloadTestResults(None)
    with zipfile.ZipFile(zip_file) as z:
      adb_trace_log = z.read('adb_trace.log')
      for line in adb_trace_log.splitlines():
        logging.critical(line)

  def _DidDeviceGoOffline(self):
    zip_file = self._DownloadTestResults(None)
    with zipfile.ZipFile(zip_file) as z:
      adb_trace_log = z.read('adb_trace.log')
      if any(_DEVICE_OFFLINE_RE.search(l) for l in adb_trace_log.splitlines()):
        return True
    return False

  def _DetectPlatformErrors(self, results):
    if not self._results['results']['pass']:
      if any(_SHORT_MSG_RE.search(l)
          for l in self._results['results']['output'].splitlines()):
        self._LogLogcat()
        for line in self._results['results']['output'].splitlines():
          if _LONG_MSG_RE.search(line):
            results.AddResult(base_test_result.BaseTestResult(
                line.split('=')[1], base_test_result.ResultType.CRASH))
            break
        else:
          results.AddResult(base_test_result.BaseTestResult(
              'Unknown platform error detected.',
              base_test_result.ResultType.UNKNOWN))
      elif self._DidDeviceGoOffline():
        self._LogLogcat()
        self._LogAdbTraceLog()
        raise remote_device_helper.RemoteDeviceError(
            'Remote service unable to reach device.', is_infra_error=True)
      else:
        results.AddResult(base_test_result.BaseTestResult(
            'Remote Service detected error.',
            base_test_result.ResultType.UNKNOWN))
