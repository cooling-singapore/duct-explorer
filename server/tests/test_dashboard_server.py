import json
import logging
import os
import shutil
import time
import unittest

from saas.core.logging import Logging
from saas.dor.schemas import DataObject, GPP_DATA_TYPE
from saas.rti.schemas import Task, JobStatus
from saas.sdk.app.auth import UserDB, UserAuth
from saas.sdk.base import SDKProcessor, connect
from tests.base_testcase import create_wd, create_rnd_hex_string

from dashboard.proxy import DashboardProxy
from dashboard.server import DashboardServer, DashboardRuntimeError
from duct.dots.duct import LandUseMap

Logging.initialise(logging.DEBUG)
logger = Logging.get(__name__)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')


class DashboardServerTestCase(unittest.TestCase):
    _server_address = ('127.0.0.1', 5011)
    _node_address = ('127.0.0.1', 5001)
    _wd_path = None
    _server = None
    _proxy = None

    _keystore_path = None
    _datastore_path = None
    _owner = None
    _user = None
    _context = None
    _proc: SDKProcessor = None

    def setUp(self):
        if not self._server:
            # create folders
            self._wd_path = create_wd()
            self._keystore_path = os.path.join(self._wd_path, 'keystore')
            os.makedirs(self._keystore_path, exist_ok=True)

            # initialise user Auth and DB
            UserAuth.initialise(create_rnd_hex_string(32))
            UserDB.initialise(self._wd_path)

            # create users: owner and user
            password = 'password'
            self._owner = UserDB.add_user('foo.bar@email.com', 'Foo Bar', password)
            self._user = UserDB.add_user('john.doe@email.com', 'John Doe', password)

            # create Dashboard server and proxy
            self._server = DashboardServer(self._server_address, self._node_address, self._wd_path)
            self._server.startup()
            self._proxy = DashboardProxy(self._server_address, self._user, password)

            # get SaaS context
            self._context = connect(self._node_address, self._user.keystore)

            # make identities known
            self._context.publish_identity(self._owner.identity)
            self._context.publish_identity(self._user.identity)

            # upload test processor
            source = 'https://github.com/cooling-singapore/saas-processor-template'
            commit_id = '7a87928'
            proc_path = 'processor_test'
            proc_config = 'default'
            gpp = self._context.upload_gpp(source, commit_id, proc_path, proc_config)

            # deploy the test processor
            rti = self._context.rti()
            self._proc = gpp.deploy(rti)

    @classmethod
    def tearDownClass(cls):
        if cls._server is not None:
            # undeploy processor
            cls._proc.undeploy()

            # shutdown server
            cls._server.shutdown()

            # delete working directory
            shutil.rmtree(cls._wd_path, ignore_errors=True)

    def test_get_processors(self):
        results = self._proxy.get_processors()
        assert (results is not None)

        results = {result.proc_id: result for result in results}
        assert (self._proc.descriptor.proc_id in results)

    def test_submit_job_wait_provenance(self):
        # add test data
        content_path = os.path.join(self._wd_path, 'a.json')
        with open(content_path, 'w') as f:
            f.write(json.dumps({"v": 1}))

        # upload object a
        obj_a = self._context.upload_content(content_path, 'JSONObject', 'json', False, False)

        # submit job
        job = self._proxy.submit_job('job0', 'this is a test job', self._proc.descriptor.proc_id, [
            Task.InputReference(name='a', type='reference', obj_id=obj_a.meta.obj_id),
            Task.InputValue(name='b', type='value', value={"v": 1})
        ], [
            Task.Output(name='c', owner_iid=self._user.identity.id,
                        restricted_access=False, content_encrypted=False)
        ])

        # wait for job to be done
        while True:
            time.sleep(1)
            status = self._proxy.get_job(job.id)
            if status['state'] in [JobStatus.State.SUCCESSFUL]:
                break
            elif status['state'] in [JobStatus.State.FAILED, JobStatus.State.CANCELLED]:
                raise DashboardRuntimeError(f"Unexpected state: {status['state']}")

        # test getting all jobs with status
        jobs = self._proxy.get_all_jobs()
        print(jobs)
        assert(len(jobs) == 1)
        assert(jobs[0]['job']['id'] == job.id)

        # check if we have the output data object
        assert (status['output_objects'][0]['output_name'] == 'c')

        # get the provenance information
        obj_c_id = status['output_objects'][0]['obj_id']
        result = self._proxy.provenance(obj_c_id)
        assert(result is not None)
        print(result)

    def test_submit_job_and_cancel(self):
        # add test data
        content_path = os.path.join(self._wd_path, 'a.json')
        with open(content_path, 'w') as f:
            f.write(json.dumps({"v": 1}))

        # upload object a
        obj_a = self._context.upload_content(content_path, 'JSONObject', 'json', False, False)

        # submit job
        job = self._proxy.submit_job('job0', 'this is a test job', self._proc.descriptor.proc_id, [
            Task.InputReference(name='a', type='reference', obj_id=obj_a.meta.obj_id),
            Task.InputValue(name='b', type='value', value={"v": 1})
        ], [
            Task.Output(name='c', owner_iid=self._user.identity.id, restricted_access=False, content_encrypted=False)
        ])

        # wait for job to be running
        while True:
            time.sleep(0.25)
            status = self._proxy.get_job(job.id)
            print(status['state'])
            if status['state'] == JobStatus.State.RUNNING:
                break

        status = self._proxy.cancel_job(job.id)
        assert (status['state'] == JobStatus.State.CANCELLED)

    def test_upload_data_search_delete(self):
        # add test data
        content_path = os.path.join(self._wd_path, 'a.json')
        with open(content_path, 'w') as f:
            f.write(json.dumps({"v": 1}))

        # upload the content
        obj = self._proxy.upload_content(content_path, 'JSONObject', 'json', tags=[
            DataObject.Tag(key='project', value='hello-world'),
            DataObject.Tag(key='department', value='planning')
        ])

        # upload the gpp
        gpp = self._proxy.upload_gpp(
            source='https://github.com/cooling-singapore/saas-processor-template',
            commit_id='7a87928',
            proc_path='processor_test',
            proc_config='default',
            tags=[
                DataObject.Tag(key='project', value='hello-world'),
                DataObject.Tag(key='department', value='IT')
            ])

        # search by patterns
        result = self._proxy.search_data()
        assert(len(result) > 1)

        result = self._proxy.search_data(patterns=['planning'], owned_by_user=True)
        assert(len(result) == 1)

        result = self._proxy.search_data(patterns=['IT'], owned_by_user=True)
        assert(len(result) == 1)

        result = self._proxy.search_data(patterns=['hello-world'], owned_by_user=True)
        assert(len(result) == 2)

        result = self._proxy.search_data(patterns=['planning', 'IT'], owned_by_user=True)
        assert(len(result) == 2)

        result = self._proxy.search_data(c_hashes=[obj.c_hash], owned_by_user=True)
        assert(len(result) == 1)

        result = self._proxy.search_data(c_hashes=[gpp.c_hash], owned_by_user=True)
        assert(len(result) == 2)  # +1 from the GPP that has been uploaded during cls.setUp()

        result = self._proxy.search_data(c_hashes=[obj.c_hash, gpp.c_hash], owned_by_user=True)
        assert(len(result) == 3)

        result = self._proxy.search_data(data_type=GPP_DATA_TYPE, owned_by_user=True)
        assert(len(result) == 2)

        result = self._proxy.search_data(data_format='json', owned_by_user=True)
        assert(len(result) == 3)

        # delete data objects
        result = self._proxy.delete_data(obj.obj_id)
        assert(result is not None)

        result = self._proxy.delete_data(gpp.obj_id)
        assert(result is not None)

    def test_download_extract_feature_lczmap(self):
        # upload the data object
        obj_path = os.path.join(nextcloud_path, 'ucmwrf_lczgen', 'output', 'lcz-map')
        obj = self._proxy.upload_content(obj_path, LandUseMap.DATA_TYPE, 'tiff', tags=[
            DataObject.Tag(key='project', value='hello-world'),
            DataObject.Tag(key='department', value='planning')
        ])

        # download the content
        download_path = os.path.join(self._wd_path, f"{obj.obj_id}.tiff")
        self._proxy.download_content(obj.obj_id, download_path)
        assert(os.path.isfile(download_path))

        # download the feature
        download_path = os.path.join(self._wd_path, 'lczmap.json')
        self._proxy.download_feature(obj.obj_id, download_path, {'data_type': LandUseMap.DATA_TYPE})
        assert(os.path.isfile(download_path))


if __name__ == '__main__':
    unittest.main()
