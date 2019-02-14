##############################################################################
#
# Merge JSON property files
# Used to apply global settings to local server instances for:
#
#     banned-ips.json
#     banned-players.json
#     ops.json
#     whitelist.json
#
##############################################################################

import json
import sys
import os
import pprint


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def error_msg(*args, **kwargs):
    eprint("ERROR:", *args, **kwargs)


def info_msg(*args, **kwargs):
    eprint("INFO :", *args, **kwargs)


def load_props(filename):
    props = []
    try:
        with open(filename, 'rb') as fp:
            props = json.load(fp)
    except Exception as ex:
        error_msg("Failed to read properties from [{}]: {}".format(filename, str(ex)))
        return None

    if type(props) != type([]):
        error_msg("Expected top level array, found [{}] instead".format(type(props)))
        return None

    return props


def prop_merge(global_filename, local_filename):
    g_props = load_props(global_filename)
    l_props = load_props(local_filename)

    if g_props is None or l_props is None:
        return None

    for entry in l_props:
        if type(entry) == type({}) and 'uuid' in entry:
            # only merge if uuid is not already in global
            merge = True
            for check in g_props:
                if type(check) == type({}) and 'uuid' in check:
                    if entry['uuid'] == check['uuid']:
                        merge = False
                        break
            if merge:
                g_props.append(entry)
        else:
            g_props.append(entry)

    return g_props


def usage():
    eprint("{} <global-props.json> <local-props.json>".format(os.path.basename(sys.argv[0])))


def verify_path(path):
    if not os.path.exists(path):
        error_msg("The file [{}] does not exist.".format(path))
        return False

    if not os.path.isfile(path):
        error_msg("The path [{}] is not a file.".format(path))
        return False

    return True


if __name__ == '__main__':
    if len(sys.argv) != 3:
        usage()
        exit(1)

    if not verify_path(sys.argv[1]) or not verify_path(sys.argv[2]):
        exit(2)

    result = prop_merge(sys.argv[1], sys.argv[2])
    if result is None:
        exit(3)

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(result)

    exit(0)
