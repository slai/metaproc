import os
import urllib
import glob
import re
from datetime import date, datetime

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from tvdb_api import tvdb_api, tvdb_exceptions
from themoviedb import tmdb

NO_IMAGE_EXTENSION = '.noimage'
IMAGE_EXTENSIONS = [ '.jpg', '.png' ]

tvdb = tvdb_api.Tvdb(select_first=True, cache=True, banners=True)

def process(path, conf, facts):
    '''\
    This one of the entry points to this processor. This method is called when
    a path needs to be processed.
    '''
    item_type = facts.get('type', '').lower()
    
    if item_type == 'tv':
        series_title = facts.get('series_title', '')
        season_number = facts.get('season_number', '')
        episode_number = facts.get('episode_number', '')
        
        # if this is a file, this is an episode
        if os.path.isfile(path):
            if series_title and season_number and episode_number:
                process_episode(path, conf, facts)
            else:
                print '\t%s [%s, s%se%s]' % (os.path.basename(path),
                                             series_title or '?',
                                             season_number or '?',
                                             episode_number or '?')
                print '\t\t[WARN] Not enough facts were available. Skipping.'
                return
        
        # if we only have the series title, this is a series directory
        elif series_title and not season_number and not episode_number:
            process_series(path, conf, facts)
        
        # if we have the series title and the season number, this is a season
        # directory
        elif series_title and season_number and not episode_number:
            process_season(path, conf, facts)
        
        else:
            print '\t%s' % path
            print '\t\t[WARN] Not enough facts were available. Skipping.'
            return
            
    elif item_type == 'movie':
        movie_title = facts.get('movie_title', '')
        
        if os.path.isfile(path):
            # we don't process files because Media Browser expects each movie
            # to be in a separate directory, so we just need to process
            # directories. This is not an error, so we just silently return.
            return
        elif movie_title:
            process_movie(path, conf, facts)
        else:
            print '\t%s' % path
            print '\t\t[WARN] Not enough facts were available. Skipping.'
            return
    
    else:
        print '\t%s' % path
        print '\t\t[WARN] Unknown item type (%s). Skipping.' % item_type
        return

def clean(path, conf, facts):
    '''\
    This is the other entry point to this processor. This is called when a path
    needs to be cleaned of any metadata.
    '''
    item_type = facts.get('type', '').lower()
    
    if item_type == 'tv':
        series_title = facts.get('series_title', '')
        season_number = facts.get('season_number', '')
        episode_number = facts.get('episode_number', '')
        
        # if this is a file, this is an episode
        if os.path.isfile(path):
            if series_title and season_number and episode_number:
                clean_episode(path, conf, facts)
            else:
                print '\t%s' % os.path.basename(path)
                print '\t\t[WARN] Not enough facts were available. Skipping.'
                return
        
        # if we only have the series title, this is a series directory
        elif series_title and not season_number and not episode_number:
            clean_series(path, conf, facts)
        
        # if we have the series title and the season number, this is a season
        # directory
        elif series_title and season_number and not episode_number:
            clean_season(path, conf, facts)
        
        else:
            print '\t%s' % path
            print '\t\t[WARN] Not enough facts were available. Skipping.'
            return
            
    elif item_type == 'movie':
        movie_title = facts.get('movie_title', '')
        
        if os.path.isfile(path):
            # we don't process files because Media Browser expects each movie
            # to be in a separate directory, so we just need to process
            # directories. This is not an error, so we just silently return.
            return
        elif movie_title:
            clean_movie(path, conf, facts)
        else:
            print '\t%s' % path
            print '\t\t[WARN] Not enough facts were available. Skipping.'
            return
    
    else:
        print '\t%s' % path
        print '\t\t[WARN] Unknown item type (%s). Skipping.' % item_type
        return

def get_metadata_dir_path(path):
    '''\
    Returns the path to the metadata directory for this path.
    '''
    dir_name = os.path.dirname(path)
    metadata_path = os.path.join(dir_name, 'metadata')
    
    return metadata_path

def mkdir_if_not_exists(path):
    '''\
    Creates the directories needed in the path if they don't exist.
    '''
    p = os.path.dirname(path)
    if not os.path.exists(p):
        os.makedirs(p)

def rm_if_exists(path):
    '''\
    Removes a file if it exists, otherwise swallow the file does not exist error.
    '''
    try:
        os.remove(path)
    except OSError, e:
        # only catch the 'no such file or directory' error
        if e.errno != 2:
            raise

def image_file_exists(glob_pattern, include_no_image=True):
    '''\
    Performs a glob and checks the extension of each result to see if it matches
    a known image file extension. Returns a list of image files, or None if none
    were found.
    
    Because filenames can contain square brackets, but square brackets have a
    special meaning when globbing, all square brackets are replaced with a [[]
    or []] respectively to 'escape' them. Square brackets in glob land means
    match any of the characters inside the square brackets once.
    
    Therefore in effect, the square bracket functionality for the glob pattern
    has been disabled.
    '''
    # HACK: escaping square brackets in filenames
    # replace the left square bracket with [[]
    glob_pattern = re.sub(r'\[', '[[]', glob_pattern)
    # replace the right square bracket with []] but being careful not to replace
    # the right square brackets in the left square bracket's 'escape' sequence.
    glob_pattern = re.sub(r'(?<!\[)\]', '[]]', glob_pattern)
    
    files = glob.glob(glob_pattern)
    image_files = [ ]
    for f in files:
        ext = os.path.splitext(f)[1]
        if ext in IMAGE_EXTENSIONS:
            image_files.append(f)
        if include_no_image and ext == NO_IMAGE_EXTENSION:
            image_files.append(f)
    
    if len(image_files) > 0:
        return image_files
    else:
        return None

def get_episode_metadata_path(path):
    '''\
    Returns the expected metadata path for this video file.
    '''
    file_name = os.path.basename(path)
    metadata_path = get_metadata_dir_path(path)
    
    # work out what the metadata.xml path is (just the filename with an extension of .xml instead)
    # but in the metadata directory
    metadata_xml_path = file_name
    # don't want to match a leading . for unix hidden files
    if metadata_xml_path.find('.') > 0:
        metadata_xml_path = metadata_xml_path[:metadata_xml_path.rfind('.')]
    metadata_xml_path = '%s.xml' % metadata_xml_path
    metadata_xml_path = os.path.join(metadata_path, metadata_xml_path)
    
    return metadata_xml_path

def is_episode_metadata_complete(path, conf):
    '''\
    Returns true if all the metadata for the episode at the given path looks
    to be complete (i.e. the expected files are there).
    '''
    if not os.path.exists(get_episode_metadata_path(path)):
        return False
    
    # images are optional, dependent on the setting. If no image is available,
    # the .noimage file is dropped. Image files are named with the name of the
    # file and a .jpg, .png or .noimage extension in the metadata directory.
    if conf.get('DOWNLOAD_IMAGES'):
        # if at least one image file exists for this episode, metadata is
        # complete.
        images = image_file_exists(os.path.splitext(get_episode_metadata_path(path))[0] + '.*')
        if images is None:
            return False
    
    return True

def process_episode(path, conf, facts):
    '''\
    Retrieve and write metadata for this episode.
    '''
    # check if metadata has already been written for this episode
    if is_episode_metadata_complete(path, conf):
        return
    
    # no metadata yet, so fetch it
    try:
        print '\t%s' % os.path.basename(path),
        season_number = int(facts['season_number'])
        episode_number = int(facts['episode_number'])
        # the .decode call is necessary because the series title may have non-
        # ASCII characters in it. In Linux, path names are UTF-8 encoded, so
        # we need to tell Python that so it can use that information for
        # encoding later (the tvdb_api forces re-encoding to UTF-8).
        series_title = facts['series_title'].decode('utf-8')
        print ' [%s, s%de%d]' % (series_title, season_number, episode_number)
        
        print '\t\tRetrieving episode metadata...'
        result = tvdb[series_title][season_number][episode_number]
    
        # data has been fetched; write it out
        xml_path = get_episode_metadata_path(path)
        
        # the .get method is used for non-essential attributes
        xml_root = ET.Element('Item')
        x = ET.SubElement(xml_root, 'ID')
        x.text = result['id']
        x = ET.SubElement(xml_root, 'Director')
        x.text = result.get('director')
        x = ET.SubElement(xml_root, 'EpisodeID')
        x.text = result['id']
        x = ET.SubElement(xml_root, 'EpisodeName')
        x.text = result['episodename']
        x = ET.SubElement(xml_root, 'EpisodeNumber')
        x.text = result['episodenumber']
        x = ET.SubElement(xml_root, 'FirstAired')
        x.text = result.get('firstaired')
        x = ET.SubElement(xml_root, 'GuestStars')
        x.text = result.get('gueststars')
        x = ET.SubElement(xml_root, 'Overview')
        x.text = result.get('overview')
        x = ET.SubElement(xml_root, 'ProductionCode')
        x.text = result.get('productioncode')
        x = ET.SubElement(xml_root, 'Writer')
        x.text = result.get('writer')
        x = ET.SubElement(xml_root, 'SeasonNumber')
        x.text = result['seasonnumber']
        x = ET.SubElement(xml_root, 'SeasonID')
        x.text = result['seasonid']
        x = ET.SubElement(xml_root, 'SeriesID')
        x.text = result['seriesid']
        x = ET.SubElement(xml_root, 'LastUpdated')
        x.text = result.get('lastupdated')
        x = ET.SubElement(xml_root, 'Rating')
        x.text = result.get('rating')
        
        xml = ET.ElementTree(xml_root)
        mkdir_if_not_exists(xml_path)
        # TODO: somehow pretty print this?
        xml.write(xml_path)
        
        if conf.get('DOWNLOAD_IMAGES'):
            image_path = os.path.splitext(xml_path)[0]
            # only attempt to download an image if one does not already exist
            if not image_file_exists(image_path + '.*'):
                image_url = result.get('filename')
                if image_url:
                    print '\t\tDownloading episode image...'
                    # the utf-8 conversion is important because otherwise if the
                    # image_path contains non-ASCII characters, Python won't
                    # know how to put them together (the ext is ASCII; path is
                    # UTF-8 on Linux).
                    image_path += os.path.splitext(image_url)[1].encode('utf-8')
                    urllib.urlretrieve(image_url, image_path)
                else:
                    # there is no image; drop a marker file so we won't check again
                    image_path += NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
    
    except tvdb_exceptions.tvdb_exception, e:
        print '\t\t[ERROR] ' + repr(e)

def clean_episode(path, conf, facts):
    '''\
    Removes metadata for this episode.
    '''
    path_printed = False

    # metadata XML
    xml_path = get_episode_metadata_path(path)
    if os.path.exists(xml_path):
        if not path_printed:
            print '\t%s' % os.path.basename(path)
            path_printed = True
        print '\t\tRemoving episode metadata...'
        rm_if_exists(xml_path)
    
    # image
    if conf.get('DOWNLOAD_IMAGES'):
        image_path = os.path.splitext(xml_path)[0]
        image_files = image_file_exists(image_path + '.*')
        if image_files:
            if not path_printed:
                print '\t%s' % os.path.basename(path)
                path_printed = True
            print '\t\tRemoving episode images...'
            for f in image_files:
                os.remove(f)

def is_season_metadata_complete(path, conf):
    '''\
    Returns true if all the metadata for the season at the given path looks
    to be complete (i.e. the expected files are there).
    '''
    if conf.get('DOWNLOAD_IMAGES'):
        # check for poster (folder.*)
        poster_found = image_file_exists(os.path.join(path, 'folder.*'))
        
        # check for banner (banner.*)
        banner_found = image_file_exists(os.path.join(path, 'banner.*'))
        
        # check for backdrops (backdrop*)
        backdrop_found = image_file_exists(os.path.join(path, 'backdrop*'))
        
        if poster_found and banner_found and backdrop_found:
            return True
        else:
            return False
    
    return True

def process_season(path, conf, facts):
    '''\
    Retrieve and write metadata for this season.
    '''
    # check if metadata has already been written for this season
    if is_season_metadata_complete(path, conf):
        return
    
    # no metadata yet, so fetch it
    try:
        print '\tRetrieving season metadata...'
        
        # the .decode call is necessary because the series title may have non-
        # ASCII characters in it. In Linux, path names are UTF-8 encoded, so
        # we need to tell Python that so it can use that information for
        # encoding later (the tvdb_api forces re-encoding to UTF-8).
        result = tvdb[facts['series_title'].decode('utf-8')]
        
        # download the image files
        if conf.get('DOWNLOAD_IMAGES'):
            # the poster, saved as folder.jpg
            image_path = os.path.join(path, 'folder')
            # only attempt to download an image if one does not already exist
            if not image_file_exists(image_path + '.*'):
                print '\tDownloading season poster...'
                images = result['_banners'].get('season', { }).get('season', { }).values()
                # filter to only the items that are for this season
                images = filter(lambda s: s.get('season') == str(facts['season_number']), images)
                if images:
                    # sort the images by rating
                    images.sort(key=lambda i: i.get('rating'))
                    images.reverse()
                    # grab the best one
                    image = images[0]
                    image_url = image['_bannerpath']
                    # the utf-8 conversion is important because otherwise if the
                    # image_path contains non-ASCII characters, Python won't
                    # know how to put them together (the ext is ASCII; path is
                    # UTF-8 on Linux).
                    image_path += os.path.splitext(image_url)[1].encode('utf-8')
                    urllib.urlretrieve(image_url, image_path)
                else:
                    # no posters exist, drop a marker file so we don't check again
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
            
            # the season image, saved as banner.jpg
            image_path = os.path.join(path, 'banner')
            # only attempt to download an image if one does not already exist
            if not image_file_exists(image_path + '.*'):
                print '\tDownloading season banner...'
                images = result['_banners'].get('season', { }).get('seasonwide', { }).values()
                # filter to only the items that are for this season
                images = filter(lambda s: s.get('season') == str(facts['season_number']), images)
                if images:
                    # sort the images by rating
                    images.sort(key=lambda i: i.get('rating'))
                    images.reverse()
                    # grab the best one
                    image = images[0]
                    image_url = image['_bannerpath']
                    # the utf-8 conversion is important because otherwise if the
                    # image_path contains non-ASCII characters, Python won't
                    # know how to put them together (the ext is ASCII; path is
                    # UTF-8 on Linux).
                    image_path += os.path.splitext(image_url)[1].encode('utf-8')
                    urllib.urlretrieve(image_url, image_path)
                else:
                    # no season images exist, drop a marker file so we don't check
                    # again
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
            
            # all fanart images, saved as backdropX.jpg, where X is an
            # incrementing number, up to conf.MAX_NUMBER_OF_BACKDROPS.
            # only attempt to download an image if one does not already exist
            if not image_file_exists(os.path.join(path, 'backdrop*')):
                print '\tDownloading season backdrops...'
                images = result['_banners'].get('season', { }).get('fanart', { }).values()
                # filter to only the items that are for this season
                images = filter(lambda s: s.get('season') == str(facts['season_number']), images)
                if images:
                    # sort the images by rating
                    images.sort(key=lambda i: i.get('rating'))
                    images.reverse()
                    # take up to the max number of backdrops setting
                    images = images[:conf.get('MAX_NUMBER_OF_BACKDROPS', 3)]
                    
                    for i,image in enumerate(images):
                        image_path = os.path.join(path, 'backdrop') + str(i > 0 and i or '')
                        image_url = image['_bannerpath']
                        # the utf-8 conversion is important because otherwise if the
                        # image_path contains non-ASCII characters, Python won't
                        # know how to put them together (the ext is ASCII; path is
                        # UTF-8 on Linux).
                        image_path += os.path.splitext(image_url)[1].encode('utf-8')
                        urllib.urlretrieve(image_url, image_path)
                else:
                    # no posters exist, drop a marker file so we don't check again
                    image_path = os.path.join(path, 'backdrop')
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
    
    except tvdb_exceptions.tvdb_exception, e:
        print '\t\t[ERROR] ' + repr(e)

def clean_season(path, conf, facts):
    '''\
    Removes metadata for this season.
    '''
    if conf.get('DOWNLOAD_IMAGES'):
        # the poster, saved as folder.jpg
        image_path = os.path.join(path, 'folder')
        image_files = image_file_exists(image_path + '.*')
        if image_files:
            print '\tRemoving season poster...'
            for f in image_files:
                os.remove(f)
        
        # the season image, saved as banner.jpg
        image_path = os.path.join(path, 'banner')
        image_files = image_file_exists(image_path + '.*')
        if image_files:
            print '\tRemoving season banner...'
            for f in image_files:
                os.remove(f)
        
        # all fanart images, saved as backdropX.jpg, where X is an
        # incrementing number, up to conf.MAX_NUMBER_OF_BACKDROPS.
        image_path = os.path.join(path, 'backdrop')
        image_files = image_file_exists(image_path + '*')
        if image_files:
            print '\tRemoving season backdrops...'
            for f in image_files:
                os.remove(f)

def get_series_metadata_path(path):
    '''\
    Returns the expected metadata path for this series directory.
    '''
    return os.path.join(path, 'series.xml')

def is_series_metadata_complete(path, conf):
    '''\
    Returns true if all the metadata for the series at the given path looks
    to be complete (i.e. the expected files are there).
    '''
    # check if series.xml exists in the series dir
    series_xml_path = get_series_metadata_path(path)
    
    if not os.path.exists(series_xml_path):
        return False
    
    # images are optional, dependent on the setting. If no image is available,
    # the .noimage file is dropped. Image files are named either 'folder', 
    # 'banner' or 'backdrop' with a .jpg, .png or .noimage extension.
    if conf.get('DOWNLOAD_IMAGES'):
        # check for poster (folder.*)
        poster_found = image_file_exists(os.path.join(path, 'folder.*'))
        
        # check for banner (banner.*)
        banner_found = image_file_exists(os.path.join(path, 'banner.*'))
        
        # check for backdrops (backdrop*)
        backdrop_found = image_file_exists(os.path.join(path, 'backdrop*'))
        
        if poster_found and banner_found and backdrop_found:
            return True
        else:
            return False
    
    return True

def process_series(path, conf, facts):
    '''\
    Retrieve and write metadata for this series.
    '''
    # check if metadata has already been written for this series
    if is_series_metadata_complete(path, conf):
        return
    
    # no metadata yet, so fetch it
    try:
        print '\tRetrieving series metadata...'
        
        # the .decode call is necessary because the series title may have non-
        # ASCII characters in it. In Linux, path names are UTF-8 encoded, so
        # we need to tell Python that so it can use that information for
        # encoding later (the tvdb_api forces re-encoding to UTF-8).
        result = tvdb[facts['series_title'].decode('utf-8')]
        
        # data has been fetched; write it out
        xml_path = get_series_metadata_path(path)
        
        # the .get method is used for non-essential attributes
        xml_root = ET.Element('Series')
        x = ET.SubElement(xml_root, 'id')
        x.text = result['seriesid']
        x = ET.SubElement(xml_root, 'Overview')
        x.text = result.data.get('overview')
        x = ET.SubElement(xml_root, 'SeriesName')
        x.text = result['seriesname']
        x = ET.SubElement(xml_root, 'Actors')
        x.text = result.data.get('actors')
        x = ET.SubElement(xml_root, 'Genre')
        x.text = result.data.get('genre')
        x = ET.SubElement(xml_root, 'ContentRating')
        x.text = result.data.get('contentrating')
        x = ET.SubElement(xml_root, 'Runtime')
        x.text = result.data.get('runtime')
        x = ET.SubElement(xml_root, 'Rating')
        x.text = result.data.get('rating')
        x = ET.SubElement(xml_root, 'Status')
        x.text = result.data.get('status')
        x = ET.SubElement(xml_root, 'Network')
        x.text = result.data.get('network')
        
        # these attributes are not used by MediaBrowser, but we'll store them
        # anyway
        x = ET.SubElement(xml_root, 'AirsDayOfWeek')
        x.text = result.data.get('airs_dayofweek')
        x = ET.SubElement(xml_root, 'AirsTime')
        x.text = result.data.get('airs_time')
        x = ET.SubElement(xml_root, 'LastUpdated')
        x.text = result.data.get('lastupdated')
        x = ET.SubElement(xml_root, 'Added')
        x.text = result.data.get('added')
        x = ET.SubElement(xml_root, 'IMdbId')
        x.text = result.data.get('imdbid')
        x = ET.SubElement(xml_root, 'FirstAired')
        x.text = result.data.get('firstaired')
        
        xml = ET.ElementTree(xml_root)
        mkdir_if_not_exists(xml_path)
        # TODO: somehow pretty print this?
        xml.write(xml_path)
        
        # download the image files
        if conf.get('DOWNLOAD_IMAGES'):
            # the poster, saved as folder.jpg
            image_path = os.path.join(path, 'folder')
            # only attempt to download an image if one does not already exist
            if not image_file_exists(image_path + '.*'):
                print '\tDownloading series poster...'
                # TODO: work out which res is appropriate
                images = result['_banners'].get('poster')
                if images:
                    # HACK: we're just taking the first res available
                    # after resolving the res, a banner-id, banner-info dict is
                    # returned. We don't care about the id, so just take the
                    # banner-info.
                    images = images[images.keys()[0]].values()
                    # sort the images by rating and take the best rating one
                    images.sort(key=lambda i: i.get('rating'))
                    images.reverse()
                    image = images[0]
                    image_url = image['_bannerpath']
                    # the utf-8 conversion is important because otherwise if the
                    # image_path contains non-ASCII characters, Python won't
                    # know how to put them together (the ext is ASCII; path is
                    # UTF-8 on Linux).
                    image_path += os.path.splitext(image_url)[1].encode('utf-8')
                    urllib.urlretrieve(image_url, image_path)
                else:
                    # no posters exist, drop a marker file so we don't check again
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
            
            # the series image, saved as banner.jpg
            image_path = os.path.join(path, 'banner')
            # only attempt to download an image if one does not already exist
            if not image_file_exists(image_path + '.*'):
                print '\tDownloading series banner...'
                images = result['_banners'].get('series', { }).get('graphical')
                if images:
                    # a banner-id, banner-info dict is returned. We don't care about
                    # the id, so just take the banner-info.
                    images = images.values()
                    # sort the images by rating and take the best rating one
                    images.sort(key=lambda i: i.get('rating'))
                    images.reverse()
                    image = images[0]
                    image_url = image['_bannerpath']
                    # the utf-8 conversion is important because otherwise if the
                    # image_path contains non-ASCII characters, Python won't
                    # know how to put them together (the ext is ASCII; path is
                    # UTF-8 on Linux).
                    image_path += os.path.splitext(image_url)[1].encode('utf-8')
                    urllib.urlretrieve(image_url, image_path)
                else:
                    # no series images exist, drop a marker file so we don't check
                    # again
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
            
            # all fanart images, saved as backdropX.jpg, where X is an
            # incrementing number, up to conf.MAX_NUMBER_OF_BACKDROPS.
            # only attempt to download an image if one does not already exist
            if not image_file_exists(os.path.join(path, 'backdrop*')):
                print '\tDownloading series backdrops...'
                # TODO: work out which res is appropriate
                images = result['_banners'].get('fanart')
                if images:
                    # HACK: we're just taking the first res available
                    # after resolving the res, a banner-id, banner-info dict is
                    # returned. We don't care about the id, so just take the
                    # banner-info.
                    images = images[images.keys()[0]].values()
                    # sort the images by rating
                    images.sort(key=lambda i: i.get('rating'))
                    images.reverse()
                    # take up to the max number of backdrops setting
                    images = images[:conf.get('MAX_NUMBER_OF_BACKDROPS', 3)]
                    
                    for i,image in enumerate(images):
                        image_path = os.path.join(path, 'backdrop') + str(i > 0 and i or '')
                        image_url = image['_bannerpath']
                        # the utf-8 conversion is important because otherwise if the
                        # image_path contains non-ASCII characters, Python won't
                        # know how to put them together (the ext is ASCII; path is
                        # UTF-8 on Linux).
                        image_path += os.path.splitext(image_url)[1].encode('utf-8')
                        urllib.urlretrieve(image_url, image_path)
                else:
                    # no posters exist, drop a marker file so we don't check again
                    image_path = os.path.join(path, 'backdrop')
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
    
    except tvdb_exceptions.tvdb_exception, e:
        print '\t\t[ERROR] ' + repr(e)

def clean_series(path, conf, facts):
    '''\
    Removes metadata for this series.
    '''
    # metadata XML
    xml_path = get_series_metadata_path(path)
    if os.path.exists(xml_path):
        print '\tRemoving series metadata...'
        rm_if_exists(xml_path)
    
    if conf.get('DOWNLOAD_IMAGES'):
        # the poster, saved as folder.jpg
        image_path = os.path.join(path, 'folder')
        image_files = image_file_exists(image_path + '.*')
        if image_files:
            print '\tRemoving series poster...'
            for f in image_files:
                os.remove(f)
        
        # the season image, saved as banner.jpg
        image_path = os.path.join(path, 'banner')
        image_files = image_file_exists(image_path + '.*')
        if image_files:
            print '\tRemoving series banner...'
            for f in image_files:
                os.remove(f)
        
        # all fanart images, saved as backdropX.jpg, where X is an
        # incrementing number, up to conf.MAX_NUMBER_OF_BACKDROPS.
        image_path = os.path.join(path, 'backdrop')
        image_files = image_file_exists(image_path + '*')
        if image_files:
            print '\tRemoving series backdrops...'
            for f in image_files:
                os.remove(f)

def get_movie_metadata_path(path):
    '''\
    Returns the expected metadata path for this movie.
    '''
    return os.path.join(path, 'movie.xml')

def is_movie_metadata_complete(path, conf):
    '''\
    Returns true if all the metadata for the movie at the given path looks
    to be complete (i.e. the expected files are there).
    '''
    # check if movie.xml exists in the series dir
    movie_xml_path = get_movie_metadata_path(path)
    
    if not os.path.exists(movie_xml_path):
        return False
    
    # images are optional, dependent on the setting. If no image is available,
    # the .noimage file is dropped. Image files are named either 'folder' 
    # or 'backdrop' with a .jpg, .png or .noimage extension.
    if conf.get('DOWNLOAD_IMAGES'):
        # check for poster (folder.*)
        poster_found = image_file_exists(os.path.join(path, 'folder.*'))
        
        # check for backdrops (backdrop*)
        backdrop_found = image_file_exists(os.path.join(path, 'backdrop*'))
        
        if poster_found and backdrop_found:
            return True
        else:
            return False
    
    return True

def process_movie(path, conf, facts):
    '''\
    Retrieve and write metadata for this movie.
    '''
    # check if metadata has already been written for this movie
    if is_movie_metadata_complete(path, conf):
        return
    
    # no metadata yet, so fetch it
    try:
        print '\tRetrieving movie metadata...'
        
        movie_title = facts['movie_title']
        # the .decode call is necessary because the series title may have non-
        # ASCII characters in it. In Linux, path names are UTF-8 encoded, so
        # we need to tell Python that so it can use that information for
        # encoding later.
        results = tmdb.search(movie_title.decode('utf-8'))
        if results:
            # using .info() returns the full record, not just a common subset
            result = results[0].info()
        else:
            print '\t\t[ERROR] No matches found for the title \'%s\'' % movie_title
            return
        
        # data has been fetched; write it out
        xml_path = get_movie_metadata_path(path)
        
        # the .get method is used for non-essential attributes
        xml_root = ET.Element('Title')
        x = ET.SubElement(xml_root, 'LocalTitle')
        x.text = result['name']
        x = ET.SubElement(xml_root, 'OriginalTitle')
        x.text = result['original_name']
        x = ET.SubElement(xml_root, 'Description')
        x.text = result.get('overview')
        x = ET.SubElement(xml_root, 'Tagline')
        x.text = result.get('tagline')
        x = ET.SubElement(xml_root, 'IMDBId')
        x.text = result.get('imdb_id')
        
        # parse the production year manually
        date_released = result.get('released')
        if date_released:
            try:
                date_released = datetime.strptime('%Y-%m-%d', date_released)
                x = ET.SubElement(xml_root, 'ProductionYear')
                x.text = date_released.year
            except ValueError, e:
                # could not parse the date; whatever.
                pass
        
        x = ET.SubElement(xml_root, 'IMDBrating')
        x.text = result.get('rating')
        x = ET.SubElement(xml_root, 'MPAARating')
        x.text = result.get('certification')
        
        persons = ET.SubElement(xml_root, 'Persons')
        cast = result.get('cast', { })
        for actor in cast.get('actor', [ ]):
            try:
                actor_id = actor['id']
                actor_name = actor['name']
                actor_role = actor['character']
                person = ET.SubElement(persons, 'Person')
                # the ID field isn't used by Media Browser, but seems useful for
                # other uses.
                x = ET.SubElement(person, 'Id')
                x.text = actor_id
                x = ET.SubElement(person, 'Type')
                x.text = 'Actor'
                x = ET.SubElement(person, 'Name')
                x.text = actor_name
                x = ET.SubElement(person, 'Role')
                x.text = actor_role
            except KeyError, e:
                # incomplete metadata, meh.
                pass
        
        for director in cast.get('director', [ ]):
            try:
                director_id = director['id']
                director_name = director['name']
                person = ET.SubElement(persons, 'Person')
                # the ID field isn't used by Media Browser, but seems useful for
                # other uses.
                x = ET.SubElement(person, 'Id')
                x.text = director_id
                x = ET.SubElement(person, 'Type')
                x.text = 'Director'
                x = ET.SubElement(person, 'Name')
                x.text = director_name
            except KeyError, e:
                # incomplete metadata, meh.
                pass
        
        genres = ET.SubElement(xml_root, 'Genres')
        categories = result.get('categories', { })
        for genre in categories.get('genre', { }).keys():
                x = ET.SubElement(genres, 'Genre')
                x.text = genre
        
        studios = ET.SubElement(xml_root, 'Studios')
        for studio in result.get('studios', { }).keys():
                x = ET.SubElement(studios, 'Studio')
                x.text = studio
        
        # these attributes are not used by MediaBrowser, but we'll store them
        # anyway
        x = ET.SubElement(xml_root, 'Runtime')
        x.text = result.get('runtime')
        x = ET.SubElement(xml_root, 'Id')
        x.text = result['id']
        x = ET.SubElement(xml_root, 'Released')
        x.text = result.get('released')
        x = ET.SubElement(xml_root, 'TrailerURL')
        x.text = result.get('trailer')
        x = ET.SubElement(xml_root, 'Budget')
        x.text = result.get('budget')
        x = ET.SubElement(xml_root, 'AlternativeName')
        x.text = result.get('alternative_name')
        
        xml = ET.ElementTree(xml_root)
        mkdir_if_not_exists(xml_path)
        # TODO: somehow pretty print this?
        xml.write(xml_path)
        
        # download the image files
        if conf.get('DOWNLOAD_IMAGES'):
            images = result['images']
            # the poster, saved as folder.jpg
            image_path = os.path.join(path, 'folder')
            # only attempt to download an image if one does not already exist
            if not image_file_exists(image_path + '.*'):
                print '\tDownloading movie poster...'
                if images.posters:
                    # HACK: don't know how to pick the best one, so we'll just
                    #       take the first.
                    image = images.posters[0]
                    image_url = image['original']
                    # the utf-8 conversion is important because otherwise if the
                    # image_path contains non-ASCII characters, Python won't
                    # know how to put them together (the ext is ASCII; path is
                    # UTF-8 on Linux).
                    image_path += os.path.splitext(image_url)[1].encode('utf-8')
                    urllib.urlretrieve(image_url, image_path)
                else:
                    # no posters exist, drop a marker file so we don't check again
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
            
            # all fanart images, saved as backdropX.jpg, where X is an
            # incrementing number, up to conf.MAX_NUMBER_OF_BACKDROPS.
            # only attempt to download an image if one does not already exist
            if not image_file_exists(os.path.join(path, 'backdrop*')):
                print '\tDownloading movie backdrops...'
                # TODO: work out which res is appropriate
                if images.backdrops:
                    # HACK: don't know how to pick the best one, so we'll just
                    #       take the first X, up to the max number of backdrops
                    #       setting
                    backdrops = images.backdrops[:conf.get('MAX_NUMBER_OF_BACKDROPS', 3)]
                    
                    for i,image in enumerate(backdrops):
                        image_path = os.path.join(path, 'backdrop') + str(i > 0 and i or '')
                        image_url = image['original']
                        # the utf-8 conversion is important because otherwise if the
                        # image_path contains non-ASCII characters, Python won't
                        # know how to put them together (the ext is ASCII; path is
                        # UTF-8 on Linux).
                        image_path += os.path.splitext(image_url)[1].encode('utf-8')
                        urllib.urlretrieve(image_url, image_path)
                else:
                    # no posters exist, drop a marker file so we don't check again
                    image_path = os.path.join(path, 'backdrop')
                    image_path = image_path + NO_IMAGE_EXTENSION
                    open(image_path, 'a').close()
    
    except KeyError, e:
        print '\t\t[ERROR] ' + repr(e)

def clean_movie(path, conf, facts):
    '''\
    Removes metadata for this movie.
    '''
    # metadata XML
    xml_path = get_movie_metadata_path(path)
    if os.path.exists(xml_path):
        print '\tRemoving movie metadata...'
        rm_if_exists(xml_path)
    
    if conf.get('DOWNLOAD_IMAGES'):
        # the poster, saved as folder.jpg
        image_path = os.path.join(path, 'folder')
        image_files = image_file_exists(image_path + '.*')
        if image_files:
            print '\tRemoving movie poster...'
            for f in image_files:
                os.remove(f)
        
        # all fanart images, saved as backdropX.jpg, where X is an
        # incrementing number, up to conf.MAX_NUMBER_OF_BACKDROPS.
        image_path = os.path.join(path, 'backdrop')
        image_files = image_file_exists(image_path + '*')
        if image_files:
            print '\tRemoving movie backdrops...'
            for f in image_files:
                os.remove(f)
