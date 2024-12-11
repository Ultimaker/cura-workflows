# See https://pyinstaller.readthedocs.io/en/stable/usage.html#what-to-bundle-where-to-search
# for information about the --additional-hooks-dir option and how to use it to include this file.

import glob
import os

from PyInstaller.utils.hooks import logger

def pre_find_module_path(api):
    """
    Hook to apply modifications to default PyQt6 hook that exclude unwanted items,
    like some differently licenced ones that somehow got through our other filtering processes.
    """
    from PyInstaller.utils.hooks import qt

    logger.info("Override get_qt_binaries in hooks/qt.py")
    qt.get_qt_binaries = get_qt_binaries

    logger.info("Exclude unused Qt plugins")
    from PyInstaller.utils import misc
    misc.files_in_dir = files_in_dir

def get_qt_binaries(qt_library_info):
    # Monkey-patch that omits unused Qt binaries to reduce file size
    binaries = []
    return binaries

def files_in_dir(directory, file_patterns=[]):
    # Monkey-patch that excludes specific Qt plugins to reduce file size
    included_files = []
    excluded_files = []
    exclusion_patterns = [ "*quick3d*" ]
    for file_pattern in file_patterns:
        included_files.extend(glob.glob(os.path.join(directory, file_pattern)))
    for file_pattern in exclusion_patterns:
        excluded_files.extend(glob.glob(os.path.join(directory, file_pattern)))
    files = list(set(included_files) - set(excluded_files))
    return files
