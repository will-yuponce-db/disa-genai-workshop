# Collection of Databricks-specific functions used by scripts

import base64
import copy
import functools
import json
import logging
import os
import random
import subprocess
import sys
import time
from enum import Enum, auto
from io import BytesIO
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Type
from urllib.parse import urlparse, urlunsplit
from zipfile import ZipFile

import requests


class RetryTimeout(Exception):
    pass


try:
    from scripts.python.platforms import AWSPlatform, AzurePlatform, Platform
except ModuleNotFoundError:
    from platforms import AWSPlatform, AzurePlatform, Platform

from databricks.sdk import AccountClient, WorkspaceClient

try:
    from databricks.sdk.errors import (
        AlreadyExists,
        BadRequest,
        InternalError,
        InvalidParameterValue,
        NotFound,
        ResourceAlreadyExists,
        ResourceConflict,
        ResourceDoesNotExist,
    )
except ImportError:  # pragma: no cover - fallback for older SDKs
    from databricks.sdk.errors.platform import (
        AlreadyExists,
        BadRequest,
        InternalError,
        InvalidParameterValue,
        NotFound,
        ResourceAlreadyExists,
        ResourceConflict,
        ResourceDoesNotExist,
    )
from databricks.sdk.service import catalog as catalog_service
from databricks.sdk.service import sql
from databricks.sdk.service.catalog import (
    AzureManagedIdentityRequest,
    PermissionsChange,
    Privilege,
    SecurableType,
    VolumeType,
)


def _catalog_class(*names: str):
    for name in names:
        cls = getattr(catalog_service, name, None)
        if cls is not None:
            return cls

    class _Fallback:  # pragma: no cover - SDK compatibility shim
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    _Fallback.__name__ = names[0]
    return _Fallback


AwsIamRoleRequest = _catalog_class("AwsIamRoleRequest")
CreateMetastore = _catalog_class("CreateMetastore", "CreateMetastoreRequest")

CreateStorageCredential = _catalog_class("CreateStorageCredential")
UpdateMetastore = _catalog_class("UpdateMetastore", "UpdateMetastoreRequest")
UpdateMetastoreDeltaSharingScope = _catalog_class(
    "DeltaSharingScopeEnum", "UpdateMetastoreDeltaSharingScope"
)
from databricks.sdk.service.compute import ClusterSpec, State
from databricks.sdk.service.iam import (
    AccessControlRequest,
    Patch,
    PatchOp,
    PatchSchema,
    PermissionLevel,
    WorkspacePermission,
)
from databricks.sdk.service.jobs import NotebookTask, Task
from databricks.sdk.service.marketplace import ConsumerTerms
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
    ServingEndpointAccessControlRequest,
    ServingEndpointPermissionLevel,
)
from databricks.sdk.service.settings import (
    DefaultNamespaceSetting,
    StringMessage,
    TokenAccessControlRequest,
    TokenPermissionLevel,
)
from databricks.sdk.service.sql import (
    CreateWarehouseRequestWarehouseType,
    StatementState,
)
from databricks.sdk.service.vectorsearch import EndpointType
from databricks.sdk.service.workspace import (
    AclPermission,
    ImportFormat,
    Language,
    ObjectType,
)

# from wonderwords import RandomWord

# Base URL for S3 data files
S3_DATA_FILES_BASE_URL = (
    "https://s3.us-west-2.amazonaws.com/files.training.databricks.com/"
)


class DBAcademyNamingScheme(Enum):
    USER = 'USERNAME'
    RANDOM = 'RANDOM'


class DBAcademyClusterType(Enum):
    PERSONAL = auto()
    SHARED = auto()
    JOB = auto()


class DBAcademyClusterPolicy(Enum):
    ALL_PURPOSE = 'ALL_PURPOSE'
    JOBS = 'JOBS'
    DLT = 'DLT'
    DLT_UC = 'DLT_UC'


# nested dict implementation of c1.update(c2)
def config_merge(c1: dict, c2: dict):
    for k, v in c2.items():
        if k in c1 and isinstance(c1[k], dict) and isinstance(v, dict):
            c1[k] = config_merge(c1[k], v)
        else:
            c1[k] = v

    return c1


# path can be a file (in which case course_path will be the containing directory) or it
# can be a folder (in which case it will load any .json or .cfg it finds)
def config_load_from_fs(path: str) -> dict:
    config = {}

    if os.path.isdir(path):
        for file in os.scandir(path):
            ext = file.name.split('.')[-1].lower()
            if ext == 'json' or ext == 'cfg':
                with open(file.path) as fd:
                    config.update(json.load(fd))

        config['course_path'] = path

    elif os.path.isfile(path):
        with open(path) as fd:
            config.update(json.load(fd))

        config['course_path'] = os.path.dirname(path)

    return config


def config_load_from_tags(tags: dict) -> dict:
    if tags:
        config_tags = [t for t in tags if t.startswith('dbacademy.config')]

        if config_tags:
            config_tags.sort()

            config_string = ''

            for t in config_tags:
                config_string += tags[t]

            return json.loads(base64.b64decode(config_string).decode())


def config_save_to_tags(config: dict, existing_tags: dict = None, tag_max_len=255):
    tags_out = {}

    # remove any existing config tags if present
    if existing_tags:
        for key in filter(
            lambda k: not k.startswith('dbacademy.config'), existing_tags.keys()
        ):
            tags_out[key] = existing_tags[key]

    # serialize config and base64 encode it to a string
    config_string = base64.b64encode(json.dumps(config).encode()).decode()

    if len(config_string) > tag_max_len:
        custom_tag_count = int((len(config_string) + tag_max_len - 1) / tag_max_len)
        for x in range(custom_tag_count):
            tags_out[f'dbacademy.config.{x:02}'] = config_string[
                x * tag_max_len : (x + 1) * tag_max_len
            ]
    else:
        tags_out['dbacademy.config'] = config_string

    return tags_out


# initialize a DBAcademy object using Vocareum interface
def voc_init():
    custom_data_file = os.getenv('VOC_CUSTOM_DATA_FILE', 'voccustomdata.txt')

    host = os.getenv('VOC_DB_WORKSPACE_URL')
    token = os.getenv('VOC_DB_API_TOKEN')
    account_id = os.getenv('VOC_DB_ACCOUNT_ID')
    client_id = os.getenv('VOC_DB_SP_APPLICATION_ID')
    client_secret = os.getenv('VOC_DB_SP_SECRET')
    if client_secret:
        client_secret = base64.b64decode(client_secret).decode()

    partid = os.getenv('VOC_PARTID')

    for course_path in [
        f'/voc/course/part{partid}',
        '/voc/private/courseware',
        './private/courseware',
    ]:  # the last path is added to test init scripts locally
        if os.path.isdir(course_path):
            course_config = config_load_from_fs(course_path)
            if 'metastore_config' not in course_config:
                course_config['metastore_config'] = {}

            course_config['metastore_config']['name'] = partid
            break
    else:
        course_config = {}
        course_config['metastore_config'] = {}
    course_config['metastore_config']['default_metastore_name'] = os.environ.get(
        "DEFAULT_METASTORE_NAME", ""
    )

    db = DBAcademy(
        host=host,
        token=token,
        account_id=account_id,
        client_id=client_id,
        client_secret=client_secret,
        course_config=course_config,
    )

    with open(custom_data_file, 'w') as data_file:
        data_file.write(json.dumps(course_config))

    return db


class DBAcademy:

    def try_until_succeeds(
        self,
        fn: Callable[..., Any],
        *args,
        exceptions: Iterable[Type[BaseException]] = (Exception,),
        max_attempts: Optional[
            int
        ] = None,  # None = unlimited attempts until max_elapsed
        max_elapsed: Optional[
            float
        ] = 600.0,  # seconds; None = no overall deadline (default 10 min)
        initial_delay: float = 1.0,  # seconds
        max_delay: float = 30.0,  # cap between attempts
        backoff: float = 2.0,  # exponential factor
        jitter: float = 0.25,  # add up to ±jitter*delay
        check: Optional[Callable[[Any], bool]] = None,  # optional success predicate
        **kwargs,
    ) -> Any:
        """
        Call `fn(*args, **kwargs)` repeatedly until it stops raising `exceptions`
        (and optionally passes `check(result)`), using exponential backoff.
        """
        attempt = 0
        delay = max(0.0, initial_delay)
        start = time.monotonic()

        # for logging the fn name
        def callable_name(f):
            if hasattr(f, "__qualname__"):
                return f.__qualname__
            if isinstance(f, functools.partial):
                return f"partial({callable_name(f.func)})"
            if hasattr(f, "__class__"):
                return f"{f.__class__.__name__}.__call__"
            return repr(f)

        while True:
            attempt += 1
            try:
                result = fn(*args, **kwargs)
                last_exc = None
                if check is None or check(result):
                    if attempt > 1:
                        self.logger.warning(
                            f"{callable_name(fn)} succeeded after {attempt} attempts (took {time.monotonic() - start} sec)"
                        )

                    return result  # success!

            except exceptions as e:
                last_exc = e

            # deadlines?
            elapsed = time.monotonic() - start
            if (max_attempts is not None and attempt >= max_attempts) or (
                max_elapsed is not None and elapsed >= max_elapsed
            ):

                msg = f"{callable_name(fn)} still failing after {attempt} attempts ({elapsed} sec)"
                self.logger.error(msg)

                if last_exc:
                    raise RetryTimeout(
                        f"{msg} last exception: {last_exc!r}"
                    ) from last_exc
                else:
                    raise RetryTimeout(f"{msg} last exception: {last_exc!r}")

            # sleep with jitter
            wait = delay
            if jitter:
                wait = max(0.0, wait + random.uniform(-jitter * delay, jitter * delay))
            time.sleep(wait)
            delay = min(max_delay, delay * backoff)

    def __init__(
        self,
        host: str = None,
        token: str = None,
        workspace_client: WorkspaceClient = None,
        account_id: str = None,
        client_id: str = None,
        client_secret: str = None,
        account_host: str = 'https://accounts.cloud.databricks.com',
        course_config: dict = None,
        account_client: AccountClient = None,
    ):

        # set up module logging
        self.logger = logging.getLogger('dbacademy')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter('%(asctime)s (%(name)s) %(levelname)s: %(message)s')
        )
        self.logger.addHandler(handler)

        # create workspace api client
        if workspace_client:
            self.w = workspace_client
        elif host and token:
            # for debugging SDK issues, uncomment the following
            # logging.getLogger('databricks.sdk').setLevel(logging.DEBUG)
            self.w = WorkspaceClient(
                host=host, token=token, debug_truncate_bytes=1024, debug_headers=False
            )
        else:
            self.w = None

        # support for multiple cloud types
        resolved_host = host or (self.w.config.host if self.w else None)
        self.cloud_type, account_host = Platform.get_cloud_configuration(resolved_host)

        # create account api client
        if account_client:
            self.a = account_client
        elif account_id and client_id and client_secret:
            self.a = AccountClient(
                host=account_host,
                account_id=account_id,
                client_id=client_id,
                client_secret=client_secret,
                debug_truncate_bytes=1024,
                debug_headers=False,
            )
        else:
            self.a = None

        # setup platform
        if self.a and self.w:
            match self.cloud_type:
                case 'aws':
                    self.platform = AWSPlatform(self.a, self.w, self.logger)
                case 'azure':
                    self.platform = AzurePlatform(self.a, self.w, self.logger)
                case 'gcp':
                    raise NotImplementedError(f"GCP is not supported yet")
                case _:
                    raise Exception(f"Unsupported cloud type: {self.cloud_type}")
        else:
            self.platform = None

        self.update_config_tags = False
        self._workspace_id = None

        if course_config:
            self.course_config = copy.deepcopy(course_config) if course_config else {}
            self.update_config_tags = True
            self.logger.info(
                f'using the following provided course configuration:\n{json.dumps(self.course_config, indent=4)}'
            )
        elif self.w and self.a:
            workspace = self.a.workspaces.get(self.workspace_id)
            self.course_config = config_load_from_tags(workspace.custom_tags) or {}

            if self.course_config:
                self.logger.info(
                    f'loaded the following configuration from workspace custom tags:\n{json.dumps(self.course_config, indent=4)}'
                )
        else:
            self.course_config = {}
            self.logger.warning('no course configuration loaded')

        self._warehouse = None

        me = self.try_until_succeeds(
            self.w.current_user.me,
            exceptions=(InternalError,),
            max_elapsed=60.0,
            initial_delay=2.0,
        )
        self.username = me.user_name
        self._default_catalog = None
        self.metastore_defer_setup = False

    @property
    def workspace_id(self):
        if self._workspace_id is None:
            self._workspace_id = self.try_until_succeeds(
                self.w.get_workspace_id,
                exceptions=(InternalError,),
                max_elapsed=60.0,
                initial_delay=2.0,
            )
        return self._workspace_id

    # as per https://docs.databricks.com/en/sql/language-manual/sql-ref-names.html
    # - no periods, spaces, or forward slashes (we will replace those with _)
    # - no control characters (0x00 - 0x1f) or DELETE (0x7f) (we will omit those)
    # - all lowercase
    # - limited to 255 chars
    @staticmethod
    def safe_name(name: str):
        return ''.join(
            map(
                lambda x: (
                    '_'
                    if x in ['.', ' ', '/']
                    else '' if ord(x) < 0x20 or ord(x) == 0x7F else x
                ),
                name,
            )
        ).lower()[0:255]

    # generate a name for a principal using one of two schemes:
    # 1. (simple) username-based (name will replace the '@' with a space)
    # 2. (more user-friendly) two-word phrase. If _random_name is passed in, this value will be returned in this case.
    @staticmethod
    def _get_name(
        username: str = None,
        naming_scheme=DBAcademyNamingScheme.RANDOM,
        _random_name=None,
    ):

        if type(naming_scheme) == DBAcademyNamingScheme:
            naming_scheme = naming_scheme.value

        match naming_scheme:
            case DBAcademyNamingScheme.RANDOM.value:
                return username.split('@')[0]
                # LPT-1660 shorting out wonderwords code due to poor choices
                # TODO substitute with homegrown curated list of words
                # if _random_name:
                #     return _random_name
                #
                # r = RandomWord()
                #
                # # if username:
                # #     seed = zlib.crc32(username.encode())
                # #     random.seed(seed)
                #
                # words = r.word(include_parts_of_speech=['adjectives']) + ' ' + r.word(include_parts_of_speech=['nouns'])
                # return words

            case DBAcademyNamingScheme.USER.value:
                return username.split('@')[0] if username else None

            case _:
                return naming_scheme

    # copy a file to DBFS
    def file_to_dbfs(
        self, local_filename: str, dbfs_filename: str, blocksize: int = 1048576
    ):

        with open(local_filename, 'rb') as ifd:
            ofd = self.w.dbfs.create(dbfs_filename, overwrite=True).handle

            while True:
                data = ifd.read(blocksize)
                if data:
                    self.w.dbfs.add_block(ofd, base64.b64encode(data).decode('ascii'))
                else:
                    break

            self.w.dbfs.close(ofd)

    def zip_to_dbfs(self, zip_file: str, dbfs_dir: str = '/', force: bool = False):

        with open(zip_file, 'rb') as fd:
            zip_info = ZipFile(BytesIO(fd.read()))

        for f in filter(lambda x: not x.endswith('/'), zip_info.namelist()):

            dbfs_file = os.path.join(dbfs_dir, f)

            if force or not self.w.dbfs.exists(path=dbfs_file):
                with zip_info.open(f) as ifd:
                    ofd = self.w.dbfs.create(path=dbfs_file, overwrite=True).handle

                    while True:
                        data = ifd.read(1048576)
                        if data:
                            self.w.dbfs.add_block(ofd, base64.b64encode(data).decode())
                        else:
                            break

                    self.w.dbfs.close(ofd)

    # recursively copy a directory to DBFS
    def dir_to_dbfs(self, local_dir: str, dbfs_dir: str = '/'):

        for root, dirs, files in os.walk(local_dir):
            for file in files:
                self.file_to_dbfs(
                    os.path.join(root, file),
                    os.path.join(dbfs_dir, root.lstrip(local_dir), file),
                )

    def _db_files_create_catalog(self, catalog: str):

        # if the dir is named "DEFAULT" then we'll assume the default catalog; otherwise we'll take the
        # subdir name
        if catalog == 'DEFAULT':
            catalog_name = self.default_catalog
        else:
            catalog_name = self.safe_name(catalog)

            if catalog_name != catalog:
                self.logger.warning(
                    f"file_copy: adjusted catalog name from {catalog} to {catalog_name}"
                )

        try:
            self.w.catalogs.create(catalog_name)
            self.logger.info(f"file_copy: created catalog {catalog_name}")

        except BadRequest:
            self.logger.info(f"file_copy: catalog {catalog_name} already exists")

        # grant use of created catalog to all
        self.w.grants.update(
            full_name=catalog_name,
            securable_type=SecurableType.CATALOG,
            changes=[
                PermissionsChange(
                    add=[Privilege.USE_CATALOG], principal='account users'
                )
            ],
        )

        return catalog_name

    def _db_files_create_schema(self, schema: str, catalog_name: str):

        schema_name = self.safe_name(schema)

        if schema_name != schema:
            self.logger.warning(
                f"file_copy: adjusted schema name from {schema} to {schema_name}"
            )

        try:
            self.w.schemas.create(name=schema_name, catalog_name=catalog_name)
            self.logger.info(f"file_copy: created schema {catalog_name}.{schema_name}")

        except BadRequest:
            self.logger.info(
                f"file_copy: schema {catalog_name}.{schema_name} already exists"
            )

        # grant use of created schema to all
        self.w.grants.update(
            full_name=f'{catalog_name}.{schema_name}',
            securable_type=SecurableType.SCHEMA,
            changes=[
                PermissionsChange(add=[Privilege.USE_SCHEMA], principal='account users')
            ],
        )

        return schema_name

    def _db_files_create_volume(self, volume: str, schema_name: str, catalog_name: str):

        volume_name = self.safe_name(volume)

        if volume_name != volume:
            self.logger.warning(
                f"file_copy: adjusted volume name from {volume} to {volume_name}"
            )

        volume_full_name = '.'.join([catalog_name, schema_name, volume_name])

        try:
            self.w.volumes.create(
                catalog_name=catalog_name,
                schema_name=schema_name,
                name=volume_name,
                volume_type=VolumeType.MANAGED,
            )

            self.logger.info(f'created volume {volume_full_name}')

        except ResourceAlreadyExists:
            # volume already exists
            self.logger.info(f'volume {volume_full_name} already exists')

        self.w.grants.update(
            full_name=volume_full_name,
            securable_type=SecurableType.VOLUME,
            changes=[
                PermissionsChange(
                    add=[Privilege.READ_VOLUME], principal='account users'
                )
            ],
        )

        return volume_name

    def dir_to_db(self, src_dir: str):

        for subdir in os.scandir(src_dir):
            if subdir.name == 'Volumes':
                # we can handle /Volumes using the Files API

                # first level dir in here is a catalog
                for catalog_dir in os.scandir(subdir.path):

                    if not catalog_dir.is_dir():
                        # skip files at the catalog level
                        self.logger.error(
                            f'file_copy: {catalog_dir.path} is not a directory'
                        )
                        continue

                    catalog_name = self._db_files_create_catalog(catalog_dir.name)

                    # second level dir in here is a schema
                    for schema_dir in os.scandir(catalog_dir.path):

                        if not schema_dir.is_dir():
                            # skip files at the schema level
                            self.logger.error(
                                f'file_copy: {schema_dir.path} is not a directory'
                            )
                            continue

                        schema_name = self._db_files_create_schema(
                            schema_dir.name, catalog_name
                        )

                        # third level dir in here is a volume
                        for volume_dir in os.scandir(schema_dir.path):

                            if not volume_dir.is_dir():
                                # skip files at the volume level
                                self.logger.error(
                                    f'file_copy: {volume_dir.path} is not a directory'
                                )
                                continue

                            volume_name = self._db_files_create_volume(
                                volume_dir.name, schema_name, catalog_name
                            )

                            # now we just create folders and transfer files
                            for root, dirs, files in os.walk(volume_dir.path):
                                relative_root = root.removeprefix(src_dir)

                                # doesn't seem to be necessary to explicitly create directories first (makes sense) and
                                # skipping it is a time saver
                                # for dir in dirs:
                                #
                                #     full_dst_path = os.path.join(
                                #         '/Volumes',
                                #         catalog_name,
                                #         schema_name,
                                #         volume_name,
                                #         relative_root,
                                #         dir
                                #     )
                                #
                                #     self.w.files.create_directory(full_dst_path)
                                #     self.logger.info(f"file_copy: created folder {full_dst_path}")

                                for file in files:
                                    full_dst_path = os.path.join(
                                        '/Volumes',
                                        catalog_name,
                                        schema_name,
                                        volume_name,
                                        relative_root,
                                        file,
                                    )

                                    with open(os.path.join(root, file), "rb") as infd:
                                        self.w.files.upload(full_dst_path, infd)

                                    self.logger.info(
                                        f"file_copy: uploaded file {full_dst_path}"
                                    )

            else:
                self.logger.error(f'file_copy: {subdir.name} namespace not supported')

    def zip_to_db(self, zip_file: str):

        # data structure to remember which volumes have been created to save on API calls
        created = {}

        # open zip file for reading
        with open(zip_file, 'rb') as fd:
            zip_info = ZipFile(BytesIO(fd.read()))

        # filter out folder entries (ie ending with '/')
        for f in filter(lambda x: not x.endswith('/'), zip_info.namelist()):

            # break out all path components for easier processing
            path_components = f.lstrip('/').split('/')

            # handle files destined for volume
            if path_components[0] == 'Volumes':

                # ensure path components have at least 4 parts:
                # - 1: 'Volume' or 'Volumes'
                # - 2: Catalog
                # - 3: Schema
                # - 4: Volume
                # if not, then it is malformed and we'll flag it as an error

                if len(path_components) < 5:
                    self.logger.error(
                        f'file_copy: archive member {f} missing required 4-level namespace'
                    )
                    continue

                # build hash key and check the cache to see if this volume has already been created rather than blindly
                # doing it for every archive entry (saving a lot of needless API calls)
                [c, s, v] = path_components[1:4]
                csv = '.'.join([c, s, v])

                if csv not in created:
                    catalog_name = self._db_files_create_catalog(c)
                    schema_name = self._db_files_create_schema(s, catalog_name)
                    volume_name = self._db_files_create_volume(
                        v, schema_name, catalog_name
                    )
                    path = f'/Volumes/{catalog_name}/{schema_name}/{volume_name}'
                    created[csv] = path
                else:
                    path = created[csv]

                # build a complete destination path
                path = path + '/' + '/'.join(path_components[4:])

                # upload the file to the calculated destination
                with zip_info.open(f) as infd:
                    self.w.files.upload(path, infd)

                self.logger.info(f"file_copy: uploaded file {path}")

            else:
                # reject non-volume files for now. for future, could handle /Workspace using the import API
                self.logger.error(
                    f'file_copy: {path_components[0]} namespace not supported'
                )

    def _unpack_datafiles_s3_to_db(self, data_file_path: str) -> None:
        """
        Downloads a data zip file from S3 in chunks and unpacks it into the workspace.

        Args:
            data_file_path: Relative path to the data file in S3.
        """
        # Construct full URL
        url = S3_DATA_FILES_BASE_URL + data_file_path

        # Derive filename and save file to /tmp/<filename>
        zip_filename = os.path.basename(urlparse(url).path)
        tmp_file_path = f"/tmp/{zip_filename}"

        self.logger.info(f"Downloading {zip_filename} from URL: {url}")
        self.logger.info(f"Saving to: {tmp_file_path}")

        try:
            # Stream download to avoid loading the full file into memory
            with requests.get(url, stream=True, timeout=(10, 60)) as r:
                r.raise_for_status()

                with open(tmp_file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

            self.logger.info(f"Unpacking data file {tmp_file_path}")
            self.zip_to_db(tmp_file_path)

        except Exception as e:
            self.logger.error(f"Failed to download/unpack data file: {e}")

    # acquire a serverless SQL warehouse for execution of SQL statements
    @property
    def warehouse(self):

        if not self._warehouse:

            # set up a warehouse for internal use; we won't strive to clean it up because we can reuse it for every
            # lifecycle transition (which includes the coming and going of all users)

            warehouse_name = self._get_name(
                username=self.username, naming_scheme=DBAcademyNamingScheme.USER
            )

            # identify an existing serverless SQL warehouse we can use
            for warehouse in self.w.warehouses.list():
                if warehouse.name == warehouse_name:
                    if warehouse.state not in [
                        sql.State.RUNNING,
                        sql.State.STARTING,
                        sql.State.DELETED,
                        sql.State.DELETING,
                    ]:
                        self.w.warehouses.start(warehouse.id)

                    break

            else:
                warehouse = self.w.warehouses.create_and_wait(
                    cluster_size='2X-Small',
                    enable_serverless_compute=True,
                    warehouse_type=CreateWarehouseRequestWarehouseType.PRO,
                    name=warehouse_name,
                    max_num_clusters=1,
                )

                self.logger.info(
                    f'created internal serverless warehouse {warehouse.name}'
                )

            self._warehouse = warehouse.id

        return self._warehouse

    # run a SQL statement (statement is executed on a serverless SQL warehouse)
    def sql(self, statement: str):

        self.logger.debug(f'executing the following statement:\n{statement}')

        response = self.w.statement_execution.execute_statement(
            statement=statement,
            warehouse_id=self.warehouse,
            wait_timeout='50s',
            on_wait_timeout=sql.ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        )

        while response.status.state == StatementState.PENDING:
            self.logger.info(
                f'still waiting for statement to complete: {response.status.state}'
            )
            time.sleep(5)
            response = self.w.statement_execution.get_statement(
                statement_id=response.statement_id
            )

        if response.status.state != StatementState.SUCCEEDED:
            self.logger.info(f'The following statement failed:\n{statement}')
            raise Exception(response.status.error.message)

        return response.result.data_array

    # enable DBFS access through UI
    def enable_dbfs(self):

        self.w.workspace_conf.set_status(contents={'enableDbfsFileBrowser': 'true'})

    # grant usage of PATs to everyone
    def enable_tokens(self):

        try:
            self.w.token_management.update_permissions(
                access_control_list=[
                    TokenAccessControlRequest(
                        group_name='users',
                        permission_level=TokenPermissionLevel.CAN_USE,
                    )
                ]
            )

            self.logger.info('enabled PAT access for all users')

        except ResourceDoesNotExist:

            # if no tokens exist, we need to create at least one in order to set permissions
            # this requirement is not documented but was observed through the API and UI
            token_id = self.w.tokens.create(
                comment='enable_tokens', lifetime_seconds=30
            ).token_info.token_id
            self.logger.info(
                'created temporary token to enable PAT access for all users'
            )

            self.w.token_management.update_permissions(
                access_control_list=[
                    TokenAccessControlRequest(
                        group_name='users',
                        permission_level=TokenPermissionLevel.CAN_USE,
                    )
                ]
            )

            self.logger.info('enabled PAT access for all users')

            # delete the token we created
            try:
                self.w.tokens.delete(token_id)
            except:
                pass

    # delete folder and contents
    def workspace_delete_folder(self, folder: str):

        try:
            self.w.workspace.delete(folder, recursive=True)

        except ResourceDoesNotExist:
            pass

    # delete contents of folder (keeping folder intact)
    def workspace_clear_folder(self, folder: str):

        for f in self.w.workspace.list(folder):
            self.w.workspace.delete(f.path, recursive=True)

    # import contents of dbc/zip file
    def workspace_import(
        self,
        src_parms: dict,
        src_base: str,
        dst_base: str,
        overwrite: bool = False,
        dbfs: bool = False,
    ):

        # use urlparse() to determine if src is a web url (git repo) or a file path
        url_object = urlparse(src_parms['src'])

        if url_object.scheme:
            # looks like a web url; we'll assume it's a git repo
            dbc = None
            repo = src_parms['src']
            repo_provider = src_parms.get('provider', 'gitHub')
        else:
            # looks like a local file; handle relative or absolute paths

            repo = None
            repo_provider = None

            if os.path.isabs(src_parms['src']):
                dbc = src_parms['src']
            else:
                dbc = os.path.join(src_base, src_parms['src'])

        folder = src_parms.get('folder', os.path.split(src_parms['src'])[1][0:-4])

        dst = os.path.join(dst_base, folder)

        # delete existing folder if overwrite == True
        if overwrite:
            self.workspace_delete_folder(dst)

        try:
            # attempt to get the status of dst folder (throws exception if not there)
            self.w.workspace.get_status(dst)

        except ResourceDoesNotExist:
            # folder not there; import material

            if dbc:
                self.logger.info(f"Importing material in {dbc} to {dst}")

                if dbc[-4:].lower() == '.dbc':
                    fmt = ImportFormat.DBC
                    import_dst = dst
                    with open(dbc, 'rb') as fd:
                        self.w.workspace.import_(
                            path=import_dst,
                            format=fmt,
                            content=base64.b64encode(fd.read()).decode('ascii'),
                        )
                else:
                    # unzip and import each supported file individually
                    with ZipFile(dbc, 'r') as zf:
                        notebooks = [n for n in zf.infolist() if not n.is_dir()]
                        notebooks.sort(key=lambda n: n.filename)

                        for notebook in notebooks:
                            # normalize path inside zip (strip leading ./ and convert backslashes)
                            notebook_path = notebook.filename.lstrip('./').replace(
                                '\\', '/'
                            )
                            # Skip any top-level zip entries that are just directories
                            if notebook_path.endswith('/'):
                                continue
                            # Strip repeated top-level folders that equal the zip's folder name
                            path_segments = [
                                p for p in notebook_path.split('/') if p != ''
                            ]
                            while (
                                path_segments
                                and path_segments[0].lower() == folder.lower()
                            ):
                                path_segments.pop(0)
                            # if nothing remains after stripping, skip
                            if not path_segments:
                                continue

                            # rebuild normalized path and split ext
                            notebook_path = '/'.join(path_segments)
                            notebook_base, ext = os.path.splitext(notebook_path)
                            ext = ext.lower().lstrip('.')

                            target = os.path.join(dst, notebook_base)
                            parent = os.path.dirname(target)
                            if parent and hasattr(self.w.workspace, "mkdirs"):
                                try:
                                    self.w.workspace.mkdirs(parent)
                                except Exception:
                                    pass

                            try:
                                with zf.open(notebook) as fd:
                                    content_bytes = fd.read()

                                b64 = base64.b64encode(content_bytes).decode('ascii')

                                # Check if file is a Databricks notebook by looking for the header
                                is_databricks_notebook = False
                                try:
                                    databricks_nb_start = (
                                        content_bytes.decode('utf-8')
                                        .split('\n')[0]
                                        .strip()
                                    )
                                    is_databricks_notebook = (
                                        databricks_nb_start
                                        == '# Databricks notebook source'
                                    )
                                except (UnicodeDecodeError, IndexError):
                                    # If we can't decode or split, it's not a text file/notebook
                                    is_databricks_notebook = False

                                if ext == 'dbc':
                                    self.w.workspace.import_(
                                        path=target,
                                        content=b64,
                                        format=ImportFormat.DBC,
                                    )

                                elif ext == 'ipynb':
                                    # ipynb -> JUPYTER
                                    self.w.workspace.import_(
                                        path=target,
                                        content=b64,
                                        format=ImportFormat.JUPYTER,
                                    )

                                elif (
                                    ext in ('py', 'r', 'scala', 'sql')
                                    and is_databricks_notebook
                                ):
                                    # Only import as notebook if it has the Databricks header
                                    match ext:
                                        case 'py':
                                            language = Language.PYTHON
                                        case 'r':
                                            language = Language.R
                                        case 'scala':
                                            language = Language.SCALA
                                        case 'sql':
                                            language = Language.SQL
                                        case _:
                                            language = None

                                    self.w.workspace.import_(
                                        path=target,
                                        content=b64,
                                        format=ImportFormat.SOURCE,
                                        language=language,
                                    )
                                else:
                                    # Import as file with extension (not as notebook)
                                    target_with_ext = os.path.join(dst, notebook_path)
                                    self.w.workspace.import_(
                                        path=target_with_ext,
                                        content=b64,
                                        format=ImportFormat.AUTO,
                                    )
                            except Exception as e:
                                # log and continue with other files
                                self.logger.error(
                                    f"Failed to import {notebook_path} → {target}: {e}",
                                    exc_info=True,
                                )
                                continue

                    # unpack DBFS zip if present (keep original behavior)
                    if dbfs:
                        dbc_dbfs = dbc[0:-4] + '-dbfs.zip'
                        if os.path.isfile(dbc_dbfs):
                            self.logger.info(
                                f"Uploading material in {dbc_dbfs} to DBFS"
                            )
                            self.zip_to_dbfs(dbc_dbfs, force=overwrite)
                    self.logger.info(f"Finished importing notebooks into {dst}")
            else:
                self.logger.info(f"Pulling material from {repo} to {dst}")
                self.w.repos.create(url=repo, path=dst, provider=repo_provider)

            # apply patches, if present
            if 'patch' in src_parms:
                for p in src_parms['patch']:
                    self.logger.info(f"- patching {p['target']}")

                    # figure out src
                    if os.path.isabs(p['src']):
                        src = p['src']
                    else:
                        src = os.path.join(src_base, p['src'])

                    target = os.path.join(dst, p['target'])

                    # make way for dest if there
                    try:
                        self.w.workspace.delete(target, recursive=True)

                    except ResourceDoesNotExist:
                        pass

                    with open(src, 'rb') as fd:
                        if src[-4:].lower() == '.dbc':
                            self.w.workspace.import_(
                                path=target,
                                content=base64.b64encode(fd.read()).decode('ascii'),
                                format=ImportFormat.DBC,
                            )
                        elif src.lower().endswith('.ipynb'):
                            self.w.workspace.import_(
                                path=target,
                                content=base64.b64encode(fd.read()).decode('ascii'),
                                format=ImportFormat.JUPYTER,
                            )
                        else:
                            match src.split('.')[-1].lower():
                                case 'py':
                                    language = Language.PYTHON
                                case 'r':
                                    language = Language.R
                                case 'scala':
                                    language = Language.SCALA
                                case 'sql':
                                    language = Language.SQL
                                case _:
                                    language = None

                            self.w.workspace.import_(
                                path=target,
                                content=base64.b64encode(fd.read()).decode(),
                                format=ImportFormat.SOURCE,
                                language=language,
                            )

        # determine the main notebook:
        # - ['entry'] if specified, otherwise
        # - the first notebook in the sorted list of notebooks that got extracted

        if 'entry' in src_parms:
            main_notebook = src_parms['entry']
        else:
            # if entry not explicitly specified, choose first notebook in the sorted list

            notebooks = sorted(
                [
                    os.path.split(i.path)[1]
                    for i in self.w.workspace.list(dst)
                    if i.object_type == ObjectType.NOTEBOOK
                ]
            )

            main_notebook = notebooks[0] if len(notebooks) else ''

        if main_notebook:
            # return os.path.join(dst, main_notebook)
            return os.path.join(dst, main_notebook)

    # get url of a notebook (given its path), or other path relative to workspace root (for example, "explore/data" to
    # obtain the URL that directs to the Catalog Explorer page)
    def workspace_get_url(self, notebook_path: str = None, path: str = None):

        url = urlparse(self.w.config.host)

        if path is None:
            return urlunsplit(
                (
                    url.scheme,
                    url.netloc,
                    url.path,
                    url.query,
                    f'notebook/{self.w.workspace.get_status(notebook_path).object_id}',
                )
            )

        return urlunsplit((url.scheme, url.netloc, path, url.query, None))

    def secrets_put(
        self, scope: str = None, secrets: dict = None, principal: str = 'users'
    ):

        if not scope:
            scope = principal
            self.user_putmetadata(principal, records_for={'secrets': scope})

        try:
            self.w.secrets.create_scope(scope=scope)
        except ResourceAlreadyExists:
            pass

        self.w.secrets.put_acl(
            scope=scope, principal=principal, permission=AclPermission.READ
        )

        for key in secrets:
            self.w.secrets.put_secret(scope=scope, key=key, string_value=secrets[key])

    # build a complete cluster configuration using provided settings as a starting point
    # returns a new structure with filled out settings
    def _cluster_config(
        self,
        catalog: str = None,
        settings: dict = None,
        username: str = None,
        ctype: DBAcademyClusterType = DBAcademyClusterType.PERSONAL,
    ):

        # create a deep copy of the settings which we'll modify and pass back
        settings = copy.deepcopy(settings) if settings else {}

        # strip out settings not applicable for job clusters
        if ctype == DBAcademyClusterType.JOB:
            for i in ['autotermination_minutes']:
                if i in settings:
                    del settings[i]

        if 'aws_attributes' not in settings:
            settings['aws_attributes'] = {}

        if 'zone_id' not in settings['aws_attributes']:
            settings['aws_attributes']['zone_id'] = 'auto'

        # dynamically select DBR
        # change values of photon, ml, gpu as needed, or simply hardcode
        if 'spark_version' not in settings:
            settings['spark_version'] = self.w.clusters.select_spark_version(
                long_term_support=True, latest=True, photon=False, ml=False, gpu=False
            )

        # dynamically select node type
        # change values as needed or simply hardcode
        if 'node_type_id' not in settings:
            settings['node_type_id'] = (
                self.w.clusters.select_node_type(
                    photon_driver_capable=False, photon_worker_capable=False
                )
                if ctype != DBAcademyClusterType.JOB
                else "m6gd.large"
            )

        settings['enable_elastic_disk'] = True

        if (
            'autotermination_minutes' not in settings
            and ctype != DBAcademyClusterType.JOB
        ):
            settings['autotermination_minutes'] = 120

        # configure data_security_mode (access mode) based on whether the cluster is shared or not
        # if shared, data_security_mode = user isolation (shared)
        # if not shared, data_security_mode = single user

        if ctype == DBAcademyClusterType.SHARED:
            settings['data_security_mode'] = 'USER_ISOLATION'
        elif ctype in [DBAcademyClusterType.PERSONAL, DBAcademyClusterType.JOB]:
            settings['data_security_mode'] = 'SINGLE_USER'
            settings['single_user_name'] = username

        if 'spark_conf' not in settings:
            settings['spark_conf'] = {}

        # configure default catalog
        if catalog:
            settings['spark_conf'][
                'spark.databricks.sql.initial.catalog.name'
            ] = catalog

        if 'custom_tags' not in settings:
            settings['custom_tags'] = {}

        if 'num_workers' not in settings and 'autoscale' not in settings:
            settings['spark_conf'].update(
                {
                    'spark.databricks.cluster.profile': 'singleNode',
                    'spark.master': 'local[*, 4]',
                }
            )
            settings['custom_tags']['ResourceClass'] = 'SingleNode'
            settings['num_workers'] = 0

        if 'spark_env_vars' not in settings:
            settings['spark_env_vars'] = {}

        settings['spark_env_vars']['PYSPARK_PYTHON'] = '/databricks/python3/bin/python3'

        # ensure on-demand for jobs (for at least one instance)
        if ctype == DBAcademyClusterType.JOB:
            settings['aws_attributes']['first_on_demand'] = 1

        return settings

    def cluster_policies_create(self):

        policy_definitions = {
            DBAcademyClusterPolicy.ALL_PURPOSE.value: {
                "name": "DBAcademy",
                "cluster_type": {"type": "fixed", "value": "all-purpose"},
                "autotermination_minutes": {
                    "type": "range",
                    "minValue": 1,
                    "maxValue": 180,
                    "defaultValue": 120,
                    "hidden": False,
                },
                "spark_conf.spark.databricks.cluster.profile": {
                    "type": "fixed",
                    "value": "singleNode",
                    "hidden": False,
                },
                "num_workers": {"type": "fixed", "value": 0, "hidden": False},
                "data_security_mode": {
                    "type": "unlimited",
                    "defaultValue": "SINGLE_USER",
                },
                "runtime_engine": {"type": "unlimited", "defaultValue": "STANDARD"},
                "driver_node_type_id": {
                    "type": "fixed",
                    "value": "i3.xlarge",
                    "hidden": False,
                },
            },
            DBAcademyClusterPolicy.JOBS.value: {
                "name": "DBAcademy Jobs",
                "cluster_type": {"type": "fixed", "value": "job"},
                "spark_conf.spark.databricks.cluster.profile": {
                    "type": "fixed",
                    "value": "singleNode",
                    "hidden": False,
                },
                "num_workers": {"type": "fixed", "value": 0, "hidden": False},
                "data_security_mode": {
                    "type": "unlimited",
                    "defaultValue": "SINGLE_USER",
                },
                "runtime_engine": {"type": "unlimited", "defaultValue": "STANDARD"},
                "driver_node_type_id": {
                    "type": "fixed",
                    "value": "i3.xlarge",
                    "hidden": False,
                },
            },
            DBAcademyClusterPolicy.DLT.value: {
                "name": "DBAcademy DLT",
                "cluster_type": {"type": "fixed", "value": "dlt"},
                "num_workers": {"type": "range", "maxValue": 1},
                "driver_node_type_id": {
                    "type": "fixed",
                    "value": "i3.xlarge",
                    "hidden": False,
                },
                "node_type_id": {
                    "type": "fixed",
                    "value": "i3.xlarge",
                    "hidden": False,
                },
            },
            DBAcademyClusterPolicy.DLT_UC.value: {
                "name": "DBAcademy DLT UC",
                "cluster_type": {"type": "fixed", "value": "dlt"},
                "num_workers": {"type": "range", "maxValue": 1},
                "driver_node_type_id": {
                    "type": "fixed",
                    "value": "i3.xlarge",
                    "hidden": False,
                },
                "node_type_id": {
                    "type": "fixed",
                    "value": "i3.xlarge",
                    "hidden": False,
                },
            },
        }

        if 'cluster_policies' not in self.course_config:
            return

        for policy in self.course_config['cluster_policies']:
            settings = {}

            if 'template' in policy:
                if policy['template'] in policy_definitions:
                    settings.update(policy_definitions[policy['template']])
                else:
                    self.logger.info(
                        f'encountered unsupported cluster policy template {policy["template"]}'
                    )

            settings.update(policy)

            if 'template' in settings:
                del settings['template']

            if 'name' in settings:
                name = settings['name']
                del settings['name']
            else:
                self.logger.info('policy name not specified; skipping')
                continue

            # delete policy if it already exists
            for p in self.w.cluster_policies.list():
                if p.name == name:
                    self.logger.warning(f'policy {name} already exists; deleting')
                    self.w.cluster_policies.delete(p.policy_id)
                    break

            self.logger.info(
                f'about to create policy\n{json.dumps(settings, indent=4)}'
            )
            response = self.w.cluster_policies.create(
                name=name, definition=json.dumps(settings), max_clusters_per_user=1
            )

            self.logger.info(f'created cluster policy {name}')

            # allow everyone to use the policy
            self.w.permissions.set(
                request_object_type='cluster-policies',
                request_object_id=response.policy_id,
                access_control_list=[
                    AccessControlRequest(
                        group_name='users', permission_level=PermissionLevel.CAN_USE
                    )
                ],
            )

    def cluster_start_or_create(
        self,
        principal: str = None,
        catalog: str = None,
        cluster_name: str = None,
        _random_name: str = None,
    ):

        # check user_config block first for cluster_config, and fall back to main block for backwards compatibility
        if (
            'user_config' in self.course_config
            and 'cluster_config' in self.course_config['user_config']
        ):
            settings = self.course_config['user_config']['cluster_config']
        elif 'cluster_config' in self.course_config:
            settings = self.course_config['cluster_config']
        else:
            # no cluster config found, return nothing
            return

        if 'aws_attributes' not in settings:
            settings['aws_attributes'] = {}
            settings['aws_attributes']['first_on_demand'] = 1

        shared = False

        if not cluster_name:
            cluster_name = self._get_name(
                username=principal,
                naming_scheme=settings.get(
                    'cluster_name', DBAcademyNamingScheme.RANDOM
                ),
                _random_name=_random_name,
            )

        if cluster_name == settings.get('cluster_name'):
            shared = True

        self.logger.info(
            f'cluster name for user {principal} is {cluster_name} and it is {"" if shared else "not "}a shared cluster'
        )

        # if named cluster already exists, start it
        for c in self.w.clusters.list():
            if c.cluster_name == cluster_name:
                if c.state not in [
                    State.RUNNING,
                    State.PENDING,
                    State.RESIZING,
                    State.RESTARTING,
                ]:
                    self.logger.info(
                        f'cluster {cluster_name} already exists; starting it'
                    )
                    self.w.clusters.start(c.cluster_id)
                else:
                    self.logger.info(
                        f'cluster {cluster_name} already exists and looks like it is (or will be) running'
                    )

                return not shared, cluster_name, c.cluster_id

        # no cluster existing; configure settings and create cluster

        settings = self._cluster_config(
            catalog=catalog,
            username=principal,
            settings=settings,
            ctype=(
                DBAcademyClusterType.SHARED if shared else DBAcademyClusterType.PERSONAL
            ),
        )

        settings['cluster_name'] = cluster_name

        self.logger.debug(
            f"Creating cluster with following options: {json.dumps(settings, indent=4)}"
        )

        # note: using low-level do() call rather than cluster.create() because the latter does not allow
        # specifying data_security_mode at the current time
        cluster = self.w.api_client.do(
            'POST', '/api/2.0/clusters/create', body=settings
        )
        self.logger.info(f'submitted request to create cluster {cluster_name}')

        # install libraries if supplied
        if 'libraries' in settings:
            self.w.api_client.do(
                'POST',
                '/api/2.0/libraries/install',
                body={
                    'cluster_id': cluster['cluster_id'],
                    'libraries': settings['libraries'],
                },
            )
            self.logger.info(
                f'submitted request to install libraries on cluster {cluster_name}'
            )

        if shared:
            acl = [
                AccessControlRequest(
                    group_name='users', permission_level=PermissionLevel.CAN_RESTART
                )
            ]
            self.logger.info(f'configuring access to {cluster_name} for all users')
        else:
            acl = [
                AccessControlRequest(
                    user_name=principal, permission_level=PermissionLevel.CAN_RESTART
                )
            ]
            self.logger.info(f'configuring access to {cluster_name} for {principal}')

        # configure permissions
        self.w.permissions.set(
            request_object_type='clusters',
            request_object_id=cluster['cluster_id'],
            access_control_list=acl,
        )

        return not shared, cluster_name, cluster['cluster_id']

    def warehouse_start_or_create(
        self,
        principal: str = False,
        warehouse_name: str = None,
        _random_name: str = None,
    ):

        # check user_config block first for cluster_config, and fall back to main block for backwards compatibility
        if (
            'user_config' in self.course_config
            and 'warehouse' in self.course_config['user_config']
        ):
            settings = self.course_config['user_config']['warehouse']
        elif 'warehouse' in self.course_config:
            settings = self.course_config['warehouse']
        else:
            # no warehouse config found, return nothing
            return

        shared = False

        if not warehouse_name:
            warehouse_name = self._get_name(
                username=principal,
                naming_scheme=settings.get('name', DBAcademyNamingScheme.RANDOM),
                _random_name=_random_name,
            )

        if warehouse_name == settings.get('name'):
            shared = True

        self.logger.info(
            f'warehouse name for user {principal} is {warehouse_name} and it is {"" if shared else "not "}shared'
        )

        # if named warehouse already exists, start it
        for wh in self.w.warehouses.list():
            if wh.name == warehouse_name:
                if wh.state not in [
                    sql.State.RUNNING,
                    sql.State.STARTING,
                    sql.State.DELETED,
                    sql.State.DELETING,
                ]:
                    self.logger.info(
                        f'warehouse {warehouse_name} already exists; starting it'
                    )
                    self.w.warehouses.start(wh.id)
                else:
                    self.logger.info(
                        f'warehouse {warehouse_name} already exists and looks like it is (or will be) running'
                    )

                return not shared, warehouse_name, wh.id

        # no warehouse existing; configure settings and create

        settings = copy.deepcopy(settings)

        settings['name'] = warehouse_name

        if 'warehouse_type' not in settings:
            settings['warehouse_type'] = 'PRO'
            settings['enable_serverless_compute'] = True

        if 'spot_instance_policy' not in settings:
            # settings['spot_instance_policy'] = sql.SpotInstancePolicy.COST_OPTIMIZED
            settings['spot_instance_policy'] = 'COST_OPTIMIZED'

        if 'min_num_clusters' not in settings:
            settings['min_num_clusters'] = 1

        if 'max_num_clusters' not in settings:
            settings['max_num_clusters'] = settings['min_num_clusters']

        if 'cluster_size' not in settings:
            settings['cluster_size'] = '2X-Small'

        # expire after idling for 30 min - adjust if needed
        if 'auto_stop_mins' not in settings:
            settings['auto_stop_mins'] = 30

        # invoke warehouse creation
        # note: using low-level do() call rather than warehouses.create() to be able to get id without having to wait
        # warehouse_id = w.warehouses.create_and_wait(**my_settings).id
        warehouse = self.w.api_client.do(
            'POST', '/api/2.0/sql/warehouses', body=settings
        )
        self.logger.info(f'submitted request to create warehouse {warehouse_name}')

        # configure permissions

        if shared:
            acl = [
                AccessControlRequest(
                    group_name='users', permission_level=PermissionLevel.CAN_USE
                )
            ]
            self.logger.info(
                f'configuring CAN USE access to {warehouse_name} for all users'
            )
        else:
            acl = [
                AccessControlRequest(
                    user_name=principal, permission_level=PermissionLevel.CAN_MONITOR
                )
            ]
            self.logger.info(
                f'configuring CAN MONITOR access to {warehouse_name} for {principal}'
            )

        self.w.permissions.set(
            request_object_type='warehouses',
            request_object_id=warehouse['id'],
            access_control_list=acl,
        )

        return not shared, warehouse_name, warehouse['id']

    def vector_search_endpoints_create(self, specs: List[Dict]):

        for i in specs:
            try:
                endpoint_id = self.w.vector_search_endpoints.create_endpoint(
                    name=i['name'], endpoint_type=EndpointType.STANDARD
                ).response.id

                self.logger.info(f'created vector search endpoint {i["name"]}')

            # at time of writing, create_endpoint throws NotFound even on succeeding (underlying REST API does the same
            # thing)
            except NotFound:
                endpoint_id = self.w.vector_search_endpoints.get_endpoint(
                    endpoint_name=i['name']
                ).id
            except AlreadyExists:
                endpoint_id = self.w.vector_search_endpoints.get_endpoint(
                    endpoint_name=i['name']
                ).id
                self.logger.info(f'vector search endpoint {i["name"]} already exists')

            try:
                self.w.permissions.update(
                    request_object_type='vector-search-endpoints',
                    request_object_id=endpoint_id,
                    access_control_list=[
                        AccessControlRequest(
                            group_name='users', permission_level=PermissionLevel.CAN_USE
                        )
                    ],
                )

                self.logger.info(
                    f'opened permissions on vector search endpoint {i["name"]}'
                )

            except Exception as e:
                self.logger.error(
                    f'error opening permissions on vector search endpoint {i["name"]}: {str(e)}'
                )

    def run_setup(self, parameters: dict, src_base: str, user: str = None):

        setup_notebook = self.workspace_import(
            parameters,
            src_base,
            dst_base=os.path.join('/Users', user or self.username),
            overwrite=not user,
        )

        if not setup_notebook:
            self.logger.error('could not find a setup notebook')
            return

        job_parameters = {'host': self.w.config.host, 'token': self.w.config.token}

        if user:
            job_parameters['username'] = user
            task_key = f'setup-{user}'
        else:
            task_key = 'setup-workspace'

        settings = self.course_config.get('cluster_config', {})
        cluster_parameters = self._cluster_config(
            settings=settings, ctype=DBAcademyClusterType.JOB
        )

        job_cluster_type = self.course_config.get("workspace_setup", {}).get(
            "serverless_job_cluster", False
        )

        task_kwargs = dict(
            notebook_task=NotebookTask(
                notebook_path=setup_notebook, base_parameters=job_parameters
            ),
            task_key=task_key,
            max_retries=1,
            min_retry_interval_millis=600000,
        )

        if job_cluster_type:
            pass
        else:
            task_kwargs["new_cluster"] = ClusterSpec.from_dict(cluster_parameters)

        job = self.w.jobs.create(
            name=task_key, tasks=[Task(**task_kwargs)], timeout_seconds=0
        )

        self.w.jobs.run_now(job_id=job.job_id)

        self.logger.info(f"submitted job {job.job_id} to run {setup_notebook}")

    @property
    def default_catalog(self):

        if self._default_catalog:
            return self._default_catalog

        try:
            return self.w.settings.default_namespace.get().namespace.value
        except ResourceDoesNotExist:
            pass

        return self.course_config.get('metastore_config', {}).get(
            'default_catalog', 'dbacademy'
        )

    # attach to the named metastore (creating one if necessary, copying settings as needed from the default metastore
    # if those settings are not specified)
    def metastore_create(self):

        metastore_config = self.course_config.get('metastore_config', {})

        workspace_id = self.workspace_id
        region = self.platform.get_region(workspace_id)

        def _find_metastore(metastore_region: str, metastore_name: str | None = None):
            metastore_lists = self.a.metastores.list()
            if metastore_name:
                full_name = f'{metastore_name}-{metastore_region}'
                # look for metastore with same name and double-check the region
                for m in metastore_lists:
                    if (
                        m.name in [full_name, metastore_name]
                        and m.region == metastore_region
                    ):
                        return m

            else:
                for m in metastore_lists:
                    if m.name == self.course_config.get("metastore_config", {}).get(
                        "default_metastore_name"
                    ):
                        return m
                for m in metastore_lists:
                    # identify first metastore in the region if no name specified
                    if (
                        m.region == metastore_region
                        and m.storage_root is not None
                        and m.storage_root_credential_id is not None
                    ):
                        return m

            raise NotFound

        if metastore_config.get("unique", False):
            # if metastore.unique is True, then use the workspace_id as a unique name to ensure each
            # workspace gets a unique name. This ensures metastore level service constraints are not
            # shared over workspaces
            name = f'ws{workspace_id}'
            self.logger.info(f'Unique metastore will be configured as {name}')
        else:
            # get metastore name. if not specified it will assume a name based on the workspace id
            name = metastore_config.get('name', f'ws{workspace_id}')
            self.logger.info(f'Shared metastore name will be {name}')

        try:
            # only creating a metastore if a metastore name is specified in the course_config and no metastore exists in the region with the same name
            metastore = None
            if "name" in self.course_config["metastore_config"]:
                metastore = _find_metastore(
                    metastore_region=region,
                    metastore_name=self.course_config["metastore_config"]["name"],
                )
            else:
                self.logger.info(
                    f"metastore name not found in course_config, Using default metastore in the region"
                )
            if not metastore:
                raise NotFound
            self.logger.info(
                f'metastore {metastore.name} ({metastore.metastore_id}) exists; will use that one'
            )

        except NotFound:
            metastore = None
            self.logger.info(f"metastore {name} doesn't exist; will create")

        # find a metastore to copy settings from, using default_metastore_name (or just use first metastore in the
        # region if that isn't specified)
        default_metastore = _find_metastore(
            metastore_region=region,
            # metastore_name=metastore_config.get('default_metastore_name'), #uncomment this line when there are default metastores added to each region
        )

        if not metastore:
            metastore = self.platform.create_metastore(
                name=name,
                region=region,
                metastore_config=metastore_config,
                default_metastore=default_metastore,
            )

        # update metastore to set delta sharing scope and token lifetime
        update_metastore_req = UpdateMetastore()
        update_metastore_req.delta_sharing_scope = (
            UpdateMetastoreDeltaSharingScope.INTERNAL_AND_EXTERNAL
        )
        update_metastore_req.delta_sharing_recipient_token_lifetime_in_seconds = (
            31536000
        )

        self.a.metastores.update(
            metastore_id=metastore.metastore_id, metastore_info=update_metastore_req
        )

        # assign metastore to workspace
        self.a.workspaces.get(workspace_id)
        try:
            current_metastore = self.w.metastores.current().metastore_id
        except:
            current_metastore = None

        if current_metastore != metastore.metastore_id:
            self.logger.info(
                f"assigning metastore {metastore.name} (id={metastore.metastore_id}) to workspace {workspace_id}"
            )

            self.a.metastore_assignments.create(
                workspace_id=workspace_id, metastore_id=metastore.metastore_id
            )

            if current_metastore:

                try:
                    current_metastore_summary = self.w.metastores.summary()
                    self.logger.warning(
                        f"existing metastore {current_metastore_summary.name} (id={current_metastore}) detected; will defer setup for some time to avoid cache issues"
                    )
                    self.metastore_defer_setup = True

                    if self._warehouse:
                        self.logger.warning(
                            f'also stopping warehouse {self._warehouse} to invalidate cache'
                        )
                        self.w.warehouses.stop(self._warehouse)

                except NotFound:
                    self.logger.warning(f"existing metastore no longer exists")

        self.logger.info(
            f"assigned metastore {metastore.metastore_id} to workspace {workspace_id}"
        )

        # set workspace default catalog
        default_catalog = metastore_config.get('default_catalog', 'dbacademy')

        setting = DefaultNamespaceSetting(
            namespace=StringMessage(value=default_catalog)
        )

        try:
            self.w.settings.default_namespace.update(
                allow_missing=True, setting=setting, field_mask='namespace'
            )

            self.logger.info(f"set workspace default catalog to {default_catalog}")

        except ResourceConflict as e:

            setting.etag = json.loads(e.args[0])["serializedCT"]
            self.logger.info(
                f'resource conflict setting workspace default catalog to {default_catalog}; will retry with fresh etag ({setting.etag})'
            )

            self.w.settings.default_namespace.update(
                allow_missing=True, setting=setting, field_mask='namespace'
            )

        self._default_catalog = default_catalog

    # initialize a metastore (create default catalog, operational schema, metadata table, etc. this is done in a
    # separate function so that we have the option to defer setup and avoid cache coherency issues shortly after
    # assigning the new metastore to the workspace
    def metastore_setup(self):

        if self.metastore_defer_setup:
            self.logger.info(
                'waiting 12 min TTL for metastore setup following metastore change'
            )
            time.sleep(720)
            self.logger.info('proceeding with metastore setup')

        metastore_config = self.course_config.get('metastore_config', {})

        def _schema_set_ownerships(
            _w: WorkspaceClient, _catalog: str, _schema: str, _owner: str
        ):

            for _function in _w.functions.list(
                catalog_name=_catalog, schema_name=_schema
            ):
                _w.functions.update(name=_function.full_name, owner=_owner)

            for _table in _w.tables.list(catalog_name=_catalog, schema_name=_schema):
                _w.tables.update(full_name=_table.full_name, owner=_owner)

            for _volume in _w.volumes.list(catalog_name=_catalog, schema_name=_schema):
                _w.volumes.update(name=_volume.full_name, owner=_owner)

            for _model in _w.registered_models.list(
                catalog_name=_catalog, schema_name=_schema
            ):
                _w.registered_models.update(full_name=_model.full_name, owner=_owner)

            _w.schemas.update(full_name=f'{_catalog}.{_schema}', owner=_owner)

        def _catalog_set_ownerships(
            _w: WorkspaceClient, _catalog: str, _owner: str, _recurse: bool = False
        ):

            if _recurse:
                for _schema in _w.schemas.list(catalog_name=_catalog):
                    if _schema.owner != 'System user':
                        _schema_set_ownerships(_w, _catalog, _schema.name, _owner)

            _w.catalogs.update(_catalog, owner=_owner)

        summary = self.w.metastores.summary()
        owner = summary.owner
        default_catalog = self.default_catalog

        # 1. create all the things

        # 1a. default catalog
        try:
            res = self.w.catalogs.create(default_catalog)
            self.logger.info(
                f"initializing metastore; created catalog {default_catalog}"
            )

        except BadRequest as BE:
            self.logger.info(f"catalog {default_catalog} already exists, {BE}")

        # 1b. ops schema
        try:
            self.w.schemas.create(name='ops', catalog_name=default_catalog)
            self.logger.info(f"created schema {default_catalog}.ops")
        except BadRequest:
            self.logger.info(f"schema {default_catalog}.ops already exists")

        # 1c. meta table and filter function - the metadata table is a row-filtered table that will be filtered based
        # on the 'owner' column versus who is running the query

        # note: APIs for creating functions etc are experimental and/or non-existent at this time (and they're also
        # exceptionally hard to use), so let's just do it in SQL
        # this row filter is returning TRUE if the caller is a metastore admin (check user or group membership);
        # otherwise, return TRUE if the caller is (or is a group member) of the principal listed in the owner field
        # note that {owner} is referencing the metastore owner set up earlier, while owner is referencing the table
        # column by the same name
        # self.sql(statement=f"""
        # CREATE OR REPLACE FUNCTION {default_catalog}.ops.meta_filter(owner STRING)
        # RETURN IF(
        #   current_user() = '{owner}' OR is_account_group_member('{owner}'),
        #   TRUE,
        #   current_user() = owner OR is_account_group_member(owner)
        # )
        # """)
        self.sql(
            statement=f"""
        CREATE FUNCTION IF NOT EXISTS {default_catalog}.ops.meta_filter(owner STRING)
        RETURN IF(
          current_user() = owner OR current_user() = '{owner}',
          TRUE,
          is_account_group_member(owner) OR is_member(owner) OR is_account_group_member('{owner}')
        )
        """
        )

        self.sql(
            statement=f"""
        CREATE TABLE IF NOT EXISTS {default_catalog}.ops.meta (owner STRING, object STRING, key STRING, value STRING)
        WITH ROW FILTER {default_catalog}.ops.meta_filter ON (owner)
            """
        )
        self.logger.info(
            f"created table {default_catalog}.ops.meta with fine-grained access control"
        )

        # 2. configure permissions on all things

        # 2a. grant use of default catalog to all
        self.w.grants.update(
            full_name=default_catalog,
            securable_type=SecurableType.CATALOG,
            changes=[
                PermissionsChange(
                    add=[Privilege.USE_CATALOG], principal='account users'
                )
            ],
        )

        # 2b. grant use of ops schema to all
        self.w.grants.update(
            full_name=f'{default_catalog}.ops',
            securable_type=SecurableType.SCHEMA,
            changes=[
                PermissionsChange(add=[Privilege.USE_SCHEMA], principal='account users')
            ],
        )

        # 2c. grant SELECT on metadata table to all (row filtering will ensure that a user only sees metadata they own)
        try:
            self.w.grants.update(
                full_name=f'{default_catalog}.ops.meta',
                securable_type=SecurableType.TABLE,
                changes=[
                    PermissionsChange(add=[Privilege.SELECT], principal='account users')
                ],
            )
        except Exception as e:
            self.logger.error(
                f"Failed to grant SELECT on ops.meta (table may not exist): {e}"
            )

        self.logger.info("configured permissions")

        # 3. configure ownerships of default catalog and contained "ops" schema
        _catalog_set_ownerships(self.w, default_catalog, owner)
        _schema_set_ownerships(self.w, default_catalog, 'ops', owner)

        self.logger.info(
            f"configured ownership of catalog '{default_catalog}' and schema 'meta' to {owner}"
        )

        # enable catalog creation if selected
        if metastore_config.get('enable_create_catalog', False):
            self.w.grants.update(
                full_name=summary.metastore_id,
                securable_type=SecurableType.METASTORE,
                changes=[
                    PermissionsChange(
                        add=[Privilege.CREATE_CATALOG], principal='account users'
                    )
                ],
            )

            self.logger.info(
                "enabled CREATE_CATALOG for all; this should only be enabled if you really need it"
            )

        for s in metastore_config.get('system_schemas', []):
            try:
                # at time of writing, SDK for this was not handling the "schema_name" arg properly... so we'll use
                # REST directly instead
                self.w.api_client.do(
                    method='PUT',
                    path=f'/api/2.1/unity-catalog/metastores/{summary.metastore_id}/systemschemas/{s}',
                )

                self.logger.info(f'enabled system schema {s}')

            except Exception as e:
                self.logger.error(f'error enabling system schema {s}: {str(e)}')

            try:
                self.try_until_succeeds(
                    fn=self.w.grants.update,
                    full_name=f'system.{s}',
                    securable_type=SecurableType.SCHEMA,
                    changes=[
                        PermissionsChange(
                            add=[Privilege.SELECT, Privilege.USE_SCHEMA],
                            principal='account users',
                        )
                    ],
                )

                self.logger.info(f"successfully granted access to system schema {s}")

            except:
                self.logger.error(f"failed to grant access to system schema {s}")

        # Marketplace access guard (default: False)
        enable_use_marketplace_assets = bool(
            metastore_config.get("enable_use_marketplace_assets", False)
        )

        # enable USE_MARKETPLACE_ASSETS for account users if provided in config
        if enable_use_marketplace_assets:
            try:
                self.try_until_succeeds(
                    fn=self.w.grants.update,
                    full_name=summary.metastore_id,
                    securable_type=SecurableType.METASTORE,
                    changes=[
                        PermissionsChange(
                            add=[Privilege.USE_MARKETPLACE_ASSETS],
                            principal='account users',
                        )
                    ],
                )

                self.logger.info("enabled USE_MARKETPLACE_ASSETS for account users")

            except:
                self.logger.error(
                    f"failed to grant USE_MARKETPLACE_ASSETS to account users"
                )

        else:
            # revoke access from account users
            try:
                self.try_until_succeeds(
                    fn=self.w.grants.update,
                    full_name=summary.metastore_id,
                    securable_type=SecurableType.METASTORE,
                    changes=[
                        PermissionsChange(
                            remove=[Privilege.USE_MARKETPLACE_ASSETS],
                            principal='account users',
                        )
                    ],
                )

                self.logger.info(
                    "successfully revoked USE_MARKETPLACE_ASSETS from account users"
                )

            except:
                self.logger.error(
                    f"failed to revoke USE_MARKETPLACE_ASSETS from account users"
                )

        marketplace: list[Dict] = self.course_config.get('marketplace', []).copy()
        datasets: list[Dict] = self.course_config.get('datasets', [])

        self.logger.info("checking for datasets")

        for dataset in datasets:
            if 'name' not in dataset:
                self.logger.error(
                    f'encountered dataset without a specification for name; skipping'
                )
                continue
            elif 'version' not in dataset:
                self.logger.error(
                    f'dataset {dataset["name"]} does not include a version; skipping'
                )
                continue

            m = {
                'dataset': dataset['name'],
                'dataset_version': dataset['version'],
                'schemas': [dataset['version']],
                'catalog': dataset.get(
                    'catalog', f'{default_catalog}_{dataset["name"]}'
                ),
            }

            if 'listing_id' in dataset:
                m['listing_id'] = dataset['listing_id']
            elif 'listing_name' in dataset:
                m['listing_name'] = dataset['listing_name']
                m['provider_name'] = 'Databricks'
            else:
                self.logger.error(
                    f'dataset {dataset["name"]} does not include a listing_id or listing_name; skipping'
                )
                continue

            self.logger.info(
                f'adding dataset {dataset["name"]} to the list of Marketplace assets to install'
            )
            marketplace.append(m)

        if marketplace:

            self.logger.info("preparing to install items from Marketplace")

            cached_provider_ids = {}
            metadata = {}

            for listing in marketplace:

                # install listing only if it isn't already installed (we test this by looking for the existence of the
                # target catalog)

                self.logger.info(
                    f'processing item {listing.get("listing_id", listing.get("listing_name"))}'
                )

                if 'listing_id' in listing:
                    # if listing is specified by id, we simply need to get the info for that id
                    try:
                        listing_info = self.w.consumer_listings.get(
                            listing['listing_id']
                        ).listing
                    except (NotFound, BadRequest):
                        self.logger.error(
                            f'listing {listing["listing_id"]} not found - skipping'
                        )
                        continue
                elif 'listing_name' in listing:
                    # otherwise, search for the listing by name, but we're going to filter on provider
                    if 'provider_id' in listing:
                        # if provider_id is specified directly, use it
                        provider_id = listing['provider_id']
                    else:
                        # search for the provider by name (assume dbacademy as default provider if not specified)
                        provider_name = listing.get('provider_name', 'Databricks')

                        if provider_name in cached_provider_ids:
                            # if we already cached the id for the named provider, use that
                            provider_id = cached_provider_ids[provider_name]
                        else:
                            # otherwise, fetch id for named provider
                            try:
                                provider_id = next(
                                    p.id
                                    for p in self.w.consumer_providers.list()
                                    if p.name == provider_name
                                )
                                cached_provider_ids[provider_name] = provider_id
                                self.logger.info(
                                    f'found provider {provider_name} with id {provider_id}'
                                )

                            except StopIteration:
                                self.logger.error(
                                    f'could not find provider {provider_name}; skipping'
                                )
                                continue

                    # get listing info, applying provider_id and is_free as filter criteria (this dramatically
                    # improves execution time for this call)
                    try:
                        listing_info = next(
                            item
                            for item in self.w.consumer_listings.list(
                                provider_ids=[provider_id], is_free=True
                            )
                            if item.summary.name == listing['listing_name']
                        )
                    except StopIteration:
                        self.logger.error(
                            f'listing {listing["listing_name"]} by {provider_id} not found; skipping'
                        )
                        continue

                    self.logger.info(
                        f'resolved {listing["listing_name"]}; consider using listing_id={listing_info.id} instead)'
                    )
                else:
                    self.logger.error(
                        'no listing_id or listing_name specified; skipping'
                    )
                    continue

                # with listing info in hand, we have all the info we need to install it
                # use 'catalog' from the config, if specified; otherwise combine default catalog name with listing name

                install_catalog = listing.get(
                    'catalog',
                    f'{default_catalog}_{self.safe_name(listing_info.summary.name)}',
                )

                try:
                    self.w.consumer_installations.create(
                        listing_id=listing_info.id,
                        catalog_name=install_catalog,
                        share_name=listing_info.summary.share.name,
                        # TODO engg says this is OK... but I have concerns that someday they may update the version
                        accepted_consumer_terms=ConsumerTerms(version='2023-01'),
                    )

                    self.logger.info(
                        f'installed {listing_info.summary.share.name} to catalog {install_catalog}'
                    )
                except AlreadyExists:
                    self.logger.info(
                        f'share {listing_info.summary.share.name} is already installed to catalog {install_catalog}'
                    )

                # propagate listing description to the catalog
                if listing_info.detail.description:
                    self.w.catalogs.update(
                        name=install_catalog, comment=listing_info.detail.description
                    )

                # grant privileges at the catalog level (only include USE SCHEMA if no specific schemas are specified -
                # if they are, then we'll grant them individually)

                privileges = [
                    Privilege.SELECT,
                    Privilege.EXECUTE,
                    Privilege.READ_VOLUME,
                    Privilege.USE_CATALOG,
                ]
                if 'schemas' not in listing:
                    privileges.append(Privilege.USE_SCHEMA)
                    self.logger.info(
                        f'granting read-only privileges to all on catalog {install_catalog}'
                    )

                self.w.grants.update(
                    full_name=install_catalog,
                    securable_type=SecurableType.CATALOG,
                    changes=[
                        PermissionsChange(add=privileges, principal='account users')
                    ],
                )

                # if schemas are specified, grant USE SCHEMA on specified ones

                if 'schemas' in listing:
                    self.logger.info(
                        f'restricting access to the following schemas {listing["schemas"]}'
                    )

                    for schema in listing['schemas']:
                        try:
                            self.try_until_succeeds(
                                fn=self.w.grants.update,
                                full_name=f"{install_catalog}.{schema}",
                                securable_type=SecurableType.SCHEMA,
                                changes=[
                                    PermissionsChange(
                                        add=[Privilege.USE_SCHEMA],
                                        principal='account users',
                                    )
                                ],
                            )

                            self.logger.info(
                                f"successfully granted access to schema {schema}"
                            )

                        except:
                            self.logger.error(
                                f"failed to grant access to schema {schema}"
                            )

                # recursively set ownership on everything in installed catalog
                _catalog_set_ownerships(self.w, install_catalog, owner, True)
                self.logger.info(
                    f'set ownership of catalog {install_catalog} and all contents to {owner}'
                )

                if 'dataset' in listing:

                    # add the dataset to the metadata:
                    # datasets.<name> = catalog.schema of where to find assets
                    # paths.datasets.<name> = base path (if volumes are present)
                    metadata[f'datasets.{listing["dataset"]}'] = (
                        f'{install_catalog}.{listing["dataset_version"]}'
                    )

                    try:
                        # see if we have at least one volume in the dataset
                        next(
                            self.w.volumes.list(
                                catalog_name=install_catalog,
                                schema_name=listing["dataset_version"],
                            )
                        )

                        # if there is at least one volume, then set paths.datasets.<name> metadata
                        metadata[f'paths.datasets.{listing["dataset"]}'] = (
                            f'/Volumes/{install_catalog}/{listing["dataset_version"]}'
                        )

                    except StopIteration:
                        # no volumes
                        pass

            if metadata:
                self.user_putmetadata(principal='account users', records_for=metadata)

    def workspace_init(self):

        self.logger.info(
            f'initializing workspace for {self.platform.get_platform_name()}'
        )

        self._workspace_id = self.w.get_workspace_id()

        if self.update_config_tags:
            # store config in workspace custom tags
            workspace = self.a.workspaces.get(self.workspace_id)

            # update custom tags
            self.a.workspaces.update(
                workspace_id=workspace.workspace_id,
                custom_tags=config_save_to_tags(
                    self.course_config,
                    existing_tags=workspace.custom_tags,
                    tag_max_len=255 if workspace.cloud != 'gcp' else 63,
                ),
            )

            self.logger.info(f'saved config to workspace custom tags')

        # set up the metastore
        self.metastore_create()

        # delete "starter" warehouses
        for wh in self.w.warehouses.list():
            if wh.id != self._warehouse:
                self.logger.info(f'deleting warehouse {wh.name} ({wh.id})')
                self.w.warehouses.delete(wh.id)

        if 'course_path' in self.course_config:

            # copy files to Databricks from ./files (if subdir is present)
            file_src = f'{self.course_config["course_path"]}/files'

            if os.path.isdir(file_src):
                self.dir_to_db(file_src)

            # unpack files*.zip to Databricks (if any such files are present)
            for f in filter(
                lambda x: x.is_file()
                and x.name.lower().startswith('files')
                and x.name.lower().endswith('.zip'),
                os.scandir(self.course_config["course_path"]),
            ):
                self.zip_to_db(f.path)

        if 'data_file_path' in self.course_config:
            self._unpack_datafiles_s3_to_db(self.course_config['data_file_path'])

        if self.course_config.get('enable_file_access', False):
            self.logger.info('granting SELECT on ANY FILE to everyone')
            self.sql('GRANT SELECT ON ANY FILE TO users')

        if self.course_config.get('enable_dbfs', False):
            self.logger.info('enabling DBFS access')
            self.enable_dbfs()

            if 'course_path' in self.course_config:

                # copy DBFS contents if present
                dbfs_src = f'{self.course_config["course_path"]}/dbfs'

                if os.path.isdir(dbfs_src):
                    self.dir_to_dbfs(dbfs_src)

        # many courses rely on ability to create tokens
        if self.course_config.get('enable_tokens', True):
            self.enable_tokens()

        # secrets
        if 'secrets' in self.course_config:
            for scope in self.course_config['secrets']:
                self.logger.info(f'creating secret scope {scope}')
                self.secrets_put(
                    scope=scope, secrets=self.course_config['secrets'][scope]
                )

        # cluster policies
        if 'cluster_policies' in self.course_config:
            self.cluster_policies_create()

        # deferred setup of metastore to avoid cache coherency issues when assigning a metastore to a workspace
        self.metastore_setup()

        setup_parms = self.course_config.get('workspace_setup', {})
        setup_base = self.course_config.get('course_path')

        if setup_parms and setup_base:
            self.run_setup(parameters=setup_parms, src_base=setup_base)

    # called when the workspace is being destroyed, giving us the opportunity to reap resources tied to
    # that workspace (or users still in the workspace) that live outside the workspace (metastore, account)
    def workspace_destroy(self):

        self.logger.info('tearing down workspace')

        try:
            metastore = self.w.metastores.summary()
        except NotFound:
            # if the metastore isn't there, we won't be able to do much here anyway
            self.logger.error(f'metastore has been removed from the workspace')
            return

        # if number of metastore assignments < 2, then this workspace is the last or only one currently assigned to
        # it, which means we should drop it too
        if (
            len([x for x in self.a.metastore_assignments.list(metastore.metastore_id)])
            < 2
        ):
            drop_metastore = True
        else:
            drop_metastore = False

        # consult metadata table for any remaining users; since each user has a metadata entry for their username,
        # we can just get the value field where key == 'username'
        try:
            user_records = self.sql(
                f"SELECT value FROM {self.default_catalog}.ops.meta WHERE key = 'username'"
            )
            active_users = (
                [r[0] for r in user_records] if user_records is not None else []
            )
        except:
            active_users = []

        if active_users:
            self.logger.info(
                f'there are still {len(active_users)} in this workspace; will reap them now'
            )

            # for any users remaining in the workspace, clean up resources that won't go away with the workspace
            for user in active_users:
                user_metadata = self.user_getmetadata(user)
                self.reap_account_resources(user, user_metadata)
                if not drop_metastore:
                    self.reap_metastore_resources(user, user_metadata)
        else:
            self.logger.info('there are no active users to reap')

        if drop_metastore:
            self.a.metastores.delete(metastore_id=metastore.metastore_id, force=True)
            self.logger.info(
                f'deleted metastore {metastore.name} because it is not referenced by other workspaces'
            )

    # get one or more metadata related to a specific principal
    def user_getmetadata(self, principal: str, key: str = None):

        # if key specified, return a string for the value
        if key:
            records = self.sql(
                f"""
            SELECT value FROM {self.default_catalog}.ops.meta
            WHERE '{principal}' IN (owner,object) AND key='{key}'
            """
            )

            return records[0][0] if records else None

        # otherwise, return a dict
        records = self.sql(
            f"""
        SELECT key,value FROM {self.default_catalog}.ops.meta
        WHERE '{principal}' IN (owner,object)
        """
        )

        values = {}

        if records:

            for record in records:
                values[record[0]] = record[1]

        return values

    # write metadata records related to a specific principal
    # records_for: records for use by the principal (owner=principal, object=null)
    # records_about: records for use by admin (owner=current, object=principal)
    # principal can see records_for but not records_about
    def user_putmetadata(
        self, principal: str, records_for: dict = None, records_about: dict = None
    ):

        if records_for:
            self.sql(
                "INSERT INTO {}.ops.meta REPLACE WHERE owner='{}' AND key in ({}) VALUES {}".format(
                    self.default_catalog,
                    principal,
                    ','.join([f"'{k}'" for k in records_for.keys()]),
                    ','.join(
                        [
                            f"('{principal}',null,'{k}','{v}')"
                            for k, v in records_for.items()
                        ]
                    ),
                )
            )

        if records_about:
            self.sql(
                "INSERT INTO {}.ops.meta REPLACE WHERE owner='{}' AND object='{}' AND key in ({}) VALUES {}".format(
                    self.default_catalog,
                    self.username,
                    principal,
                    ','.join([f"'{k}'" for k in records_about.keys()]),
                    ','.join(
                        [
                            f"('{self.username}','{principal}','{k}','{v}')"
                            for k, v in records_about.items()
                        ]
                    ),
                )
            )

    def user_clearmetadata(self, principal: str):

        self.sql(
            f"DELETE FROM {self.default_catalog}.ops.meta WHERE '{principal}' IN (owner,object)"
        )

    # part 1 of user env setup - parts that can be done early to prepare for the arrival of a user (but we don't yet
    # know when, or if, that user is actually arriving)
    def lab_setup(self, user: str):

        self.logger.info(f'lab_setup for user {user}')

        # deploy models if specified
        if 'models' in self.course_config:
            self.ml_deploy_models(self.course_config['models'])

    # part 2 of user env setup - parts that should be done once we know user is arriving
    # - a schema in the default catalog, to which user has ALL PRIVILEGES
    # - a volume in the ops schema, to which user has ALL PRIVILEGES (this is user's working dir)
    def user_setup(self, user: str):

        self.logger.info(f'user_setup for user {user}')

        metadata_about_user = {}
        metadata_for_user = {}
        metadata = self.user_getmetadata(user) or {}

        if metadata:
            self.logger.warning(
                f'user {user} already has metadata records (failed earlier setup or terminate?)'
            )
            for k in metadata:
                self.logger.info(f'  {k} -> {metadata[k]}')

        user_config = self.course_config.get('user_config', {})
        user_schema = metadata.get('user_schema', False)

        pseudonym = metadata.get('pseudonym')

        if not pseudonym:

            # I'm going to throw some comments here to explain the thought process behind the next few lines.
            # Even though the odds are astronomical that two users in the same metastore would ever draw the
            # same random name, ya never know. Also, we could be executing through this same block of code at
            # the same time, against the same metastore, in two completely different jobs. So here's what I'm
            # doing to make things as atomic/consistent as possible:
            # 1. pick a fake name.
            # 2. insert it into the metadata table
            # 3. run a count of the entries in the table with same fake name. if/while that count > 1
            #    - pick a new fake name
            #    - update (not insert) the record in the metadata table, and circle back to check again
            # Coming out of this, we have a value guaranteed to be unique in the metastore, and therefore
            # unique in the workspace too. But not necessarily guaranteed to be unique in the account.
            # POTENTIAL ALTERNATE APPROACH TO CONSIDER
            # Guaranteeing account uniqueness (and hence metastore and workspace) uniqueness in theory is pretty
            # easy, for example by using the SCIM API to create a group with the fake name. That's an atomic
            # operation that will fail if the named group already exists. And in cases where we need a secondary
            # principal, creating that named group is the first step of the process anyway. However, I'm hesitant
            # to do this by default due to the group limit of 5K/account. Not sure how many users we can expect in
            # the account at any given time, so it seems dangerous to subject the system to an operational limit
            # like that.

            pseudonym = self._get_name(user, DBAcademyNamingScheme.RANDOM)
            self.sql(
                "INSERT INTO {}.ops.meta (owner,key,value) VALUES ('{}','pseudonym','{}')".format(
                    self.default_catalog, user, pseudonym
                )
            )
            # self.sql(f"""
            # INSERT INTO {self.default_catalog}.ops.meta (owner,key,value)
            # VALUES ('{user}','pseudonym','{pseudonym}')
            # """)

            # while count of fake name entries with the same value > 1...
            while (
                int(
                    self.sql(
                        f"""
            SELECT COUNT(*) FROM {self.default_catalog}.ops.meta
            WHERE key='pseudonym' AND value='{pseudonym}'
            """
                    )[0][0]
                )
                > 1
            ):
                # pick a new fake name, and update the record we wrote
                new_pseudonym = self._get_name(user, DBAcademyNamingScheme.RANDOM)
                self.sql(
                    f"""
                UPDATE {self.default_catalog}.ops.meta
                SET value='{new_pseudonym}'
                WHERE owner='{user}' AND key='pseudonym'
                """
                )
                pseudonym = new_pseudonym

            self.logger.info(f'generated fake name "{pseudonym}" for user {user}')

        metadata_for_user['username'] = user

        if 'catalog' in user_config:
            # need a catalog for the user

            catalog = self.safe_name(
                self._get_name(
                    username=user,
                    naming_scheme=user_config['catalog'],
                    _random_name=pseudonym,
                )
            )

            user_catalog = (
                catalog if catalog != self.safe_name(user_config['catalog']) else None
            )

            try:
                self.w.catalogs.create(catalog)

                if user_catalog:
                    self.logger.info(f'created catalog {user_catalog} for user {user}')
                else:
                    self.logger.info(f'created common catalog {catalog}')

            except BadRequest:
                # catalog already exists - if it's a user catalog this ought not to have happened
                if user_catalog:
                    self.logger.warning(f'catalog {catalog} already exists')

            # if it's a user catalog, let them have ALL PRIVILEGES; otherwise only grant USE and CREATE
            if user_catalog:

                metadata_about_user['user_catalog'] = user_catalog
                grantee = user

                if user_config.get('manage_catalog', False):
                    privileges = [Privilege.ALL_PRIVILEGES, Privilege.MANAGE]
                else:
                    privileges = [Privilege.ALL_PRIVILEGES]
            else:
                privileges = [Privilege.USE_CATALOG, Privilege.CREATE_SCHEMA]
                # grantee = 'account users'
                grantee = user

            self.w.grants.update(
                full_name=catalog,
                securable_type=SecurableType.CATALOG,
                changes=[PermissionsChange(add=privileges, principal=grantee)],
            )

            if 'schema' in user_config:
                schema = self.safe_name(
                    self._get_name(
                        username=user,
                        naming_scheme=user_config['schema'],
                        _random_name=pseudonym,
                    )
                )

                user_schema = (
                    schema if schema != self.safe_name(user_config['schema']) else None
                )
            else:
                schema = None
        else:
            catalog = self.default_catalog
            schema = self.safe_name(
                self._get_name(
                    username=user,
                    naming_scheme=user_config.get(
                        'schema', DBAcademyNamingScheme.RANDOM
                    ),
                    _random_name=pseudonym,
                )
            )

            user_schema = (
                schema
                if schema != self.safe_name(user_config.get('schema', ''))
                else None
            )

        metadata_for_user['catalog_name'] = catalog

        # create schema
        if schema:

            # log that we're creating a schema unique to this user (so we can destroy it in lab_end)

            try:
                self.w.schemas.create(name=schema, catalog_name=catalog)
                if user_schema:
                    self.logger.info(f'created schema {user_schema} for user {user}')
                else:
                    self.logger.info(f'created common schema {schema}')

            except BadRequest:
                # schema already exists - if it's a user schema this ought not to have happened
                if user_schema:
                    self.logger.warning(f'schema {schema} already exists')

            # if it's a user schema, give ALL PRIVILEGES; otherwise if it's a shared schema, only grant USE and CREATE

            if user_schema:
                metadata_about_user['user_schema'] = f'{catalog}.{user_schema}'
                grantee = user

                if user_config.get('manage_schema', False):
                    privileges = [Privilege.ALL_PRIVILEGES, Privilege.MANAGE]
                else:
                    privileges = [Privilege.ALL_PRIVILEGES]
            else:
                # grantee = 'account users'
                grantee = user
                privileges = [
                    Privilege.USE_SCHEMA,
                    Privilege.CREATE_TABLE,
                    Privilege.CREATE_VOLUME,
                    Privilege.CREATE_FUNCTION,
                    Privilege.CREATE_MODEL,
                    Privilege.CREATE_MATERIALIZED_VIEW,
                ]

            self.w.grants.update(
                full_name=f'{catalog}.{schema}',
                securable_type=SecurableType.SCHEMA,
                changes=[PermissionsChange(add=privileges, principal=grantee)],
            )

            metadata_for_user['schema_name'] = schema

        # create volume in the ops schema, to provide a file system implementing the user's workdir
        # maintaining the volumes in the ops schema relieves clutter in users' working schemas

        volume_name = self.safe_name(user)
        full_volume_name = f'{self.default_catalog}.ops.{volume_name}'

        try:
            self.w.volumes.create(
                catalog_name=self.default_catalog,
                schema_name='ops',
                name=volume_name,
                volume_type=VolumeType.MANAGED,
            )

            self.logger.info(f'created volume {full_volume_name} for user {user}')

        except ResourceAlreadyExists:
            # volume already exists - shouldn't happen
            self.logger.warning(f'volume {full_volume_name} already exists')

        # grant user ALL PRIVILEGES on their volume. they'll be able to do anything with their volume, but because
        # they don't own it, they won't be able to drop it or change privileges or ownership
        self.w.grants.update(
            full_name=full_volume_name,
            securable_type=SecurableType.VOLUME,
            changes=[PermissionsChange(add=[Privilege.ALL_PRIVILEGES], principal=user)],
        )

        metadata_about_user['volume'] = full_volume_name
        metadata_for_user['paths.working_dir'] = (
            f'/Volumes/{self.default_catalog}/ops/{volume_name}'
        )

        if 'cluster_name' in metadata:
            self.cluster_start_or_create(
                principal=user, cluster_name=metadata['cluster_name']
            )
        else:
            info = self.cluster_start_or_create(principal=user, _random_name=pseudonym)

            if info:
                metadata_for_user['cluster_name'] = info[1]

                if info[0]:
                    metadata_about_user['user_cluster'] = info[2]

        if 'warehouse_name' in metadata:
            self.warehouse_start_or_create(
                principal=user, warehouse_name=metadata['warehouse_name']
            )
        else:
            info = self.warehouse_start_or_create(
                principal=user, _random_name=pseudonym
            )

            if info:
                metadata_for_user['warehouse_name'] = info[1]

                if info[0]:
                    metadata_about_user['user_warehouse'] = info[2]

        # create vector search endpoints if specified
        if 'shared_vector_search_endpoints' in self.course_config:
            self.vector_search_endpoints_create(
                self.course_config['shared_vector_search_endpoints']
            )

        if user_config.get('secondary', False):
            if 'iam.secondary' not in metadata:
                metadata_for_user['iam.secondary'] = self.iam_create_secondary(
                    primary=user, secondary=pseudonym
                )

        self.user_putmetadata(
            user, records_for=metadata_for_user, records_about=metadata_about_user
        )

        # determine redirect url
        redirect_url = self.w.config.host

        if 'content' in self.course_config:
            main_notebook = self.workspace_import(
                src_parms=self.course_config['content'],
                src_base=self.course_config['course_path'],
                dst_base=f'/Users/{user}',
                overwrite=True,
                dbfs=True,
            )

            if main_notebook:
                redirect_url = self.workspace_get_url(notebook_path=main_notebook)

        if 'entry' in self.course_config:
            redirect_url = self.workspace_get_url(path=self.course_config['entry'])

        return redirect_url

    def user_setup_resume(self, user: str):

        self.logger.info(f'user_setup_resume for user {user}')

        user_metadata = self.user_getmetadata(user)

        if not user_metadata:
            self.logger.error(f'user {user} has no metadata')
            return

        self.logger.info(f'metadata for user {user}')
        for k in user_metadata:
            self.logger.info(f'  {k} -> {user_metadata[k]}')

        if 'cluster_name' in user_metadata:
            self.logger.info(f'starting cluster {user_metadata["cluster_name"]}')

            self.cluster_start_or_create(
                principal=user, cluster_name=user_metadata.get('cluster_name')
            )

        if 'warehouse_name' in user_metadata:
            self.logger.info(f'starting warehouse {user_metadata["warehouse_name"]}')

        self.warehouse_start_or_create(
            principal=user, warehouse_name=user_metadata.get('warehouse_name')
        )

        redirect_url = self.w.config.host

        if 'content' in self.course_config:
            main_notebook = self.workspace_import(
                src_parms=self.course_config['content'],
                src_base=self.course_config['course_path'],
                dst_base=f'/Users/{user}',
                overwrite=False,
                dbfs=False,
            )

            if main_notebook:
                redirect_url = self.workspace_get_url(notebook_path=main_notebook)
                self.logger.info(
                    f'calculated url for notebook {main_notebook} is {redirect_url}'
                )

        if 'entry' in self.course_config:
            redirect_url = self.workspace_get_url(path=self.course_config['entry'])
            self.logger.info(f'redirect url as set by main config is {redirect_url}')

        return redirect_url

    # "pause" a user's session (stop any resources incurring cost; but do no cleanup as user could be back)
    def lab_end_stop(self, user: str):

        self.logger.info(f'lab_end_stop for user {user}')

        user_metadata = self.user_getmetadata(user)

        if not user_metadata:
            self.logger.error(f'user {user} has no metadata')
            return

        self.logger.info(f'metadata for user {user}')
        for k in user_metadata:
            self.logger.info(f'  {k} -> {user_metadata[k]}')

        if 'user_cluster' in user_metadata:
            try:
                self.logger.info(f'stopping cluster {user_metadata["cluster_name"]}')
                self.w.clusters.delete(user_metadata['user_cluster'])

            except InvalidParameterValue:
                self.logger.warning(
                    f'cluster {user_metadata["cluster_name"]} ({user_metadata["user_cluster"]}) not found'
                )

        if 'user_warehouse' in user_metadata:
            try:
                self.logger.info(
                    f'stopping warehouse {user_metadata["warehouse_name"]}'
                )
                self.w.warehouses.stop(user_metadata['user_warehouse'])

            except InvalidParameterValue:
                self.logger.warning(
                    f'warehouse {user_metadata["warehouse_name"]} ({user_metadata["user_warehouse"]}) not found'
                )

        # stop unmanaged resources

        # clusters
        for c in self.w.clusters.list():
            if c.creator_user_name == user:
                self.w.clusters.delete(c.cluster_id)
                self.logger.info(f'stopped user-created cluster {c.cluster_name}')

        # warehouses
        for wh in self.w.warehouses.list():
            if wh.creator_name == user:
                self.w.warehouses.stop(wh.id)
                self.logger.info(f'stopped user-created warehouse {wh.name}')

        # apps
        try:
            app_list = self.w.api_client.do('GET', '/api/2.0/apps')
            apps = app_list.get("apps", [])

            if not apps:
                self.logger.info("No apps found in workspace.")
            else:
                found = False
                for app in apps:
                    if app.get("creator") == user:
                        app_name = app.get("name")
                        if app_name:
                            found = True
                            self.w.api_client.do(
                                'POST', f'/api/2.0/apps/{app_name}/stop'
                            )
                            self.logger.info(f"Stopped app: {app_name}")

                if not found:
                    self.logger.info(f"No apps found for creator: {user}")

        except Exception as e:
            self.logger.warning(f"Failed to stop apps for user {user}: {e}")

    # "master reaper" - reap all resources associated with a user. called when user explicitly ends lab or
    # user hits max time allotment
    # - workspace resources (compute, folders, workflows, ml resources, etc)
    # - metastore resources (managed catalog/schema, user-created catalogs or schemas, ops.volume, metadata rows
    # - account resources (secondary users, etc)
    def lab_end_terminate(self, user: str):

        self.logger.info(f'lab_end_terminate for user {user}')

        user_metadata = self.user_getmetadata(user)

        if not user_metadata:
            self.logger.error(f'user {user} has no metadata')
            return

        self.logger.info(f'metadata for user {user}')
        for k in user_metadata:
            self.logger.info(f'  {k} -> {user_metadata[k]}')

        self.reap_workspace_resources(user, user_metadata=user_metadata)
        self.reap_account_resources(user, user_metadata=user_metadata)
        self.reap_metastore_resources(user, user_metadata=user_metadata)

    # Database Instances (Lakebase Provisioned)
    def cleanup_user_database_instances(self, user: str):
        try:
            instance_list = self.w.api_client.do('GET', '/api/2.0/database/instances')
            instances = instance_list.get("database_instances", [])

            if not instances:
                self.logger.info("No database instances found in workspace.")
            else:
                found = False
                for inst in instances:
                    if inst.get("creator") == user:
                        name = inst.get("name")
                        if name:
                            found = True
                            self.w.api_client.do(
                                method="DELETE",
                                path=f"/api/2.0/database/instances/{name}",
                            )
                            self.logger.info(
                                f"Deleted provisioned database instance: {name}"
                            )

                if not found:
                    self.logger.info(f"No database instances found for owner: {user}")

        except Exception as e:
            self.logger.warning(
                f"Failed to delete database instances for user {user}: {e}"
            )

    # Lakebase Autoscaling Projects
    def cleanup_postgres_projects(self, user: str):
        try:
            project_list = self.w.api_client.do('GET', '/api/2.0/postgres/projects')
            projects = project_list.get("projects", [])

            if not projects:
                self.logger.info("No lakebase projects found in workspace.")
            else:
                found = False
                for proj in projects:
                    owner = proj.get("status", {}).get("owner")
                    if owner == user:
                        name = proj.get("name")  # format: "projects/{id}"
                        if name:
                            found = True
                            self.w.api_client.do(
                                method="DELETE",
                                path=f"/api/2.0/postgres/{name}",
                            )
                            self.logger.info(
                                f"Deleted lakebase autoscaling project: {name}"
                            )

                if not found:
                    self.logger.info(f"No lakebase projects found for creator: {user}")

        except Exception as e:
            self.logger.warning(
                f"Failed to delete lakebase projects for user {user}: {e}"
            )

    def reap_workspace_resources(self, user: str, user_metadata: dict):

        self.logger.info(f'reaping workspace resources for user {user}')

        # clusters (managed and unmanaged)
        if 'user_cluster' in user_metadata:
            try:
                self.w.clusters.permanent_delete(user_metadata['user_cluster'])
                self.logger.info(f'deleted cluster {user_metadata["cluster_name"]}')
            except InvalidParameterValue:
                self.logger.warning(
                    f'cluster {user_metadata["cluster_name"]} ({user_metadata["user_cluster"]}) not found'
                )

        for c in filter(lambda x: x.creator_user_name == user, self.w.clusters.list()):
            self.w.clusters.permanent_delete(c.cluster_id)
            self.logger.info(f'deleted user-created cluster {c.cluster_name}')

        # warehouses (managed and unmanaged)
        if 'user_warehouse' in user_metadata:
            try:
                self.w.warehouses.delete(user_metadata['user_warehouse'])
                self.logger.info(f'deleted warehouse {user_metadata["warehouse_name"]}')

            except InvalidParameterValue:
                self.logger.warning(
                    f'warehouse {user_metadata["warehouse_name"]} ({user_metadata["user_warehouse"]}) not found'
                )

        for w in filter(lambda x: x.creator_name == user, self.w.warehouses.list()):
            self.w.warehouses.delete(w.id)
            self.logger.info(f'deleted user-created warehouse {w.name}')

        #  secret scope
        if 'secrets' in user_metadata:
            try:
                self.w.secrets.delete_scope(user_metadata['secrets'])
                self.logger.info(f'deleted secret scope {user_metadata["secrets"]}')

            except ResourceDoesNotExist:
                self.logger.warning(
                    f'secret scope {user_metadata["secrets"]} does not exist'
                )

        # Agent Bricks (must be deleted before their associated endpoints)
        try:
            tiles = self.list_all_tiles(user)
            self.logger.info(f'Fetched {len(tiles)} tile(s) for user: {user}')
            if not tiles:
                self.logger.info(f'No tiles found. Nothing to delete for user {user}.')
            else:
                for tile in tiles:
                    tile_id = tile.get('tile_id')
                    self.delete_tile(tile_id)
                    self.logger.info(f'Deleted tile: {tile_id}')
        except Exception as e:
            self.logger.warning(
                f'Failed to delete agent bricks for user {user}: {e}', exc_info=True
            )

        # model serving endpoints (deleted after tiles to avoid conflicts)
        for s in filter(lambda x: x.creator == user, self.w.serving_endpoints.list()):
            self.w.serving_endpoints.delete(s.name)
            self.logger.info(f'deleted model serving endpoint {s.name}')

        # jobs and runs
        for j in filter(lambda x: x.creator_user_name == user, self.w.jobs.list()):
            for r in self.w.jobs.list_runs(job_id=j.job_id):
                try:
                    # the cancel might not always be necessary but avoids potential issues trying to delete active runs
                    self.w.jobs.cancel_run_and_wait(r.run_id)
                    self.w.jobs.delete_run(r.run_id)
                except:
                    self.logger.warning(
                        f'failed to delete run {r.run_id} of {j.job_id}'
                    )

            self.w.jobs.delete(j.job_id)
            self.logger.info(f'deleted job {j.job_id}')

        # DLT pipelines
        for p in filter(
            lambda x: x.creator_user_name == user, self.w.pipelines.list_pipelines()
        ):
            self.w.pipelines.delete(p.pipeline_id)
            self.logger.info(f'deleted pipeline {p.name}')

        # apps
        try:
            app_list = self.w.api_client.do('GET', '/api/2.0/apps')
            apps = app_list.get("apps", [])

            if not apps:
                self.logger.info("No apps found in workspace.")
            else:
                found = False
                for app in apps:
                    if app.get("creator") == user:
                        app_name = app.get("name")
                        if app_name:
                            found = True
                            self.w.api_client.do('DELETE', f'/api/2.0/apps/{app_name}')
                            self.logger.info(f"Deleted app: {app_name}")

                if not found:
                    self.logger.info(f"No apps found for creator: {user}")

        except Exception as e:
            self.logger.warning(f"Failed to delete apps for user {user}: {e}")

        # Database Instances (Lakebase Provisioned)
        self.cleanup_user_database_instances(user)
        # Lakebase Autoscaling Projects
        self.cleanup_postgres_projects(user)

    def list_all_tiles(self, user: str):
        tiles_list = []
        next_page_token = None

        while True:
            try:
                # Build query parameters
                params = {}
                if next_page_token:
                    params['page_token'] = next_page_token

                # Call the tiles API with pagination
                response = self.w.api_client.do('GET', '/api/2.0/tiles', query=params)
                all_tiles = response.get("tiles", [])

                # Filter tiles by creator
                user_tiles = [tile for tile in all_tiles if tile.get("creator") == user]
                tiles_list.extend(user_tiles)

                # Check for next page
                next_page_token = response.get("next_page_token")
                if not next_page_token:
                    break

            except Exception as e:
                self.logger.warning(f"Failed to list tiles for user '{user}': {e}")
                break

        return tiles_list

    def delete_tile(self, tile_id: str):
        try:
            self.w.api_client.do('DELETE', f'/api/2.0/tiles/{tile_id}')
            self.logger.info(f"Deleted tile: {tile_id}")
        except Exception as e:
            self.logger.warning(f"Failed to delete tile '{tile_id}': {e}")

    # clean up metastore resources associated with a user
    def reap_metastore_resources(self, user: str, user_metadata: dict):

        self.logger.info(f'reaping metastore resources for user {user}')

        # managed catalog
        if 'user_catalog' in user_metadata:
            try:
                self.w.catalogs.delete(user_metadata['user_catalog'], force=True)
                self.logger.info(
                    f'dropped catalog {user_metadata["user_catalog"]} for user {user}'
                )

            except NotFound:
                self.logger.warning(
                    f'managed catalog {user_metadata["user_catalog"]} not found'
                )

        #  managed schema (in case it didn't happen to be in the managed catalog)
        if 'user_schema' in user_metadata:
            try:
                self.w.schemas.delete(
                    full_name=user_metadata['user_schema'], force=True
                )
                self.logger.info(
                    f'dropped schema {user_metadata["user_schema"]} for user {user}'
                )

            except NotFound:
                self.logger.warning(
                    f'managed schema {user_metadata["user_schema"]} not found'
                )

        #  working volume
        if 'volume' in user_metadata:
            try:
                self.w.volumes.delete(user_metadata['volume'])
                self.logger.info(
                    f'dropped volume {user_metadata["volume"]} for user {user}'
                )

            except ResourceDoesNotExist:
                self.logger.warning(f'volume {user_metadata["volume"]} not found')

        # catalogs (if CREATE_CATALOG enabled)
        for catalog in filter(lambda c: c.owner == user, self.w.catalogs.list()):
            # even metastore admins cannot drop catalogs they don't own; so we need to change ownership first
            self.w.catalogs.update(name=catalog.name, owner=self.username)
            self.w.catalogs.delete(name=catalog.name, force=True)
            self.logger.info(f'dropped user-created catalog {catalog.name}')

        #  delete user metadata
        self.user_clearmetadata(user)
        self.logger.info(f'removed metadata for user {user}')

    # clean up account resources associated with a user
    def reap_account_resources(self, user: str, user_metadata: dict):

        self.logger.info(f'reaping account resources for user {user}')

        #  secondary principal
        if 'iam.secondary' in user_metadata:
            self.iam_delete_secondary(name=user_metadata['iam.secondary'])

    def ml_deploy_models(self, models: list = None):

        if not models:
            return

        # TODO: this is based on the instructions generally provided for how to deploy models, but it's costly
        # because it always uses provisioned throughput. Consider rearchitecting the config for this so you can
        # do one of:
        # 1. "easy switch" for deploying using pay-per-token model
        # 2. "easy switch" for using optimization api for provisioned throughput
        # 3. Pass in parameters to have full control from config file of how model is deployed
        for m in models:

            model = m['model']
            name = m.get('name', model.split('.')[-1])
            version = m.get('version', 1)

            # TODO change from provisioned throughput to pay-per-token to save cost

            optimizable_info = self.w.api_client.do(
                'GET',
                f'/api/2.0/serving-endpoints/get-model-optimization-info/{model}/{version}',
            )

            if not optimizable_info.get('optimizable', False):
                raise ValueError(
                    f"model {model} is not eligible for provisioned throughput"
                )

            chunk_size = optimizable_info['throughput_chunk_size']

            try:
                self.w.serving_endpoints.create(
                    name=name,
                    config=EndpointCoreConfigInput(
                        served_entities=[
                            ServedEntityInput(
                                entity_name=model,
                                entity_version=version,
                                max_provisioned_throughput=3 * chunk_size,
                                min_provisioned_throughput=2 * chunk_size,
                            )
                        ]
                    ),
                )

                endpoint_id = self.w.serving_endpoints.get(name).id

                self.w.serving_endpoints.set_permissions(
                    serving_endpoint_id=endpoint_id,
                    access_control_list=[
                        ServingEndpointAccessControlRequest(
                            group_name='users',
                            permission_level=ServingEndpointPermissionLevel.CAN_QUERY,
                        )
                    ],
                )

            except ResourceAlreadyExists:
                self.logger.warning(f'model serving endpoint {name} already exists')
                pass

    # Creating a secondary principal for use by the primary. Main use case is for demonstrating access control.
    # ie we have a known secondary principal to which we can grant access, and (using that principal) can
    # validate access control. Here's how this function implements that:
    # 1. Create a group as the named entity (groups are easier to address in SQL than service principals, because
    # we can use easy-to-remember names, whereas in SQL/Python we must use the big ugly application id)
    # 2. Create a service principal within the group (we use an SP rather than a user, because we cannot create
    #    tokens on behalf of another user)
    # 3. Create a secret scope (named after the primary), provide READ access to primary
    # 4. Generate token on behalf of the service principal, store it in the secret scope (key named 'token')
    #
    # How to use it:
    # * As a data owner, grant access to the "secondary" (group); service principal automatically inherits the grant
    #   through group membership
    # * Connect (to a SQL warehouse using a SQL client of some sort) using the secondary (SP) token
    # * From there, access control can be demonstrated in real time

    def iam_create_secondary(self, primary: str, secondary: str):

        self.logger.info(
            f'creating a secondary principal named {secondary} for user {primary}'
        )

        service_principal = None
        group = None

        try:
            # create named group if it doesn't exist
            try:
                group = self.a.groups.create(display_name=secondary)
                self.logger.info(f'created group named {secondary}')

            except ResourceConflict:
                group = next(
                    filter(lambda x: x.display_name == secondary, self.a.groups.list())
                )
                self.logger.warning(f'group {group.display_name} already exists')

            for s in self.a.service_principals.list():
                if s.display_name == secondary:
                    service_principal = s
                    self.logger.warning(
                        f'service principal {service_principal.application_id} already exists with display name {secondary}'
                    )
                    break
            else:
                # create the named service principal
                service_principal = self.a.service_principals.create(
                    display_name=secondary
                )
                self.logger.info(
                    f'created service principal {service_principal.application_id} with display name {service_principal.display_name}'
                )

            # add service principal to group
            self.a.groups.patch(
                id=group.id,
                operations=[
                    Patch(
                        op=PatchOp.ADD,
                        value={
                            "members": [
                                {
                                    "value": service_principal.id,
                                }
                            ]
                        },
                    )
                ],
                schemas=[PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP],
            )

            self.logger.info(
                f'added service principal {service_principal.id} to group {group.display_name}'
            )

            # bring the group into the workspace with standard privileges
            self.try_until_succeeds(
                fn=self.a.workspace_assignment.update,
                workspace_id=self.workspace_id,
                principal_id=group.id,
                permissions=[WorkspacePermission.USER],
            )

            self.logger.info(f'assigned group {group.display_name} to workspace')

            # generate a token for the service principal and store it in a secret
            self.secrets_put(
                principal=primary,
                secrets={
                    'secondary_token': self.w.token_management.create_obo_token(
                        service_principal.application_id
                    ).token_value
                },
            )

            self.logger.info(
                f'stored PAT for service principal {service_principal.id} in a secret'
            )

            return group.display_name

        except Exception as e:
            # try to clean up
            try:
                if service_principal:
                    self.a.service_principals.delete(service_principal.id)

                if group:
                    self.a.groups.delete(group.id)

            except NotFound:
                pass

            raise e

    # clean up after db_create_secondary_principal()
    def iam_delete_secondary(self, name: str):

        self.logger.info(f'deleting secondary principal {name}')

        for g in self.a.groups.list():
            if g.display_name == name:
                self.a.groups.delete(g.id)
                self.logger.info(f'deleted group {g.display_name}')
                break
        else:
            self.logger.warning(f'could not find a group named {name}')

        for s in self.a.service_principals.list():
            if s.display_name == name:
                self.a.service_principals.delete(s.id)
                self.logger.info(f'deleted service principal {s.application_id}')
                break
        else:
            self.logger.warning(f'could not find a service principal named {name}')
