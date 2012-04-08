##
# metaproc downloads metadata for media - currently movies and TV shows.
##

import os
import sys
import re
from optparse import OptionParser

APP_ONLY_SETTINGS = [ 'DIRS_TO_PROCESS' ]
MODULES_TO_LOAD_IN_SETTINGS = [ 'PROCESSOR' ]
INCLUDE_SUBDIR_REGEXP = re.compile('.*/$')

# FUNCTIONS
def default_facts_function(path, conf, facts):
    '''\
    This function retrieves the facts from the current path, making the
    following assumptions -
    
        * if this is a TV show path,
            - if there is neither a series title, season number, or episode
              number, try working out the series title.
            - if there is a series title but no season number, try working out
              the season number.
            - if there is a series title and season number, try working out the
              episode number.
        
        * if this is a movie path,
            - try working out the movie title.
    '''
    # we need to strip the trailing / off first if it exists otherwise basename
    # will return a blank string.
    file_name = os.path.basename(path.rstrip(os.path.sep))
    item_type = facts.get('type', '').lower()
    
    if item_type == 'tv':
        series_title = facts.get('series_title', '')
        season_number = facts.get('season_number', '')
        episode_number = facts.get('episode_number', '')
        
        # if this is a file, jump straight to the file regexps if we don't have
        # all the details already
        if os.path.isfile(path) and not \
            (series_title and season_number and episode_number):
            for regexp in conf['TV_FILE_FACTS_REGEXPS']:
                m = regexp.search(file_name)
                if m:
                    facts.update(m.groupdict())
                    break
        
        elif series_title and not season_number:
            for regexp in conf['TV_SEASON_FACTS_REGEXPS']:
                m = regexp.search(file_name)
                if m:
                    facts.update(m.groupdict())
                    break
        
        elif not series_title:
            facts['series_title'] = file_name
        
        else:
            # this item is already factually complete.
            pass
    
    elif item_type == 'movie':
        movie_title = facts.get('movie_title', '')
        
        if not movie_title:
            # prefer the dir name as the movie title than one extracted from the file
            if os.path.isfile(path):
                for regexp in conf['MOVIE_TITLE_FACTS_REGEXPS']:
                    m = regexp.search(file_name)
                    if m:
                        facts.update(m.groupdict())
                        break
            # this is a dir, assume the dir name is the movie title
            else:
                facts['movie_title'] = file_name
    
    else:
        print '\t[WARN] unknown type for ' + file_name
    

def get_settings_locals():
    '''\
    This function returns a new dict with the locals needed for settings or
    override files to initialise properly.
    '''
    return {
        'default_facts_function' : default_facts_function
    }

def load_settings(path, current_settings=None):
    '''\
    This function loads the given Python file and returns its locals, i.e. the
    settings.
    
    If current_settings is specified, it is passed into the loading process so
    the settings file to load can reference the current settings. The result is
    the new settings are merged in with the current settings in a new dict.
    '''
    tmp_globals = globals()
    tmp_locals = get_settings_locals()
    if current_settings:
        tmp_locals.update(current_settings)
    execfile(path, tmp_globals, tmp_locals)
    
    # load the actual module for those settings in MODULES_TO_LOAD_IN_SETTINGS
    for s in MODULES_TO_LOAD_IN_SETTINGS:
        # also check if it is a string as if current_settings is passed in, it
        # could already by a module.
        if s in tmp_locals.keys() and isinstance(tmp_locals[s], basestring):
            m = __import__(tmp_locals[s])
            
            # __import__ returns an module wrapped with metadata; we only want
            # the module, so we'll unwrap it.
            # get the module name
            module_name = tmp_locals[s]
            if module_name.rfind('.') > 0:
                module_name = module_name[module_name.rfind('.')+1:]
            
            tmp_locals[s] = getattr(m, module_name)
    
    # compile any regexps.
    for s in tmp_locals.keys():
        if s.lower().endswith('_regexp'):
            # only compile if a string is given (a compiled RE object can also
            # be provided)
            if isinstance(tmp_locals[s], basestring):
                tmp_locals[s] = re.compile(tmp_locals[s], re.IGNORECASE)
        elif s.lower().endswith('_regexps'):
            regexps = [ ]
            for regexp in tmp_locals[s]:
                # only compile if a string is given (a compiled RE object can 
                # also be provided)
                if isinstance(regexp, basestring):
                    regexps.append(re.compile(regexp, re.IGNORECASE))
                else:
                    regexps.append(regexp)
            tmp_locals[s] = regexps
    
    return tmp_locals

def get_files_list(path, conf):
    '''\
    Gets the list of files to process at this path after applying any rules set
    in conf.
    '''
    # ignore the override file (it has already be loaded; see above)
    files = [ p for p in os.listdir(path) if p != '.metaproc-override' ]
    
    # make the file paths absolute
    files = [ os.path.join(path, p) for p in files ]
    
    # add trailing slash if it is a directory
    files = [ os.path.isdir(p) and (p + os.path.sep) or p for p in files ]
    
    # apply include filters
    if 'PATH_INCLUDE_REGEXPS' in conf.keys() and \
        len(conf['PATH_INCLUDE_REGEXPS']) > 0:
        filtered_files = [ ]
        include_regexps = conf['PATH_INCLUDE_REGEXPS']
        # add the regexp to include subdirectories. If you want to exclude
        # subdirectories, that needs to be explicitly set in the
        # PATH_EXCLUDE_REGEXPS setting.
        include_regexps.append(INCLUDE_SUBDIR_REGEXP)
        for f in files:
            for r in include_regexps:
                if r.search(f):
                    # matches, so add it to the filtered list and don't bother
                    # continuing to match
                    filtered_files.append(f)
                    break
        
        files = filtered_files
    
    # apply exclude filters
    if 'PATH_EXCLUDE_REGEXPS' in conf.keys() and \
        len(conf['PATH_EXCLUDE_REGEXPS']) > 0:
        filtered_files = [ ]
        exclude_regexps = conf['PATH_EXCLUDE_REGEXPS']
        for f in files:
            exclude_file = False
            for r in exclude_regexps:
                if r.search(f):
                    # matches, so add mark this as to be excluded and don't
                    # bother continuing to match
                    exclude_file = True
                    break
            
            if not exclude_file:
                filtered_files.append(f)
        
        files = filtered_files
    
    # sort the files so the processing works in an orderly fashion, instead of a
    # seemingly random order.
    files.sort()
    
    return files

def process_path(path, conf, base_facts, is_root=False):
    '''\
    This function is called for each file/directory encountered.
    '''
    print path
    
    # load the override file if it exists
    override_path = os.path.join(path, '.metaproc-override')
    if os.path.exists(override_path):
        conf = load_settings(override_path, conf)

        # if it contains a facts override, apply it
        if 'facts' in conf.keys():
            base_facts.update(conf.pop('facts'))
    
    # process this directory if it isn't the root directory
    if not is_root:
        # make a copy of the currently known facts
        facts = base_facts.copy()
        # get the facts 
        conf['FACTS_FUNCTION'](path, conf, facts)
        # process it
        conf['PROCESSOR'].process(path, conf, facts)
        # we want these facts to apply to all descendants, so we'll make this
        # the base_facts.
        base_facts = facts
    
    # process files/directories inside this dir
    files = get_files_list(path, conf)
    
    for f in files:
        # make a copy of the currently known facts
        facts = base_facts.copy()
            
        # if this file is a directory, process that too
        if os.path.isdir(f):
            process_path(f, conf, facts)
        else:
            # this is a file; process it
            # load the override file if it exists
            override_path = f + '.metaproc-override'
            if os.path.exists(override_path):
                conf = load_settings(override_path, conf)
        
                # if it contains a facts override, apply it
                if 'facts' in conf.keys():
                    facts.update(conf.pop('facts'))
            
            # get the facts for this file
            conf['FACTS_FUNCTION'](f, conf, facts)
            
            # process this file
            conf['PROCESSOR'].process(f, conf, facts)

def perform_clean(root_path, path, conf, base_facts, recursive=False):
    '''\
    This function is the starting point for a clean operation. Paths provided
    must be absolute paths.
    '''
    # sanity check
    if not path.startswith(root_path):
        raise ValueError('The path given does not start with the root path.')
    
    # get all the path components between the root path and the path
    # we get rid of any leading or trailing path separators to ensure the split
    # result doesn't contain blank entries.
    rel_path_bits = path.strip(os.path.sep)[len(root_path):].split(os.path.sep)
    
    # work out all the intermediate paths we need to visit to build up the conf
    intermediate_paths = [ ]
    for i,p in enumerate(rel_path_bits):
        intermediate_path = os.path.join(root_path, os.path.sep.join(rel_path_bits[:i]))
        if not intermediate_path.endswith(os.path.sep):
            intermediate_path += os.path.sep
        intermediate_paths.append(intermediate_path)
    
    # don't change the original facts
    facts = base_facts.copy()
    files = [ intermediate_paths[0] ]
    for p in intermediate_paths:
        # check if this intermediate path is in the list of paths; if not, it
        # means it has been excluded by the filters.
        if p not in files:
            print 'The given path to clean has been excluded by the configured filters. Aborting.'
            return
        
        # load the override file if it exists
        override_path = os.path.join(p, '.metaproc-override')
        if os.path.exists(override_path):
            conf = load_settings(override_path, conf)
            
            # if it contains a facts override, apply it
            if 'facts' in conf.keys():
                facts.update(conf.pop('facts'))
        
        # get the facts from this path
        conf['FACTS_FUNCTION'](p, conf, facts)
        
        # process files/directories inside this dir
        files = get_files_list(p, conf)

    # conf has been built up; clean!
    clean_path(path, conf, facts, recursive)

def clean_path(path, conf, base_facts, recursive=False):
    '''\
    Cleans the given path. Also cleans any descendants if recursive = True.
    '''
    print path
    
    # clean ourselves first
    facts = base_facts.copy()
    conf['FACTS_FUNCTION'](path, conf, facts)
    conf['PROCESSOR'].clean(path, conf, facts)
    # we want these facts to apply to all descendants, so we'll make this
    # the base_facts.
    base_facts = facts
    
    # clean our children
    if recursive:
        files = get_files_list(path, conf)
        for f in files:
            # make a copy of the currently known facts
            facts = base_facts.copy()

            # if this file is a directory, process that too
            if os.path.isdir(f):
                clean_path(f, conf, facts, recursive)
            else:
                # this is a file; clean it
                # load the override file if it exists
                override_path = f + '.metaproc-override'
                if os.path.exists(override_path):
                    conf = load_settings(override_path, conf)
            
                    # if it contains a facts override, apply it
                    if 'facts' in conf.keys():
                        facts.update(conf.pop('facts'))
                
                # get the facts for this file
                conf['FACTS_FUNCTION'](f, conf, facts)
                
                # clean this file
                conf['PROCESSOR'].clean(f, conf, facts)

def main():
    # parse args
    parser = OptionParser()
    parser.add_option("-s", "--settings", dest="settings",
                      help="settings file to use")
    parser.add_option("-C", "--clean", dest="clean_path", help="path to clean")
    parser.add_option("-R", "--rclean", dest="rclean_path", help="path to recursively clean from")
   
    (options, args) = parser.parse_args()
    
    # get the settings file path
    if not options.settings:
        print "The --settings argument must be specified."
        sys.exit(1)
    
    settings_path = options.settings
    
    # load settings
    settings = load_settings(settings_path)
    
    # build the base context for processing by copying and removing the
    # irrelevant settings from the app settings.
    base_conf = { }
    for k, v in settings.items():
        if k not in APP_ONLY_SETTINGS:
            base_conf[k] = v
    
    if options.clean_path or options.rclean_path:
        # we're cleaning!
        if options.clean_path:
            path = options.clean_path
            recursive = False
        else:
            path = options.rclean_path
            recursive = True
        
        path = os.path.abspath(path)
        
        # determine the right root path
        root_path = None
        for p in settings['DIRS_TO_PROCESS']:
            if path.startswith(p):
                root_path = p
                break
        
        if root_path is None:
            print 'The path to clean is not contained in one of the configured DIRS_TO_PROCESS. Aborting.'
            sys.exit(2)
        
        perform_clean(root_path, path, base_conf, { }, recursive)
    else:
        # we're processing!
        for p in settings['DIRS_TO_PROCESS']:
            process_path(p, base_conf, { }, True)
    
    print '\nMetaProc done.\n'

# END FUNCTIONS

if __name__ == '__main__':
    main()
