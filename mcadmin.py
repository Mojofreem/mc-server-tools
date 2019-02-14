# Tools and utilities for managing a minecraft server instance

import requests
import sys
import pprint
import re
import os
import shutil
import zipfile
import json


def MINUTES(num):
    return num * 60


def HOURS(num):
    return num * 60 * 60


def DAYS(num):
    return num * 24 * 60 * 60


DEBUG_ENABLED = True
MOJANG_VERSION_MANIFEST_URL = 'https://launchermeta.mojang.com/mc/game/version_manifest.json'
MCADMIN_WORKDIR_ENV_VAR = 'MC_ADMIN_PATH'
MCADMIN_VERSION_MANIFEST_EXPIRY = None
#MCADMIN_VERSION_MANIFEST_EXPIRY = HOURS(6)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def debug_msg(*args, **kwargs):
    if DEBUG_ENABLED:
        eprint("DEBUG:", *args, **kwargs)


def error_msg(*args, **kwargs):
    eprint("ERROR:", *args, **kwargs)


def info_msg(*args, **kwargs):
    eprint("INFO :", *args, **kwargs)


def warn_msg(*args, **kwargs):
    eprint("WARN :", *args, **kwargs)


def dump_json(json):
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(json)


def make_dirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as ex:
        error_msg("Failed to create directory [{}]: {}".format(path, str(ex)))
        return False
    return True


def get_url(url):
    r = requests.get(url)
    if r.status_code != 200:
        error_msg("Failed to retrieve url[{}]: http status {}".format(url, r.status_code))
        return None
    return r.content


class MCVersion(object):
    def __init__(self, admin, version, manifest):
        self._admin = admin
        self._version = version
        self._manifest = manifest

    def dump_manifest(self):
        if self._manifest is None:
            return
        dump_json(self._manifest)

    def _create_version_dir(self):
        return make_dirs(self._admin.get_version_dir(self._version))

    def _resource_exists(self, path):
        return os.path.exists(os.path.join(self._admin.get_version_dir(self._version), path))

    def download_client_jar(self):
        if self._resource_exists('client.jar'):
            info_msg("Client jar for version [{}] is cached".format(self._version))
            return True

        if 'downloads' not in self._manifest or 'client' not in self._manifest['downloads'] or 'url' not in self._manifest['downloads']['client']:
            error_msg("Version manifest for [{}] is incomplete; missing downloads:client:url entry".format(self._version))
            return False

        if not self._create_version_dir():
            return False

        url = self._manifest['downloads']['client']['url']
        info_msg("Downloading [{}]...".format(url))
        r = requests.get(url)
        if r.status_code != 200:
            error_msg("Failed to retrieve client jar from url[{}]: http status {}".format(url, r.status_code))
            return False

        try:
            with open(os.path.join(self._admin.get_version_dir(self._version), 'client.jar'), 'wb') as f:
                f.write(r.content)
        except Exception as ex:
            error_msg("Failed to save version [{}] client jar: {}".format(self._version, str(ex)))
            return False

        return True

    def get_server_jar(self):
        if self._resource_exists('server.jar'):
            info_msg("Server jar for version [{}] is cached".format(self._version))
            return True

        if 'downloads' not in self._manifest or 'server' not in self._manifest['downloads'] or 'url' not in self._manifest['downloads']['server']:
            error_msg("Version manifest for [{}] is incomplete; missing downloads:server:url entry".format(self._version))
            return False

        if not self._create_version_dir():
            return False

        url = self._manifest['downloads']['server']['url']
        info_msg("Downloading [{}]...".format(url))
        r = requests.get(url)
        if r.status_code != 200:
            error_msg("Failed to retrieve server jar from url[{}]: http status {}".format(url, r.status_code))
            return False

        try:
            with open(os.path.join(self._admin.get_version_dir(self._version), 'server.jar'), 'wb') as f:
                f.write(r.content)
        except Exception as ex:
            error_msg("Failed to save version [{}] server jar: {}".format(self._version, str(ex)))
            return False

        return True

    def get_client_jar_path(self):
        return os.path.join(self._admin.get_version_dir(self._version), 'client.jar')

    def get_server_jar_path(self):
        return os.path.join(self._admin.get_version_dir(self._version), 'server.jar')

    def get_texture_path(self):
        return os.path.join(self._admin.get_version_dir(self._version), 'textures')

    def purge_version_cache(self):
        fail = False
        info_msg("Purging cache for version [{}]...".format(self._version))
        if self._resource_exists('client.jar'):
            try:
                os.remove(os.path.join(self._admin.get_version_dir(self._version), 'client.jar'))
            except Exception as ex:
                error_msg("Failed to remove cached client jar for version [{}]: {}".format(self._version, str(ex)))
                fail = True

        if self._resource_exists('server.jar'):
            try:
                os.remove(os.path.join(self._admin.get_version_dir(self._version), 'server.jar'))
            except Exception as ex:
                error_msg("Failed to remove cached server jar for version [{}]: {}".format(self._version, str(ex)))
                fail = True

        if self._resource_exists('textures'):
            try:
                shutil.rmtree(os.path.join(self._admin.get_version_dir(self._version), 'textures'))
            except Exception as ex:
                error_msg("Failed to remove texture cache for version [{}]: {}".format(self._version, str(ex)))
                fail = True

        return not fail

    TEXTURE_RESOURCES=['entity/chest/normal.png',
                       'entity/chest/normal_double.png',
                       'entity/chest/ender.png',
                       'entity/chest/trapped.png',
                       'entity/chest/trapped_double.png',
                       'colormap/foliage.png',
                       'colormap/grass.png',
                       'blocks/*',
                       'entity/end_portal.png']

    def extract_textures(self):
        if not self.download_client_jar():
            return False

        if self._resource_exists('textures'):
            return True

        try:
            os.mkdir(os.path.join(self._admin.get_version_dir(self._version), 'textures'))
            jar = zipfile.ZipFile(os.path.join(self._admin.get_version_dir(self._version), 'client.jar'))
            for entry in self.TEXTURE_RESOURCES:
                jar.getinfo()
            #jar.extract()
        except Exception as ex:
            error_msg("Failed to extract textures from client jar for version [{}]: {}".format(self._version, str(ex)))
            return False


class MCVersions(object):
    """See https://wiki.vg/Game_files for manifest details"""

    RELEASE='release'
    SNAPSHOT='snapshot'
    ALL='all'
    OLD_ALPHA='old_alpha'
    OLD_BETA='old_beta'

    def __init__(self, admin, manifest):
        self._valid = False
        self._admin = admin
        self._manifest = None
        self._versions = {}
        self._manifests = {}
        self._latest = None

        if manifest is not None:
            try:
                self._manifest = json.loads(manifest)
            except Exception as ex:
                error_msg("Failed to parse version manifest: {}".format(str(ex)))
                return
            self._parse_manifest()

    def _parse_manifest(self):
        self._failed = False
        versions = {MCVersions.RELEASE: {}, MCVersions.SNAPSHOT: {}}
        if 'latest' in self._manifest and 'release' in self._manifest['latest'] and 'snapshot' in self._manifest['latest']:
            self._latest = self._manifest['latest']
        else:
            error_msg("Missing or incomplete latest version definition in Mojang release manifest")
            return

        if 'versions' in self._manifest:
            for entry in self._manifest['versions']:
                if entry['type'] == MCVersions.OLD_ALPHA or entry['type'] == MCVersions.OLD_BETA:
                    continue
                versions[entry['type']][entry['id']] = entry['url']
        else:
            error_msg("No versions found in Mojang release manifest")
            return

        self._versions = versions
        self._valid = True

    def dump_manifest(self):
        if self._manifest is None:
            return
        dump_json(self._manifest)

    def dump_latest(self):
        info_msg("Release : {}".format(self._latest[MCVersions.RELEASE]))
        info_msg("Snapshot: {}".format(self._latest[MCVersions.SNAPSHOT]))

    def resolve_version_type(self, version):
        if version in self._versions[MCVersions.RELEASE]:
            return MCVersions.RELEASE
        if version in self._versions[MCVersions.SNAPSHOT]:
            return MCVersions.SNAPSHOT
        error_msg("Cannot determine release type for unknown version [{}]".format(version))
        return None

    def _resolve_update_version(self, check):
        if self.resolve_version_type(check) is None:
            return False

        comp = self.get_latest_version(self.resolve_version_type(check))
        if comp is None:
            return None

        base_version = self.parse_version(check)
        latest_version = self.parse_version(comp)

        return base_version, latest_version

    def is_major_update(self, check):
        semantics = self._resolve_update_version(check)
        if semantics is None:
            return False

        return bool(semantics[0][0] < semantics[1][0])

    def is_minor_update(self, check):
        semantics = self._resolve_update_version(check)
        if semantics is None:
            return False

        return bool((semantics[0][0] == semantics[1][0]) and (semantics[0][1] < semantics[1][1]))

    def is_revision_update(self, check):
        semantics = self._resolve_update_version(check)
        if semantics is None:
            return False

        return bool((semantics[0][0] == semantics[1][0]) and (semantics[0][1] == semantics[1][1]) and (semantics[0][2] < semantics[1][2]))

    def is_update_available(self, check):
        return self.is_major_update(check) or self.is_minor_update(check) or self.is_revision_update(check)

    def get_latest_version(self, release_type=RELEASE):
        return self._latest[release_type]

    def get_release_list(self):
        return self._versions[MCVersions.RELEASE].keys()

    def get_snapshot_list(self):
        return self._versions[MCVersions.SNAPSHOT].keys()

    def _parse_release_version(self, version):
        if self.resolve_version_type(version) != MCVersions.RELEASE:
            return 0, 0, 0

        m = re.match('^\s*(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<revision>\d+))?\s*$', version)
        if m is None:
            error_msg("Failed to parse release version: [{}]".format(version))
            return 0, 0, 0

        rev = m.group('revision') if m.group('revision') is not None else 0
        return m.group('major'), m.group('minor'), rev

    def _parse_snapshot_version(self, version):
        if self.resolve_version_type(version) != MCVersions.SNAPSHOT:
            return 0, 0, 'a'

        m = re.match('^\s*(?P<major>\d+)w(?P<minor>\d+)(?P<revision>[a-z])\s*$', version)
        if m is None:
            error_msg("Failed to parse snapshot version: [{}]".format(version))
            return 0, 0, 'a'

        return m.group('major'), m.group('minor'), m.group('revision')

    def parse_version(self, version):
        vtype = self.resolve_version_type(version)
        if vtype is None:
            return 0, 0, 0

        if vtype == MCVersions.RELEASE:
            return self._parse_release_version(version)
        return self._parse_snapshot_version(version)

    def version_url(self, version):
        if version in self._versions[MCVersions.RELEASE]:
            return self._versions[MCVersions.RELEASE][version]
        if version in self._versions[MCVersions.SNAPSHOT]:
            return self._versions[MCVersions.SNAPSHOT][version]
        error_msg("Cannot determine URL for unknown version [{}]".format(version))
        return None

    def get_version(self, version):
        if version in self._manifests:
            return self._manifests[version]

        url = self.version_url(version)
        if url is None:
            error_msg("Unrecognized version [{}]".format(version))
            return None

        manifest = self._admin.get_url_and_cache(url, 'version-{}.json'.format(version))
        if manifest is None:
            return None

        try:
            manifest = json.loads(manifest)
        except Exception as ex:
            error_msg("Failed to parse version [{}] manifest: {}".format(version, str(ex)))
            return None

        release = MCVersion(admin, version, manifest)
        if release is not None:
            self._manifests[version] = release

        return release


class MCAdmin(object):
    CORE_DIRS = ['cache', 'versions', 'worlds', 'conf']

    def __init__(self):
        self._working_dir = os.getcwd()
        self._working_dir_resolved = False
        self._working_dir_cli_arg = False
        self._versions = None

    def _resolve_working_dir(self):
        if not self._working_dir_resolved:
            if not self._working_dir_cli_arg:
                if MCADMIN_WORKDIR_ENV_VAR in os.environ:
                    self._working_dir = os.environ[MCADMIN_WORKDIR_ENV_VAR]
                else:
                    self._working_dir = '~/mcadmin'
        self._working_dir_resolved = True

    def is_init(self):
        basedir = self.get_working_dir()
        init = True
        if not os.path.exists(basedir):
            warn_msg("MCAdmin working directory [{}] does not exist.".format(basedir))
            init = False
        elif not os.path.isdir(basedir):
            error_msg("MCAdmin working directory [{}] is not a directory.".format(basedir))
            return False
        else:
            for sub in self.CORE_DIRS:
                subdir = os.path.join(basedir, sub)
                if not os.path.exists(subdir):
                    warn_msg("MCAdmin working directory [{}] was not found.".format(subdir))
                    init = False
        if not init:
            info_msg("MCAdmin is not initialized in working directory [{}].".format(basedir))
            info_msg("Please run 'mcadmin init' to initialize MCAdmin")
        return init

    def init_env(self):
        basedir = self.get_working_dir()
        if not os.path.exists(basedir):
            if not make_dirs(basedir):
                error_msg("Failed to create base working directory [{}]".format(basedir))
                return False
        elif not os.path.isdir(basedir):
            error_msg("MCAdmin working directory [{}] is not a directory.".format(basedir))
            return False

        for sub in self.CORE_DIRS:
            subdir = os.path.join(basedir, sub)
            if not make_dirs(subdir):
                error_msg("Failed to create working subdir [{}]".format(subdir))
                return False

        # TODO - copy configuration templates

        return True

    def set_working_dir(self, path):
        self._working_dir = path
        self._working_dir_cli_arg = True

    def get_working_dir(self):
        """
        --work-dir <...>
        env MC_ADMIN_PATH=...
        ~/mcadmin/
        """
        self._resolve_working_dir()
        return os.path.expanduser(self._working_dir)

    def get_cache_dir(self):
        return os.path.join(self.get_working_dir(), 'cache')

    def get_cache_path(self, path):
        return os.path.join(self.get_cache_dir(), path)

    def get_version_dir(self, version=None):
        if version is not None:
            return os.path.join(self.get_working_dir(), 'versions', version)
        return os.path.join(self.get_working_dir(), 'versions')

    def get_config_dir(self):
        return os.path.join(self.get_working_dir(), 'conf')

    def get_worlds_dir(self, instance):
        if instance is not None:
            return os.path.join(self.get_working_dir(), 'worlds', instance)
        return os.path.join(self.get_working_dir(), 'worlds')

    def get_url(self, url, dump=False):
        r = requests.get(url)
        if r.status_code != 200:
            error_msg("Failed to retrieve url[{}]: http status {}".format(url, r.status_code))
            return False
        if dump:
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(r.json())
        return True

    def clear_cache(self):
        # TODO
        pass

    def is_file_cached(self, filename):
        path = self.get_cache_path(filename)
        cached = os.path.exists(path) and os.path.isfile(path)
        debug_msg("File [{}] is {}cached".format(filename, '' if cached else 'not '))
        return cached

    def get_cache_timestamp(self, filename):
        return None

    def cache_save(self, filename, content):
        try:
            with open(self.get_cache_path(filename), 'wb') as fp:
                fp.write(content)
        except Exception as ex:
            error_msg("Failed to save cache file [{}]: {}".format(filename, str(ex)))
            return False
        return True

    def cache_load(self, filename):
        try:
            with open(self.get_cache_path(filename), 'rb') as fp:
                return fp.read()
        except Exception as ex:
            error_msg("Failed to load cache file [{}]: {}".format(filename, str(ex)))
            return None

    def get_url_and_cache(self, url, local, timeout=None):
        refresh = False

        debug_msg("Get url [{}] and cache as [{}]".format(url, local))
        if timeout is True:
            debug_msg("Caller forced cache refresh")
            refresh = True
        elif not self.is_file_cached(local):
            debug_msg("File is not yet cached")
            refresh = True
        elif timeout is not None and timeout is not True:
            debug_msg("Evaluate cache timeout...")
            # TODO - evaluate cache expiry
            refresh = False

        if refresh:
            debug_msg("Retrieving [{}]...".format(url))
            r = requests.get(url)
            if r.status_code != 200:
                error_msg("Failed to retrieve url[{}]: http status {}".format(url, r.status_code))
                return False
            content = r.content
            if not self.cache_save(local, content):
                return False
        else:
            debug_msg("From cache [{}]".format(local))
            content = self.cache_load(local)
            if content is None:
                return False

        return content

    def get_version_manifest(self):
        return self.get_url_and_cache(MOJANG_VERSION_MANIFEST_URL, 'version_manifest.json', MCADMIN_VERSION_MANIFEST_EXPIRY)

    def get_versions(self):
        if self._versions is None:
            self._versions = MCVersions(self, self.get_version_manifest())
        return self._versions


class MCWorld(object):
    VALID_NAME_CHARS = 'abcdefghijklmnopqrstuvwxyz0123456789-_.'

    def __init__(self, admin, name):
        self._valid = False
        self._admin = admin
        self._version = None
        self._name = self.normalize_name(name)

    def normalize_name(self, name):
        out = ''
        last = None
        for c in name:
            if c not in self.VALID_NAME_CHARS:
                c = '_'
            if c == '_':
                if last != '_':
                    out += '_'
            else:
                out += c
            last = c
        return out

    def verify(self):
        pass




if __name__ == '__main__':
    #manifest = MCManifest()
    #manifest.download()
    #manifest.dump()
    #manifest.latest()
    #print(manifest.versions(MCManifest.RELEASE))
    #get_url(manifest.version_url(manifest.latest()[MCVersions.RELEASE]))

    #register = MCVersions()
    #register.dump_version_manifest(register.get_latest_version())
    #register.get_client_jar(register.get_latest_version())
    #register.get_server_jar(register.get_latest_version())
    #register.extract_textures(register.get_latest_version())

    admin = MCAdmin()
    #admin.set_working_dir("/woot/woot/shnoo")
    admin.is_init()
    #admin.init_env()
    manifest = admin.get_url_and_cache(MOJANG_VERSION_MANIFEST_URL, 'version_manifest.json')
    if manifest is False:
        error_msg("Failed to get the manifest")
    admin.get_versions().dump_latest()
    admin.get_versions().dump_manifest()
    #admin.get_versions().get_version(admin.get_versions().get_latest_version(MCVersions.RELEASE)).dump_manifest()
