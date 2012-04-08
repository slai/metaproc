##
# This is the sample configuration file for metaproc.
#
# These settings are all required to exist; there are no defaults explicitly
# configured.
#
# This file can also act as the sample file for the metaproc override files;
# .metaproc-override files are simply configuration files with a different
# name. If this is a .metaproc-override file, the previous settings can be
# referenced by the same setting name, e.g. to append to the path exclusion list,
#
# PATH_EXCLUDE_REGEXPS = [
#     '.*\.wmv$'
# ] + PATH_EXCLUDE_REGEXPS
##

# list of directories to be processed. This setting is only read in the main
# settings file, not in the .metaproc-override files.
DIRS_TO_PROCESS = [
    '/mnt/videos/TV',
    '/mnt/videos/Movies'
]

# the python function to use to determine the facts from a given path, e.g.
# it will determine from the path /mnt/videos/TV/Entourage/Season 1 that the
# series_title is Entourage, and the season_number is 1.
#
# The default facts function can be referenced using the 'keyword'
# default_facts_function.
#
# If a custom facts function is necessary, the function signature needs to be -
#
#     def fact_function(path, conf, facts):
#
# ...where path is the absolute path to the file, conf is a dict of these
# settings plus any overrides applied along the way, and facts which is the
# dict where any determined facts need to be stored in.
FACTS_FUNCTION = default_facts_function

# the processor to use when processing these paths. At the moment, there is only
# one processor, the mediabrowser one, so this setting doesn't need to be
# changed. If you wish to write a custom one, look at the mediabrowser one as
# a template.
PROCESSOR = 'processors.mediabrowser'

# these are the Python regular expressions used to include and exclude paths to
# be processed. Remember that include filters are processed first before exclude
# filters. Directories will have a trailing slash applied. A regexp for
# subdirectories will be automatically added.
PATH_INCLUDE_REGEXPS = [
    '.*\.avi$',
    '.*\.mkv$',
    '.*\.mp4$'
]

PATH_EXCLUDE_REGEXPS = [
    # exclude metadata directories used by Media Browser.
    '/metadata/$'
]

# the following are the regular expressions used by the default_facts_function
# to determine what the facts are for a given path. The named capture groups
# are important - the default_facts_function uses series_title, season_number,
# episode_number and movie_title, so the regular expressions should include at
# least one of them. It is not necessary to include all of them, especially when
# the fact can come from up the directory tree (e.g. for a directory inside a
# series directory, we already know the series_title is X so there isn't a need
# to look that up again).
TV_SEASON_FACTS_REGEXPS = [
    'SEASON\s*(?P<season_number>\d+)'
]

TV_FILE_FACTS_REGEXPS = [
    '([\.\-_ ]|^)S(?P<season_number>\d+)[\.\-_ ]*E(?P<episode_number>\d+)[\.\-_ ]',
    '([\.\-_ ]|^)0?(?P<season_number>\d{1})(?P<episode_number>\d{2})[\.\-_ ]',
    '([\.\-_ ]|^)(?P<season_number>\d+)x(?P<episode_number>\d{2})[\.\-_ ]',
    '([\.\-_ ]|^)Season[\.\-_ ](?P<season_number>\d+)[\.\-_ ]+Episode[\.\-_ ](?P<episode_number>\d+)[\.\-_ ]'
]

MOVIE_TITLE_FACTS_REGEXPS = [
    
]

# download images?
DOWNLOAD_IMAGES = True

# maximum number of backdrop images to download
MAX_NUMBER_OF_BACKDROPS = 3
