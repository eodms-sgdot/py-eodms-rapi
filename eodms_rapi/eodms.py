##############################################################################
# MIT License
# 
# Copyright (c) 2021 Her Majesty the Queen in Right of Canada, as 
# represented by the President of the Treasury Board
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.
# 
##############################################################################

import os
import sys
import requests
import logging
import logging.config
import traceback
import urllib
import json
import csv
import datetime
import pytz
# import tzlocal
import time
import pprint
import re
import dateutil.parser
from dateutil.tz import tzlocal
from urllib.parse import urlencode
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree

from tqdm.auto import tqdm

from .geo import EODMSGeo

# FIELD_MAP = {'RCMImageProducts': 
                # {
                    # 'Incidence Angle': 'SENSOR_BEAM_CONFIG.INCIDENCE_LOW,'\
                                        # 'SENSOR_BEAM_CONFIG.INCIDENCE_HIGH', 
                    # # 'BEAM_MODE_TYPE': 'RCM.SBEAM',
                    # 'Within Orbit Tube': 'RCM.WITHIN_ORBIT_TUBE'
                # }, 
            # 'Radarsat1': 
                # {
                    # 'Pixel Spacing': 'ARCHIVE_RSAT1.SAMPLED_PIXEL_SPACING_PAN', 
                    # 'Incidence Angle': 'SENSOR_BEAM_CONFIG.INCIDENCE_LOW,'\
                                        # 'SENSOR_BEAM_CONFIG.INCIDENCE_HIGH', 
                    # # 'BEAM_MODE': 'RSAT1.SBEAM', 
                    # 'Beam Mnemonic': 'RSAT1.BEAM_MNEMONIC', 
                    # 'Orbit': 'RSAT1.ORBIT_ABS'
                # }, 
            # 'Radarsat2':
                # {
                    # 'Pixel Spacing': 'ARCHIVE_RSAT2.SAMPLED_PIXEL_SPACING_PAN', 
                    # 'Incidence Angle': 'SENSOR_BEAM_CONFIG.INCIDENCE_LOW,'\
                                        # 'SENSOR_BEAM_CONFIG.INCIDENCE_HIGH', 
                    # # 'BEAM_MODE': 'RSAT2.SBEAM', 
                    # 'Beam Mnemonic': 'RSAT2.BEAM_MNEMONIC'
                # }, 
            # 'NAPL':
                # {
                    # 'Colour': 'PHOTO.SBEAM', 
                    # 'Roll': 'ROLL.ROLL_NUMBER'
                    # # 'PREVIEW_AVAILABLE': 'PREVIEW_AVAILABLE'
                # }
            # }
# logger = logging.getLogger('EODMSRAPI')

# warn_ch = logging.StreamHandler()
# warn_ch.setLevel(logging.WARNING)
# formatter = logging.Formatter('| %(name)s | %(levelname)s | %(message)s', '%Y-%m-%d %H:%M:%S')
# warn_ch.setFormatter(formatter)
# logger.addHandler(warn_ch)

# sh = logging.StreamHandler()
# sh.setLevel(logging.DEBUG)
# formatter = logging.Formatter('| %(name)s | %(levelname)s | %(message)s', '%Y-%m-%d %H:%M:%S')
# sh.setFormatter(formatter)
# logger.addHandler(sh)

OTHER_FORMAT = '| %(name)s | %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'
# INFO_FORMAT = '| %(name)s | %(message)s', '%Y-%m-%d %H:%M:%S'

# LOG_CONFIG = {'version': 1,
              # 'formatters': {'error': {'format': OTHER_FORMAT}, 
                            # 'warning': {'format': OTHER_FORMAT}, 
                            # 'debug': {'format': OTHER_FORMAT}, 
                            # 'info': {'format': INFO_FORMAT}}, 
              # 'handlers': {'console':{'class': 'logging.StreamHandler',
                                     # 'formatter': 'info',
                                     # 'level': logging.INFO}},
              # 'root': {'handlers':('console')}}
              
logger = logging.getLogger('EODMSRAPI')

# Set handler for output to terminal
logger.setLevel(logging.DEBUG)
ch = logging.NullHandler()
# formatter = logging.Formatter('| %(name)s | %(levelname)s: %(message)s') #, '%Y-%m-%d %H:%M:%S')
formatter = logging.Formatter('| %(name)s | %(asctime)s | %(levelname)s: ' \
                                '%(message)s', '%Y-%m-%d %H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)

RECORD_KEYS = ["recordId", "overviewUrl", "collectionId", "metadata2", \
            "rapiOrderUrl", "geometry", "title", "orderExecuteUrl", \
            "thumbnailUrl", "metadataUrl", "isGeorectified", \
            "collectionTitle", "isOrderable", "thisRecordUrl", \
            "metadata"]

class QueryError:
    """
    The QueryError class is used to store error information for a query.
    """
    
    def __init__(self, msgs):
        """
        Initializer for QueryError object which stores an error message.
        
        :param msgs: The error message to print.
        :type msgs: str
        """
        
        self.msgs = msgs
        
    def _get_msgs(self, as_str=False):
        if as_str:
            return ' '.join(self.msgs)
        
        return self.msgs
        
    def _set_msgs(self, msgs):
        self.msgs = msgs

class EODMSRAPI():
    
    def __init__(self, username, password):
    
        # print("\nInitializing EODMSRAPI, please wait...")
        
        # Create session
        self._session = requests.Session()
        self._session.auth = (username, password)
        
        self.rapi_root = "https://www.eodms-sgdot.nrcan-rncan.gc.ca/wes/rapi"
        
        self.rapi_collections = {}
        self.unsupport_collections = {}
        self.download_size = 0
        self.size_limit = None
        self.results = []
        self.res_mdata = None
        #self.default_queryLimit = 1000
        self.limit_interval = 1000
        self.name_conv = 'camel'
        self.res_format = 'raw'
        self.stdout_enabled = True
        
        # self.name_conv: Determines what type of format for the field names.
        #                    - 'words': The label with spaces and words will be returned.
        #                    - 'camel': The format will be lower camel case like 'camelCase'.
        #                    - 'upper': The format will be all uppercase with underscore for spaces.
        # self.res_format: The type of format to return.
        #                - 'raw': Returns the JSON results straight from the RAPI.
        #                - 'full': Returns a JSON with full metadata information.
        #                - 'geojson': Returns a FeatureCollection of the results
        #                            (requires geojson package).
        
        self.timeout_query = 120.0
        self.timeout_order = 180.0
        self.attempts = 4
        self.indent = 3
        self.aoi = None
        self.dates = None
        self.feats = None
        self.start = datetime.datetime.now()
        
        self.geo = EODMSGeo(self)
        
        self._map_fields()
        
        self._header = '| EODMSRAPI | '
        
        self.failed_status = ['CANCELLED', 'FAILED', 'EXPIRED', \
                            'DELIVERED', 'MEDIA_ORDER_SUBMITTED', \
                            'AWAITING_PAYMENT']
        
        # print("Initialization complete.")
        
        return None
        
    def _check_complete(self, complete_items, record_id):
        
        for i in complete_items:
            if i['recordId'] == record_id:
                return True
                
        return False
        
    def _check_auth(self, in_err):
        
        err_msg = in_err._get_msgs(True)
        if err_msg.find('401 - Unauthorized') > -1 or \
            (err_msg.find('HTTP Error: 401 Client Error') > -1 and \
            err_msg.find('Unauthorized') > -1):
            # Inform the user if the error was caused by an authentication 
            #   issue.
            err_msg = "An authentication error has occurred while " \
                        "trying to access the EODMS RAPI. Please try " \
                        "again with your EODMS username and password."
            self._log_msg(err_msg, 'error')
            return True
            
        return False
        
    def _convert_date(self, date, in_forms=['%Y-%m-%d %H:%M:%S.%f'], 
                out='string', out_form="%Y%m%d_%H%M%S"):
        
        # print("date: %s" % date)
        #print("type(date): %s" % type(date))
        if isinstance(date, datetime.datetime):
            if out_form == 'iso':
                return date.isoformat()
            else:
                return date.strftime(out_form)
            
        elif isinstance(date, str):
            # if not '.' in date:
                # date += '.0'
                
            if isinstance(in_forms, str):
                in_forms = [in_forms]
            
            # print("in_forms: %s" % in_forms)
            for form in in_forms:
                try:
                    out_date = datetime.datetime.strptime(date, form)
                    if out == 'date':
                        return out_date
                    else:
                        return out_date.strftime(out_form)
                except ValueError as e:
                    msg = "%s. Date will not be included in query." % \
                        str(e).capitalize()
                    self._log_msg(msg, 'warning')
                    pass
                except:
                    msg = traceback.format_exc()
                    self._log_msg(msg, 'warning')
                    pass
                    
    def _convert_field(self, field, collection=None, field_type='search'):
        
        fields = self.get_availableFields(collection, 'all')[field_type]
        
        for k, v in fields.items():
            if field == k:
                return v['id']
            elif field == v['id']:
                return k
        
    def _get_conv(self, val):
        
        if self.name_conv == 'words' or self.name_conv == 'upper':
            # Remove bracketted string for 'upper'
            if self.name_conv == 'upper':
                val = re.sub(r"\([^()]*\)", "", val)
                val = val.strip()
        
            # Separate into words
            if val.find(' ') > -1:
                words = val.split(' ')
            else:
                words = re.findall('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=' \
                        '[A-Z])(?=[A-Z][a-z])|$)', val)
                words = [w[0].upper() + w[1:] for w in words]
            
            if self.name_conv == 'words':
                return ' '.join(words)
            elif self.name_conv == 'upper':
                # print("words2: %s" % words)
                return '_'.join([w.upper() for w in words])
        else:
            return self._to_camelCase(val)
        
    # def _download_image(self, url, dest_fn):
        # """
        # Downloads an image from the EODMS.
        
        # @type  url:     str
        # @param url:     The URL where the image is stored on the EODMS.
        # @type  dest_fn: str
        # @param dest_fn: The destination filename where the image will be 
                        # saved.
        # """
        
        # # Get authentication info and extract the username and password
        # auth = self._session.auth
        # user = auth[0]
        # pwd = auth[1]
        
        # # Setup basic authentication before downloading the file
        # pass_man = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        # pass_man.add_password(None, url, user, pwd)
        # authhandler = urllib.request.HTTPBasicAuthHandler(pass_man)
        # opener = urllib.request.build_opener(authhandler)
        # urllib.request.install_opener(opener)
        
        # # Download the file from the EODMS server
        # try:
            # urllib.request.urlretrieve(url, dest_fn, \
                # reporthook=self._print_progress)
        # except:
            # msg = "Unexpected error: %s" % traceback.format_exc()
            # # print("%s%s" % (self._header, msg))
            # logger.warning(msg)
            # pass
            
    def _download_image(self, url, dest_fn, fsize):
        '''
        Given a list of remote and local items, download the remote data if it is not already
        found locally

        Inputs:
          - remote_items: list of tuples containing (remote url, remote filesize)
          - local_items: list of local paths where data will be saved

        Outputs:
          - local_items: same as input 

        Assumptions:
          - length of remote_items and local_items must match
          - filenames in remote_items and local_items must be in sequence
          
        (Adapted from the eodms-api-client (https://pypi.org/project/eodms-api-client/) developed by Mike Brady)
        '''
        # remote_urls = [f[0] for f in remote_items]
        # remote_sizes = [f[1] for f in  remote_items]
        # for remote, expected_size, local in zip(remote_urls, remote_sizes, local_items):
        # # if we have an existing local file, check the filesize against the manifest
        if os.path.exists(dest_fn):
            # if all-good, continue to next file
            if os.stat(dest_fn).st_size == fsize:
                msg = "No download necessary. " \
                    "Local file already exists: %s" % dest_fn
                self._log_msg(msg)
                return None
            # otherwise, delete the incomplete/malformed local file and redownload
            else:
                msg = 'Filesize mismatch with %s. Re-downloading...' % \
                    os.path.basename(dest_fn)
                self._log_msg(msg, 'warning')
                os.remove(dest_fn)
                
        # use streamed download so we can wrap nicely with tqdm
        with self._session.get(url, stream=True) as stream:
            with open(dest_fn, 'wb') as pipe:
                with tqdm.wrapattr(
                    pipe,
                    method='write',
                    miniters=1,
                    total=fsize,
                    desc="%s%s" % (self._header, os.path.basename(dest_fn))
                ) as file_out:
                    for chunk in stream.iter_content(chunk_size=1024):
                        file_out.write(chunk)
                        
        msg = '%s has been downloaded.' % dest_fn
        self._log_msg(msg)
                        
        # return local_items
            
    def _fetch_metadata(self, max_workers=4, len_timeout=20.0):
        """
        Fetches all metadata for a given record
        
        (Adapted from: eodms-api-client (https://pypi.org/project/eodms-api-client/)
            developed by Mike Brady)
            
        :type  max_workers: int
        :param max_workers: The number of threads used for retrieving the metadata.
        :type  len_timeout: float
        :param len_timeout: The length of time in seconds before the thread returns
                            a timeout warning.
                            
        :rtype:  list
        :return: A list containing the metadata for all items in the self.results
        """
        
        metadata_fields = self._get_metaKeys()
        
        if isinstance(metadata_fields, QueryError):
            msg = "Could not generate metadata for the results."
            # print("\n%sWARNING: %s" % (self._header, msg))
            self._log_msg(msg, 'warning')
            return None
        
        # meta_urls = [(record, record['thisRecordUrl']) for record in \
                    # self.results]
        n_urls = len(self.results)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            res = list(
                tqdm(
                    executor.map(
                        self._fetch_single_record_metadata,
                        self.results,
                        [metadata_fields] * n_urls,
                        [len_timeout] * n_urls, 
                    ),
                    desc='%sFetching result metadata' % self._header,
                    total=n_urls,
                    miniters=1,
                    unit='item'
                )
            )
        
        return res
        
        # out_res = []
        # for r in self.results['results']:
            # full_rec = {}
            # full_rec['Record ID'] = r['recordId']
            # full_rec['Title'] = r['title']
            # full_rec['Collection'] = r['collectionId']
            # full_rec['Thumbnail URL'] = r['thumbnailUrl']
            # full_rec['Record URL'] = r['thisRecordUrl']
            
            # # Parse the metadata
            # for m in r['metadata2']:
                # full_rec[m['label']] = m['value']
                
            # out_res.append(full_rec)
            
        # return out_res
        
    def _fetch_single_record_metadata(self, record, keys, timeout):
        '''
        Fetch a single image's metadata
        
        (Adapted from: eodms-api-client (https://pypi.org/project/eodms-api-client/)
            developed by Mike Brady)
        
        Args:
            record (dict): A dictionary of an image record.
            keys (list): A list of metadata keys.
            timeout (float): The time in seconds to wait before timing out.
            
        Returns:
            dict: Dictionary containing the keys and geometry metadata for 
                    the given image.
        '''
        
        metadata = {}
        #r = self._session.get(url, timeout=timeout)
        # print("record['thisRecordUrl']: %s" % record['thisRecordUrl'])
        r = self._submit(record['thisRecordUrl'], timeout, as_json=False)
        
        if r is None: return None
        
        if isinstance(r, QueryError):
            err_msg = "Could not retrieve full metadata due to: %s" % \
                    r._get_msgs(True)
            # print("\n%sWARNING: %s" % (self._header, err_msg))
            self._log_msg(err_msg, 'warning')
            # print("record: %s" % record)
            record['issue'] = err_msg
            image_res = record
        elif r.ok:
            image_res = r.json()
        else:
            err_msg = "Could not retrieve metadata."
            # print("\n%sWARNING: %s" % (self._header, err_msg))
            self._log_msg(err_msg, 'warning')
            image_res = record
            
        # print("response: %s" % response)
        
        # Add all record info
        record_info = {}
        
        # Add metadata at start
        metadata[self._get_conv('recordId')] = \
            image_res['recordId']
        metadata[self._get_conv('collectionId')] = \
            image_res['collectionId']
        metadata[self._get_conv('geometry')] = \
            image_res['geometry']
        
        exclude = [self._get_conv('recordId'), \
                    self._get_conv('collectionId'), \
                    self._get_conv('geometry'), \
                    self._get_conv('metadata2'), \
                    self._get_conv('metadata')]
                    
        for k in image_res.keys():
            if self._get_conv(k) not in exclude:
                metadata[self._get_conv(k)] = image_res[k]
        
        # recInfo_name = self._get_conv('Record Info')
        # # print("recInfo_name: %s" % recInfo_name)
        # # answer = input("Press enter...")
        # metadata[recInfo_name] = record_info
        
        # Add remaining metadata
        for k in keys:
            mdata_key = res_key = k
            if isinstance(k, list):
                mdata_key = k[0]
                res_key = k[1]
            #if res_key in image_res.keys():
            
            mdata_key = self._get_conv(mdata_key)
            
            # print("mdata_key: %s" % mdata_key)
            if mdata_key in exclude: continue
            
            if res_key in image_res.keys():
                metadata[mdata_key] = image_res[res_key]
            else:
                vals = [f[1] for f in image_res['metadata'] \
                        if f[0] == res_key]
                if len(vals) > 0:
                    metadata[mdata_key] = vals[0]
                # else:
                    # print("Missing metadata tag: %s" % res_key)
        
        if self.res_format == 'full':
            wkt_field = self._get_conv('WKT Geometry')
            metadata[wkt_field] = self.geo.convert_imageGeom(\
                                image_res['geometry'], 'wkt')
            
        #print("metadata: %s" % metadata)
        return metadata
        
    def _get_dateRange(self, items):
        
        eastern = pytz.timezone('US/Eastern')
        
        dates = []
        for i in items:
            
            # print()
            # for k, v in i.items():
                # print("%s: %s" % (k, v))
                
            # print()
            # print("_get_dateRange.i:")
            # print("    Contains 'dateRapiOrdered': %s" \
                # % str('dateRapiOrdered' in i.keys()))
            # print("    dateRapiOrdered: %s" % i.get('dateRapiOrdered'))
            
            if 'dateRapiOrdered' in i.keys():
                rapi_str = i['dateRapiOrdered']
                # print("rapi_str: %s" % rapi_str)
                # if 'Z' in rapi_str:
                    # tm_form = "%Y-%m-%dT%H:%M:%SZ"
                # else:
                    # tm_form = "%Y-%m-%dT%H:%M:%S"
                
                # rapi_date = datetime.datetime.strptime(rapi_str, tm_form)
                
                rapi_date = dateutil.parser.parse(rapi_str)
                
                # print("rapi_date: %s" % rapi_date)
                
                # Convert timezone to Eastern
                # loc_zone = tzlocal.get_localzone()
                rapi_date = rapi_date.astimezone(eastern)
            else:
                rapi_str = i['dateSubmitted']
                # Adjust to local time
                # if 'Z' in rapi_str:
                    # tm_form = "%Y-%m-%dT%H:%M:%SZ"
                # else:
                    # tm_form = "%Y-%m-%dT%H:%M:%S"
                # rapi_date = datetime.datetime.strptime(rapi_str, tm_form)
                
                rapi_date = dateutil.parser.parse(rapi_str)
                
                # Convert UTC to Eastern
                rapi_date = rapi_date.astimezone(eastern)
            
            dates.append(rapi_date)
        
        # if 'rapiSubmitted' in items[0].keys():
            # dates = [i['rapiSubmitted'] for i in items]
        # else:
            # dates = [i['dateSubmitted'] for i in items]
        # print("dates: %s" % dates)
        dates.sort()
        # print("dates: %s" % dates)
        
        start = dates[0]
        start = start - datetime.timedelta(hours=0, minutes=1)
        
        end = dates[len(dates) - 1]
        end = end + datetime.timedelta(hours=0, minutes=1)
        
        return (start, end)
        
    def _get_metaKeys(self):
        """
        Gets a list of metadata (fields) keys for a given collection
        
        :rtype:  list
        :return: A list of metadata keys
        """
        
        if not self.rapi_collections:
            self.get_collections()
            
        if self.rapi_collections is None: return None
            
        fields = self.rapi_collections[self.collection]['fields']\
                    ['results'].keys()
        sorted_lst = sorted(fields)
        
        # sorted_lst = [self._get_conv(k) for k in sorted_lst]
        # print("sorted_lst: %s" % sorted_lst)
        
        return sorted_lst
        
    # def _get_dateQueries(self):
        # """
        # Gets the date range based on the user's value
        # """
        
        # if self.dates is None or self.dates == '':
            # return ''
            
        
        
    def _get_exception(self, res, output='str'):
        """
        Gets the Exception text (or XML) from an request result.
        
        :type  in_xml: xml.etree.ElementTree.Element
        :param in_xml: The XML which will be checked for an exception.
        :type  output: str
        :param output: Determines what type of output should be returned 
                        (default='str').
                       Options:
                       - 'str': returns the XML Exception as a string
                       - 'tree': returns the XML Exception as a 
                                    xml.etree.ElementTree.Element
                                    
        :rtype:        str or xml.etree.ElementTree.Element
        :return:       The Exception XML text or element depending on 
                        the output variable.
        """
        
        in_str = res.text

        # If the input XML is None, return None
        if in_str is None: return None
        
        if self._is_json(in_str): return None
        
        # If the input is a string, convert it to a xml.etree.ElementTree.Element
        if isinstance(in_str, str):
            root = ElementTree.fromstring(in_str)
        else:
            root = in_str
        
        # Cycle through the input XML and location the ExceptionText element
        out_except = []
        for child in root.iter('*'):
            if child.tag.find('ExceptionText') > -1:
                if output == 'tree':
                    return child
                else:
                    return child.text
            elif child.tag.find('p') > -1:
                out_except.append(child.text)
                
        # except_txt = ' '.join(out_except)
        
        query_err = QueryError(out_except)
                
        return query_err
        
    def _get_fieldId(self, title, collection=None, field_type='search'):
        
        if collection is None: collection = self.collection
        
        field_id = None
        if field_type == 'search':
            fields = self.get_availableFields(name_type='all')[field_type]
            
            if not title in fields.keys():
                # Check field in field_map
                coll_fields = self.field_map[self.collection]
                ui_fields = [f['uiField'] for f in coll_fields]
                # print("coll_fields: %s" % coll_fields)
                # print([f['uiField'] for f in coll_fields])
                
                for f in coll_fields:
                    if f['uiField'].find(title) > -1 or \
                        f['uiField'].upper().replace(' ', '_')\
                            .find(title) > -1 or \
                        f['fieldId'].find(title) > -1:
                        field_id = f['fieldId']
                        break
            else:
                # Check in available fields
                for k, v in fields.items():
                    if title == k:
                        field_id = v['id']
            
            # If field_id is still None, check to make sure the
            #   title entry is an ID
            if field_id is None:
                if title in [f['id'] for f in fields.values()]:
                    return title
            
            return field_id
            
        elif field_type == 'results':
            fields = self.get_availableFields(name_type='all')[field_type]
            
            # Check if results fields
            for k, v in fields.items():
                if title == k:
                    field_id = v['id']
            
            # If field_id is still None, check to make sure the
            #   title entry is an ID
            if field_id is None:
                if title in [f['id'] for f in fields.values()]:
                    return title
                    
            return field_id
        
    # def _get_fieldId(self, words, collection=None, field_type='search'):
        # """
        # Gets the Field ID with a given title.
        
        # Args:
            # words (str or list): For exact match of the title, a string is 
                # used. When contains is True, the title can contain a list
                # of words which will be checked in order if more than one 
                # match is found.
            # collection (str): The Collection ID.
        # """
        
        # print("words: %s" % words)
        
        # # Convert words to a list if it's a string
        # if isinstance(words, str):
            # words = [words]
            
        # if collection is None: collection = self.collection
        
        # # Get the geometry field and add it to resultField
        # fields = self.get_availableFields(name_type='all')[field_type]
        
        # field_id = None
        
        # # found_fields = [(key, val) for key, val in fields.items() \
                        # # if w[0].lower() in key.lower()]
        
        # for w in words:
            # found_fields = {k: v for k, v in fields.items() \
                        # if w.lower() in k.lower()}
            
            # print("found_fields: %s" % found_fields)
            
            # if len(found_fields) == 1:
                # field_id = list(found_fields.values())[0].get('id')
                # return field_id
            # elif len(found_fields) > 1:
                # fields = found_fields
                
        # if field_id is None:
            # # Check if input words is actually a valid ID
            # word = ''.join(words)
            
            # # print([f['id'] for f in fields.values()])
            # if word in [f['id'] for f in fields.values()]:
                # return word
        
        # return field_id
        
    def _get_fieldType(self, coll_id, field_id):
        
        if not self.rapi_collections:
            self.get_collections()
            
        if self.rapi_collections is None: return None
        
        for k, v in self.rapi_collections[coll_id]['fields']['search'].items():
            if v['id'] == field_id:
                return v['datatype']
                
    def _get_itemFromOrders(self, item_id, orders):
        
        for o in orders:
            # print("item_id: '%s'" % item_id)
            # print("o['itemId']: '%s'" % o['itemId'])
            # print(str(o['itemId']) == str(item_id))
            if 'parameters' in o.keys():
                if 'ParentItemId' in o['parameters'].keys():
                    if str(o['parameters']['ParentItemId']) == str(item_id):
                        return o
            
            if str(o['itemId']) == str(item_id):
                return o
                
    def _is_json(self, my_json):
        """
        Checks to see in the input item is in JSON format.
        
        :type  my_json: str
        :param my_json: A string value from the requests results.
        """
        try:
            json_object = json.loads(my_json)
        except (ValueError, TypeError) as e:
            return False
        return True
        
    def _build_or(self, field_id, op, values, d_type):
        if d_type == 'String':
            # (RCM.BEAM_MNEMONIC='16M11' OR RCM.BEAM_MNEMONIC='16M11')
            or_query = '%s' % ' OR '.join(["%s%s'%s'" % \
                        (field_id, op, v) for v in values])
        else:
            or_query = '%s' % ' OR '.join(["%s%s%s" % \
                        (field_id, op, v) for v in values])
                        
        return or_query
        
    def _log_msg(self, messages, msg_type='info', log_indent='', 
                out_indent=''):
        
        if isinstance(messages, list) or isinstance(messages, tuple):
            log_msg, out_msg = messages
        elif isinstance(messages, str):
            log_msg = out_msg = messages
        else:
            print("EODMSRAPI._log_msg: 'messages' parameter not valid.")
            return None
        
        # Log the message
        log_msg = "%s%s" % (log_indent, log_msg)
        log_msg = log_msg.replace('\n', '\\n')
        log_msg = log_msg.replace('\t', '\\t')
        log_msg = log_msg.replace("'", "\\'")
        eval_str = "logger.%s('%s')" % (msg_type, log_msg)
        eval("logger.%s('%s')" % (msg_type, log_msg))
        
        # If stdout is disabled, don't print message to terminal
        if not self.stdout_enabled: return None
        
        # Print message to terminal
        if msg_type == 'info':
            msg = "%s%s%s" % (out_indent, self._header, out_msg)
        else:
            msg = "%s%s %s: %s" % (out_indent, self._header, \
                msg_type.upper(), out_msg)
                
        print(msg)
    
    def _map_fields(self):
        
        self.field_map = {'COSMO-SkyMed1': 
                [{'collectionId': 'COSMO-SkyMed1', 
                    'fieldId': 'csmed.ORBIT_ABS', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Absolute Orbit'}, 
                 {'collectionId': 'COSMO-SkyMed1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing', 
                    'rapiField': 'Spatial Resolution'}], 
            'DMC': 
                [{'collectionId': 'DMC', 
                    'fieldId': 'DMC.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover (Not all ' \
                            'vendors supply cloud cover data)', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'DMC', 
                    'fieldId': 'Spatial Resolution', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'DMC', 
                    'fieldId': 'DMC.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'Gaofen-1': 
                [{'collectionId': 'Gaofen-1', 
                    'fieldId': 'SATOPT.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'Gaofen-1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Gaofen-1', 
                    'fieldId': 'SATOPT.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'GeoEye-1': 
                [{'collectionId': 'GeoEye-1', 
                    'fieldId': 'GE1.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'GeoEye-1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'GeoEye-1', 
                    'fieldId': 'GE1.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'GeoEye-1', 
                    'fieldId': 'GE1.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'IKONOS': 
                [{'collectionId': 'IKONOS', 
                    'fieldId': 'IKONOS.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'IKONOS', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'IKONOS', 
                    'fieldId': 'IKONOS.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'IKONOS', 
                    'fieldId': 'IKONOS.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'IRS': 
                [{'collectionId': 'IRS', 
                    'fieldId': 'IRS.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'IRS', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'IRS', 
                    'fieldId': 'IRS.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'IRS', 
                    'fieldId': 'IRS.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'PlanetScope': 
                [{'collectionId': 'PlanetScope', 
                    'fieldId': 'SATOPT.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'PlanetScope', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'PlanetScope', 
                    'fieldId': 'SATOPT.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'QuickBird-2': 
                [{'collectionId': 'QuickBird-2', 
                    'fieldId': 'QB2.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'QuickBird-2', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'QuickBird-2', 
                    'fieldId': 'QB2.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'QuickBird-2', 
                    'fieldId': 'QB2.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'Radarsat1': [{'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat1', 
                    'fieldId': 'RSAT1.ORBIT_ABS', 
                    'uiField': 'Orbit', 
                    'rapiField': 'Absolute Orbit'}], 
            'Radarsat1RawProducts': [{'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.DATASET_ID', 
                    'uiField': 'Dataset Id', 
                    'rapiField': 'Dataset Id'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'ARCHIVE_CUF.ARCHIVE_FACILITY', 
                    'uiField': 'Archive Facility', 
                    'rapiField': 'Reception Facility'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'ARCHIVE_CUF.RECEPTION_FACILITY', 
                    'uiField': 'Reception Facility', 
                    'rapiField': 'Reception Facility'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat1RawProducts', 
                    'fieldId': 'RSAT1.ORBIT_ABS', 
                    'uiField': 'Orbit', 
                    'rapiField': 'Absolute Orbit'}], 
            'Radarsat2': [{'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'CATALOG_IMAGE.SEQUENCE_ID', 
                    'uiField': 'Sequence Id', 
                    'rapiField': 'Sequence Id'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.ANTENNA_ORIENTATION', 
                    'uiField': 'Look Direction', 
                    'rapiField': 'Look Direction'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.TR_POL', 
                    'uiField': 'Transmit Polarization', 
                    'rapiField': 'Transmit Polarization'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.REC_POL', 
                    'uiField': 'Receive Polarization', 
                    'rapiField': 'Receive Polarization'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.IMAGE_ID', 
                    'uiField': 'Image Identification', 
                    'rapiField': 'Image Id'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'RSAT2.ORBIT_REL', 
                    'uiField': 'Relative Orbit', 
                    'rapiField': 'Relative Orbit'}, 
                 {'collectionId': 'Radarsat2', 
                    'fieldId': 'ARCHIVE_IMAGE.ORDER_KEY', 
                    'uiField': 'Order Key', 
                    'rapiField': 'Order Key'}], 
            'Radarsat2RawProducts': [{'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.ANTENNA_ORIENTATION', 
                    'uiField': 'Look Orientation', 
                    'rapiField': 'Look Orientation'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Sensor Mode'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Position'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.TR_POL', 
                    'uiField': 'Transmit Polarization', 
                    'rapiField': 'Transmit Polarization'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.REC_POL', 
                    'uiField': 'Receive Polarization', 
                    'rapiField': 'Receive Polarization'}, 
                 {'collectionId': 'Radarsat2RawProducts', 
                    'fieldId': 'RSAT2.IMAGE_ID', 
                    'uiField': 'Image Identification', 
                    'rapiField': 'Image Id'}], 
            'RapidEye': [{'collectionId': 'RapidEye', 
                    'fieldId': 'RE.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'RapidEye', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'RapidEye', 
                    'fieldId': 'RE.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'RapidEye', 
                    'fieldId': 'RE.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'RCMImageProducts': [{'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Beam Mnemonic'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'SENSOR_BEAM_CONFIG.BEAM_MODE_QUALIFIER', 
                    'uiField': 'Beam Mode Qualifier', 
                    'rapiField': 'Beam Mode Qualifier'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.SBEAM', 
                    'uiField': 'Beam Mode Type', 
                    'rapiField': 'Beam Mode Type'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.DOWNLINK_SEGMENT_ID', 
                    'uiField': 'Downlink segment ID', 
                    'rapiField': 'Downlink segment ID'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'LUTApplied', 
                    'uiField': 'LUT Applied', 
                    'rapiField': 'LUT Applied'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'CATALOG_IMAGE.OPEN_DATA', 
                    'uiField': 'Open Data', 
                    'rapiField': 'Open Data'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.POLARIZATION', 
                    'uiField': 'Polarization', 
                    'rapiField': 'Polarization'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'PRODUCT_FORMAT.FORMAT_NAME_E', 
                    'uiField': 'Product Format', 
                    'rapiField': 'Product Format'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'ARCHIVE_IMAGE.PRODUCT_TYPE', 
                    'uiField': 'Product Type', 
                    'rapiField': 'Product Type'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.ORBIT_REL', 
                    'uiField': 'Relative Orbit', 
                    'rapiField': 'Relative Orbit'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.WITHIN_ORBIT_TUBE', 
                    'uiField': 'Within Orbital Tube', 
                    'rapiField': 'Within Orbital Tube'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'ARCHIVE_IMAGE.ORDER_KEY', 
                    'uiField': 'Order Key', 
                    'rapiField': 'Order Key'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'CATALOG_IMAGE.SEQUENCE_ID', 
                    'uiField': 'Sequence Id', 
                    'rapiField': 'Sequence Id'}, 
                 {'collectionId': 'RCMImageProducts', 
                    'fieldId': 'RCM.SPECIAL_HANDLING_REQUIRED', 
                    'uiField': 'Special Handling Required', 
                    'rapiField': 'Special Handling Required'}], 
            'RCMScienceData': [{'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.SBEAM', 
                    'uiField': 'Beam Mode', 
                    'rapiField': 'Beam Mode Type'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.BEAM_MNEMONIC', 
                    'uiField': 'Beam Mnemonic', 
                    'rapiField': 'Beam Mnemonic'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'CUF_RCM.TR_POL', 
                    'uiField': 'Transmit Polarization', 
                    'rapiField': 'Transmit Polarization'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'CUF_RCM.REC_POL', 
                    'uiField': 'Receive Polarization', 
                    'rapiField': 'Receive Polarization'}, 
                 {'collectionId': 'RCMScienceData', 
                    'fieldId': 'RCM.DOWNLINK_SEGMENT_ID', 
                    'uiField': 'Downlink Segment ID', 
                    'rapiField': 'Downlink Segment ID'}], 
            'SPOT': [{'collectionId': 'SPOT', 
                    'fieldId': 'SPOT.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover (Not all vendors supply cloud cover data)', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'SPOT', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'SPOT', 
                    'fieldId': 'SPOT.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}], 
            'TerraSarX': [{'collectionId': 'TerraSarX', 
                    'fieldId': 'TSX1.ORBIT_DIRECTION', 
                    'uiField': 'Orbit Direction', 
                    'rapiField': 'Orbit Direction'}, 
                 {'collectionId': 'TerraSarX', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'TerraSarX', 
                    'fieldId': 'INCIDENCE_ANGLE', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Incidence Angle'}], 
            'VASP': [{'collectionId': 'VASP', 
                    'fieldId': 'CATALOG_SERIES.CEOID', 
                    'uiField': 'Value-added Satellite Product Options', 
                    'rapiField': 'Sequence Id'}], 
            'WorldView-1': [{'collectionId': 'WorldView-1', 
                    'fieldId': 'WV1.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'WorldView-1', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'WorldView-1', 
                    'fieldId': 'WV1.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'WorldView-1', 
                    'fieldId': 'WV1.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'WorldView-2': [{'collectionId': 'WorldView-2', 
                    'fieldId': 'WV2.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'WorldView-2', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId': 'WorldView-2', 
                    'fieldId': 'WV2.SENS_INC', 
                    'uiField': 'Incidence Angle (Decimal Degrees)', 
                    'rapiField': 'Sensor Incidence Angle'}, 
                 {'collectionId': 'WorldView-2', 
                    'fieldId': 'WV2.SBEAM', 
                    'uiField': 'Sensor Mode', 
                    'rapiField': 'Sensor Mode'}], 
            'WorldView-3': [{'collectionId': 'WorldView-3', 
                    'fieldId': 'WV3.CLOUD_PERCENT', 
                    'uiField': 'Maximum Cloud Cover', 
                    'rapiField': 'Cloud Cover'}, 
                 {'collectionId': 'WorldView-3', 
                    'fieldId': 'SENSOR_BEAM.SPATIAL_RESOLUTION', 
                    'uiField': 'Pixel Spacing (Metres)', 
                    'rapiField': 'Spatial Resolution'}, 
                 {'collectionId', 'WorldView-3', 
                    'fieldId', 'WV3.SENS_INC', 
                    'uiField', 'Incidence Angle (Decimal Degrees)', 
                    'rapiField', 'Sensor Incidence Angle'}, 
                 {'collectionId', 'WorldView-3', 
                    'fieldId', 'WV3.SBEAM', 
                    'uiField', 'Sensor Mode', 
                    'rapiField', 'Sensor Mode'}]}
        
        # self.field_map = {}
        # csv_fn = '%s/data/field_mapping.csv' % \
                # os.path.dirname(os.path.realpath(__file__))
        
        # #print("csv_fn: %s" % csv_fn)
        # with open(csv_fn) as csvfile:
            # reader = csv.DictReader(csvfile)
            # for row in reader:
                # coll_id = row['collectionId']
                # coll_lst = []
                # if coll_id in self.field_map.keys():
                    # coll_lst = self.field_map[coll_id]
                # coll_lst.append(row)
                # self.field_map[coll_id] = coll_lst
                
    def _order_results(self, results, keys):
        out_results = []
        for res in results:
            remain_keys = [k for k in res.keys() if k not in keys]
            
            keys += remain_keys
            
            new_res = {k: res[k] for k in keys}
            
            out_results.append(new_res)
            
        return out_results
    
    def _parse_range(self, field, start, end):
        return '(%s>=%s AND %s<=%s)' % (field, start, field, end)
        
    def _parse_query(self, filters=None, feats=None, dates=None):
        
        query_lst = []
        
        if not self.rapi_collections:
            self.get_collections()
            
        if self.rapi_collections is None: return None
        
        # srch_fields = self.rapi_collections[self.collection]['fields']\
                        # ['search']
        
        # print("Search Fields: %s" % srch_fields)
        
        # print("Search Field Keys: %s" % srch_fields.keys())
        
        # print("dates: %s" % dates)
        
        if dates is not None and not str(dates).strip() == '':
            self.dates = dates
        # print("self.dates: %s" % self.dates)
        
        if self.dates is not None:
            
            # field_id = srch_fields['Acquisition Start Date']['id']
            field_id = self._get_fieldId('Acquisition Start Date')
            
            if field_id is None:
                field_id = self._get_fieldId('Start Date')
            
            #parsed_dates = self._get_dates()
            
            date_queries = []
            for rng in self.dates:
                if 'start' not in rng.keys():
                    break
                # print("rng: %s" % rng)
                start = self._convert_date(rng.get('start'), \
                                "%Y%m%d_%H%M%S", \
                                out_form="%Y-%m-%dT%H:%M:%SZ")
                end = self._convert_date(rng.get('end'), "%Y%m%d_%H%M%S", \
                                out_form="%Y-%m-%dT%H:%M:%SZ")
                                
                if start is None or end is None:
                    continue
                                
                # print("start: %s" % start)
                # print("end: %s" % end)
                
                date_queries.append("%s>='%s' AND %s<='%s'" % \
                    (field_id, start, field_id, end))
            
            if len(date_queries) > 0:
                query_lst.append("(%s)" % ' OR '.join(date_queries))
            
            # print("query_lst: %s" % query_lst)
            
            #answer = input("Press enter...")
            #field_id = srch_fields[
        
        if feats is None: feats = self.feats
        
        if feats is not None:
            
            geom_lst = []
            
            for idx, f in enumerate(feats):
                op = f[0].upper()
                src = f[1]
            
                # self.aoi = self.geo.set_aoi(aoi)
                
                self.geoms = self.geo.add_geom(src)
            
                # print("aoi type: %s" % type(self.aoi))
                if self.geoms is None or isinstance(self.geoms, SyntaxError):
                    # print("\n%sWARNING: AOI is not a valid entry. " \
                            # "Ignoring AOI.\n" % self._header)
                    # msg = "Feature #%s either cannot be opened or the AOI " \
                    #        "is not a valid entry. Ignoring AOI."
                    msg = "Geometry feature #%s could not be determined. " \
                            "Excluding it from search." % str(idx + 1)
                    self._log_msg(msg, 'warning')
                else:                
                    # print("AOI: %s" % self.aoi)
                    
                    # field_id = srch_fields['Footprint']['id']
                    field_id = self._get_fieldId('Footprint')
                    # print("field_id: %s" % field_id) 

                    self.geoms = [self.geoms] \
                        if not isinstance(self.geoms, list) else self.geoms
                    
                    for g in self.geoms:
                        geom_lst.append('%s %s %s' % (field_id, op, g))
            
            if len(geom_lst) > 0:
                query_lst.append("(%s)" % ' OR '.join(geom_lst))
                
        if filters is not None:
            # print("query: %s" % query)
            for field, values in filters.items():
            
                # Convert field name to proper field
                # coll_fields = self.rapi_collections[self.collection]['fields']
                # print("coll_fields: %s" % coll_fields)
                
                # print("field: %s" % field)
                # print("values: %s" % str(values))
                
                # if not field in self.get_availableFields()['search']:
                    # coll_fields = self.field_map[self.collection]
                    # ui_fields = [f['uiField'] for f in coll_fields]
                    # # print("coll_fields: %s" % coll_fields)
                    # # print([f['uiField'] for f in coll_fields])
                    
                    # for f in coll_fields:
                        # if f['uiField'].find(field) > -1 or \
                            # f['uiField'].upper().replace(' ', '_')\
                                # .find(field) > -1 or \
                            # f['fieldId'].find(field) > -1:
                            # field_id = f['fieldId']
                            # break
                    
                    # if field_id is None:
                        # msg = "No available field named '%s'." % field
                        # # print("\n%sWARNING: %s" % (self._header, msg))
                        # self._log_msg(msg, 'warning')
                        # continue
                # else:
                    # # field_id = srch_fields[field]['id']
                    # field_id = self._get_fieldId(field)
                    
                field_id = self._get_fieldId(field)
                
                # print("field_id: %s" % field_id)
                
                if field_id is None:
                    msg = "No available field named '%s'." % field
                    # print("\n%sWARNING: %s" % (self._header, msg))
                    self._log_msg(msg, 'warning')
                    continue
                    
                d_type = self._get_fieldType(self.collection, field_id)
                
                op = values[0]
                val = values[1]
                
                if not any(c in op for c in '=><'):
                    op = ' %s ' % op
                
                # if field == 'Incidence Angle':
                    
                    # fields = [srch_fields['Incidence Angle (Low)']['id'], \
                                # srch_fields['Incidence Angle (High)']['id']]
                    # print("fields: %s" % fields)
                    # if isinstance(val, list) or isinstance(val, tuple):
                        # for v in val:
                            # query_lst.append(self._parse_angle(fields, op, v))
                        # continue
                    # else:
                        # val_query = self._parse_angle(fields, op, val)
                        
                if field == 'Incidence Angle' or field == 'Scale' or \
                    field == 'Spacial Resolution' or field == 'Absolute Orbit':
                    #(SENSOR_BEAM_CONFIG.INCIDENCE_LOW >= 10.0 AND SENSOR_BEAM_CONFIG.INCIDENCE_LOW < 20.0) OR 
                    # (SENSOR_BEAM_CONFIG.INCIDENCE_HIGH >= 10.0 AND SENSOR_BEAM_CONFIG.INCIDENCE_HIGH < 20.0)
                    if isinstance(val, list) or isinstance(val, tuple):
                        for v in val:
                            if v.find('-') > -1:
                                start, end = v.split('-')
                                val_query = self._parse_range(field_id, start, end)
                            else:
                                val_query = "%s%s%s" % (field_id, op, v)
                            query_lst.append(val_query)
                        continue
                    else:
                        if str(val).find('-') > -1:
                            start, end = str(val).split('-')
                            val_query = self._parse_range(field_id, start, end)
                        else:
                            val_query = "%s%s%s" % (field_id, op, val)
                else:
                    if isinstance(val, list) or isinstance(val, tuple):
                        val_query = self._build_or(field_id, op, val, d_type)
                    else:
                        if d_type == 'String':
                            val_query = "%s%s'%s'" % (field_id, op, val)
                        else:
                            val_query = "%s%s%s" % (field_id, op, val)
                
                # print("val_query: %s" % val_query)
                # print("val_query type: %s" % type(val_query))
                query_lst.append(val_query)
        
        if len(query_lst) > 1:
            query_lst = ['(%s)' % q if q.find(' OR ') > -1 else q \
                        for q in query_lst]
            
        full_query = ' AND '.join(query_lst)
        
        return full_query
            
    def _submit_search(self):
        """
        Submit a search query to the desired EODMS collection

        Since there may be instances where the default maxResults is greater 
        than 150, this method should recursively call itself until the 
        correct number of results is retrieved.
        
        (Adapted from: eodms-api-client (https://pypi.org/project/eodms-api-client/)
            developed by Mike Brady)
        
        :rtype:  json
        :return: The search-query response JSON from the EODMS REST API          
        """
        
        # old_maxResults = int(re.search(r'&maxResults=([\d*]+)', \
                        # self._search_url).group(1))
                        
        # print("old_maxResults: %s" % old_maxResults)
        
        if self.max_results is not None:
            if len(self.results) >= self.max_results:
                self.results = self.results[:self.max_results]
                return self.results
        
        # Print status of search
        # print("self._search_url: %s" % self._search_url)
        start = len(self.results) + 1
        end = len(self.results) + self.limit_interval
        
        msg = "Querying records within %s to %s..." % (start, end)
        self._log_msg(msg)
        
        logger.debug("RAPI Query URL: %s" % self._search_url)
        r = self._submit(self._search_url, as_json=False)
        
        if r is None: return None
        
        # some GETs are returning 104 ECONNRESET
        # - possibly due to geometry vertex count (failed with 734 but 73 was fine)
        if isinstance(r, QueryError):
            msg = 'Retrying in 3 seconds...'
            self._log_msg(msg, 'warning')
            time.sleep(3)
            return self._submit_search()
            
        if r.ok:
            data = r.json()
            # the data['moreResults'] response is unreliable
            # thus, we submit another query if the number of results 
            # matches our query's maxResults value
            
            # If the number of results has reached the max_results specified
            #   by the user, return results up to max_results
            # if self.max_results is not None:
                # if len(data['results']) >= self.max_results:
                    # self.results += 
                    # return data['results'][:self.max_results]
                
            
            tot_results = int(data['totalResults'])
            # print("tot_results: %s" % tot_results)
            if tot_results == 0:
                return self.results
            elif tot_results < self.limit_interval:
                self.results += data['results']
                return self.results
            
            # if data['totalResults'] == old_maxResults:
                # logger.warning('Number of search results (%d) equals query ' \
                    # 'limit (%d). Increasing limit and trying again...' % \
                    # (data['totalResults'], old_maxResults))
                # new_maxResults = old_maxResults + self.limit_interval
                # self._search_url = self._search_url.replace(
                    # '&maxResults=%d' % old_maxResults,
                    # '&maxResults=%d' % new_maxResults
                # )
            self.results += data['results']
            first_result = len(self.results) + 1
            if self._search_url.find('&firstResult') > -1:
                old_firstResult = int(re.search(
                                        r'&firstResult=([\d*]+)', \
                                        self._search_url
                                    ).group(1))
                # print("old_firstResult: %s" % old_firstResult)
                # print("first_result: %s" % first_result)
                # print("self._search_url: %s" % self._search_url)
                self._search_url = self._search_url.replace(
                                    '&firstResult=%d' % old_firstResult, 
                                    '&firstResult=%d' % first_result
                                   )
                # print("self._search_url: %s" % self._search_url)
            else:
                self._search_url += '&firstResult=%s' % first_result
            return self._submit_search()
            # else:
                # return data['results']
            # return data['results']
            
    def _submit(self, query_url, timeout=None, 
                record_name=None, quiet=True, as_json=True):
        """
        Send a query to the RAPI.
        
        :type  query_url:   str
        :param query_url:   The query URL.
        :type  timeout:     float
        :param timeout:     The length of the timeout in seconds.
        :type  record_name: str
        :param record_name: A string used to supply information for the record 
                            in a print statement.
        
        :rtype  request.Response
        :return The response returned from the RAPI.
        """
        
        # logger = logging.getLogger('eodms')
        
        # logger.debug("_submit: RAPI Query URL: %s" % query_url)
        
        if timeout is None:
            timeout = self.timeout_query
        
        verify = True
        # if query_url.find('www-pre-prod') > -1:
            # verify = False
            
        logger.debug("RAPI Query URL: %s" % query_url)
        
        res = None
        attempt = 1
        err = None
        # Get the entry records from the RAPI using the downlink segment ID
        while res is None and attempt <= self.attempts:
            # Continue to attempt if timeout occurs
            try:
                if record_name is None:
                    msg = "Sending request to the RAPI (attempt %s)..." \
                            % attempt
                    if not quiet and attempt > 1:
                        logger.debug("\n%s%s" % (self._header, msg))
                else:
                    msg = "Sending request to the RAPI for '%s' " \
                                "(attempt %s)..." % (record_name, attempt)
                    if not quiet and attempt > 1:
                        logger.debug("\n%s%s" % (self._header, msg))
                #start_time = datetime.datetime.now()
                if self._session is None:
                    res = requests.get(query_url, timeout=timeout, verify=verify)
                else:
                    res = self._session.get(query_url, timeout=timeout, verify=verify)
                res.raise_for_status()
                #end_time = datetime.datetime.now()
                #logger.info("RAPI request took %s to complete." % str(end_time - start_time))
            except requests.exceptions.HTTPError as errh:
                msg = "HTTP Error: %s" % errh
                
                if msg.find('Unauthorized') > -1 or \
                    msg.find('404 Client Error: Not Found for url') > -1:
                    err = msg
                    attempt = 4
                
                if attempt < self.attempts:
                    msg = "%s; attempting to connect again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
            except (requests.exceptions.Timeout, 
                    requests.exceptions.ReadTimeout) as errt:
                msg = "Timeout Error: %s" % errt
                if attempt < self.attempts:
                    msg = "%s; increasing timeout by a minute and trying " \
                            "again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                    timeout += 60.0
                    self.timeout_query = timeout
                else:
                    err = msg
                attempt += 1
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.RequestException) as req_err:
                # print("req_err type: %s" % type(req_err))
                msg = "%s Error: %s" % (req_err.__class__.__name__, req_err)
                if attempt < self.attempts:
                    msg = "%s; attempting to connect again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
            # except requests.exceptions.RequestException as err:
                # msg = "Exception: %s" % err
                # if attempt < self.attempts:
                    # msg = "WARNING: %s; attempting to connect again..." % msg
                    # print('\n%s' % msg)
                    # logger.warning(msg)
                    # res = None
                # else:
                    # err = msg
                # attempt += 1
            except KeyboardInterrupt as err:
                msg = "Process ended by user."
                self._log_msg(msg, out_indent='\n')
                return None
            except:
                msg = "Unexpected error: %s" % traceback.format_exc()
                if attempt < self.attempts:
                    msg = "%s; attempting to connect again..." % msg
                    self._log_msg(msg, 'warning')
                    res = None
                else:
                    err = msg
                attempt += 1
                
        if err is not None:
            query_err = QueryError(err)
            
            if self._check_auth(query_err): return None
            
            return query_err
                
        # If no results from RAPI, return None
        if res is None: return None
        
        # Check for exceptions that weren't already caught
        except_err = self._get_exception(res)
        
        if isinstance(except_err, QueryError):
            
            if self._check_auth(except_err): return None
                
            self._log_msg(msg, 'warning')
            return except_err
        
        if as_json:
            return res.json()
        else:
            return res
            
    def _to_camelCase(self, in_str):
        """
        Converts a string to lower camel case.
        
        Args:
            in_str (str): The input string to convert.
            
        Returns:
            str: The input string convert to lower camel case.
        """
        
        in_str = re.sub(r"\([^()]*\)", "", in_str)
    
        if in_str.find(' ') > -1:
            words = in_str.split(' ')
        elif in_str.find('_') > -1:
            words = in_str.split('_')
        else:
            return in_str[0].lower() + in_str[1:]
            
        first_word = words[0].lower()
        other_words = ''.join(w.title() for w in words[1:])
        
        return '%s%s' % (first_word, other_words)
        
    def _update_conv(self):
        
        if self.res_mdata is not None:
            for m in self.res_mdata:
                for k, v in m.items():
                    new_k = self._get_conv(k)
                    m[new_k] = m.pop(k)
            
    def _get_fullCollId(self, coll, unsupported=False):
        """
        Gets the full collection ID using the input collection ID which can be a 
            substring of the collection ID.
        
        Args:
            coll_id (str):      The collection ID to check.
            unsupported (bool): Determines whether to check in the supported or 
                                unsupported collection lists.
        """
        
        # if unsupported:
            # print("self.unsupport_collections: %s" % self.unsupport_collections)
            # for k in self.unsupport_collections.keys():
                # if k.find(coll_id) > -1:
                    # return k
        
        # for k in self.rapi_collections.keys():
            # if k.find(coll_id) > -1:
                # return k
                
        if not self.rapi_collections:
            self.get_collections()
            
        if self.rapi_collections is None: return None
                
        for k, v in self.rapi_collections.items():
            if coll.lower() == k.lower():
                return k
            elif coll.lower() in v['aliases']:
                return k
        
    def set_queryTimeout(self, timeout):
        """
        Sets the timeout limit for a query to the RAPI.
        
        :param timeout: The value of the timeout in seconds.
        :type  timeout: float
        
        """
        self.timeout_query = float(timeout)
        
    def set_orderTimeout(self, timeout):
        """
        Sets the timeout limit for an order to the RAPI.
        
        :param timeout: The value of the timeout in seconds.
        :type  timeout: float
            
        """
        self.timeout_order = float(timeout)
        
    def set_attempts(self, number):
        """
        Sets number of attempts to be made to the RAPI before the script 
        ends.
        
        :param number: The value for the number of attempts.
        :type  number: int
        
        """
        self.attempts = int(number)
        
    def set_fieldConvention(self, convention):
        """
        Sets the naming convention of the output fields.
        
        :param convention: The type of naming convention for the fields.
            
            - ``words``: The label with spaces and words will be returned.
            - ``camel`` (default): The format will be lower camel case like 'camelCase'.
            - ``upper``: The format will be all uppercase with underscore for spaces.
            
        :type  convention: str

        """
        
        self.name_conv = convention
        
        self._update_conv()
        
    def download(self, items, dest, wait=10.0):
        """
        Downloads a list of order items from the EODMS RAPI.
        
        :param items: A list of order items returned from the RAPI.
            
            Example:
                
                ``{'items': [{'recordId': '8023427', 'status': 'SUBMITTED', 'collectionId': 'RCMImageProducts', 'itemId': '346204', 'orderId': '50975'}, ...]}``
            or
                ``[{'recordId': '8023427', 'status': 'SUBMITTED', 'collectionId': 'RCMImageProducts', 'itemId': '346204', 'orderId': '50975'}, ...]``
                
        :type  items: list or dict
        :param dest: The local download folder location.
        :type  dest: str
        :param wait: Sets the time to wait before checking the status of all orders.
        :type  wait: float or int
        
        """
        
        # print("\n%sDownloading image results." % self._header)
        
        msg = "Downloading images..."
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # for r in results['items']:
            # self.get_order(r['itemId'])
            
        # print("items: %s" % items)
        
        if items is None:
            msg = "No images to download."
            self._log_msg(msg)
            return []
            
        if isinstance(items, dict):
            if 'items' in items.keys():
                items = items['items']
        # elif isinstance(items, list):
        #     items = [{'itemId': i} for i in items]
                
        if len(items) == 0:
            msg = "No images to download."
            self._log_msg(msg)
            return []
            
        # print("Number of items: %s" % len(items))
        
        complete_items = []
        while len(items) > len(complete_items):
            time.sleep(wait)
            
            # for idx, i in enumerate(items):
                # print()
                # print("download - i.%s:" % idx)
                # print("    recordId: %s" % i.get('recordId'))
                # print("    Contains 'dateRapiOrdered': %s" \
                    # % str('dateRapiOrdered' in i.keys()))
                # print("    dateRapiOrdered: %s" % i.get('dateRapiOrdered'))
            
            start, end = self._get_dateRange(items)
            
            # print("start: %s" % start)
            # print("end: %s" % end)
            
            orders = self.get_orders(dtstart=start, dtend=end)
            
            if len(orders) == 0:
                msg = "No orders could be found."
                self._log_msg(msg)
                return []
            
            new_count = len(complete_items)
            
            for itm in items:
                item_id = itm['itemId']
                cur_item = self._get_itemFromOrders(item_id, orders)
                status = cur_item['status']
                record_id = cur_item['recordId']
                
                # Check record is already complete
                if self._check_complete(complete_items, record_id):
                    continue
                
                if status in self.failed_status:
                    if status == 'FAILED':
                        # If the order has failed, inform user
                        status_mess = cur_item.get('statusMessage')
                        msg = "\n  The following Order Item has failed:"
                        if status_mess is None:
                            msg += "\n    Order Item Id: %s\n" \
                                    "    Record Id: %s" % \
                                    "    Collection: %s\n" \
                                    (cur_item['itemId'], \
                                    cur_item['recordId'], \
                                    cur_item['collectionId'])
                        else:
                            msg += "\n    Order Item Id: %s\n" \
                                    "    Record Id: %s\n" \
                                    "    Collection: %s\n" \
                                    "    Reason for Failure: %s" % \
                                    (cur_item['itemId'], cur_item['recordId'], \
                                    cur_item['collectionId'], \
                                    cur_item['statusMessage'])
                    else:
                        # If the order was unsuccessful with another status, 
                        #   inform user
                        msg = "\n  The following Order Item has status " \
                                "'%s' and will not be downloaded:" % status
                        msg += "\n    Order Item Id: %s\n" \
                                "    Record Id: %s\n" \
                                "    Collection: %s\n" % \
                                (cur_item['itemId'], \
                                cur_item['recordId'], \
                                cur_item['collectionId'])
                    
                    self._log_msg(msg)
                    
                    cur_item['downloaded'] = 'False'
                    
                    complete_items.append(cur_item)
                    
                elif status == 'AVAILABLE_FOR_DOWNLOAD':
                    cur_item['downloaded'] = 'True'
                    
                    dests = cur_item['destinations']
                    manifest_key = list(cur_item['manifest'].keys()).pop()
                    fsize = int(cur_item['manifest'][manifest_key])
                    
                    download_paths = []
                    for d in dests:
                        
                        # Get the string value of the destination
                        str_val = d['stringValue']
                        str_val = str_val.replace('</br>', '')
                        
                        # Parse the HTML text of the destination string
                        root = ElementTree.fromstring(str_val)
                        url = root.text
                        fn = os.path.basename(url)
                        
                        # Download the image
                        msg = "Downloading image with " \
                                "Record Id %s (%s)." % (record_id, \
                                os.path.basename(url))
                        self._log_msg(msg)
                        
                        # # Save the image contents to the 'downloads' folder
                        out_fn = os.path.join(dest, fn)
                        full_path = os.path.realpath(out_fn)
                        
                        if not os.path.exists(dest):
                            os.mkdir(dest)
                        
                        self._download_image(url, out_fn, fsize)
                        print('')
                        
                        # Record the URL and downloaded file to a dictionary
                        dest_info = {}
                        dest_info['url'] = url
                        dest_info['local_destination'] = full_path
                        download_paths.append(dest_info)
                        
                    cur_item['downloadPaths'] = download_paths
                    
                    complete_items.append(cur_item)
            
            if new_count == 0 and len(complete_items) == 0:
                msg = "No items are ready for download yet."
                self._log_msg(msg)
            elif new_count == len(complete_items):
                msg = "No new items are ready for download yet."
                self._log_msg(msg)
        
        return complete_items
        
    def get_availableFields(self, collection=None, name_type='all'):
        """
        Gets a dictionary of available fields for a collection from the RAPI.
        
        :param collection: The Collection ID.
        :type  collection: str
        
        :return: A dictionary containing the available fields for the given 
                collection.
        :rtype:  dict
        
        """
        
        if collection is None:
            if self.collection is None:
                self._log_msg('No collection can be determined.', 'warning')
                return None
            collection = self.collection
        
        query_url = '%s/collections/%s' % (self.rapi_root, collection)
        
        coll_res = self._submit(query_url, timeout=20.0)
        
        if coll_res is None: return None
        
        # If an error occurred
        if isinstance(coll_res, QueryError):
            self._log_msg(coll_res._get_msgs(True), 'warning')
            return None
        
        # Get a list of the searchFields
        fields = {}
        if name_type == 'title' or name_type == 'id':
            
            srch_fields = []
            for r in coll_res['searchFields']:
                srch_fields.append(r[name_type])
        
            fields['search'] = srch_fields
        
            res_fields = []
            for r in coll_res['resultFields']:
                res_fields.append(r[name_type])
                
            fields['results'] = res_fields
                
        else:
            srch_fields = {}
            for r in coll_res['searchFields']:
                srch_fields[r['title']] = {'id': r['id'], \
                                    'datatype': r['datatype'], \
                                    'choices': r.get('choices')}
        
            fields['search'] = srch_fields
        
            res_fields = {}
            for r in coll_res['resultFields']:
                    res_fields[r['title']] = {'id': r['id'], \
                                    'datatype': r['datatype']}
            
            fields['results'] = res_fields
            
        return fields
        
    def get_fieldChoices(self, collection, field=None):
        """
        Gets the avaiable choices for a specified field. If no choices exist,
            then the data type is returned.
            
        :param collection: The collection containing the field.
        :type  collection: str
        :param field: The field name or field ID.
        :type  field: str
        
        :return: Either a list of choices or a string containing the 
                data type.
        :rtype: list or str
        """
        
        fields = self.get_availableFields(collection)
        
        all_fields = {}
        for f, v in fields['search'].items():
            choices = []
            if field is None:
                field_choices = v.get('choices')
                if field_choices is not None:
                    for c in field_choices:
                        value = c['value']
                        if not value == '':
                            choices.append(value)
                    all_fields[f] = choices
                else:
                    all_fields[f] = {'data_type': v.get('datatype')}
            else:
                if f == field or v['id'] == field:
                    field_choices = v.get('choices')
                    if field_choices is not None:
                        for c in field_choices:
                            value = c['value']
                            if not value == '':
                                choices.append(value)
                        return choices
                    else:
                        return 'Data type: %s' % v.get('datatype')
        
        return all_fields
        
    def get_collections(self, as_list=False, titles=False, redo=False):
        """
        Gets a list of available collections for the current user.
        
        :param as_list: Determines the type of return. If False, a dictionary
                        will be returned. If True, only a list of collection
                        IDs will be returned.
        :type  as_list: bool
        
        :return: Either a dictionary of collections or a list of collection IDs 
                depending on the value of as_list.
        :rtype:  dict
        
        """
        
        # print("\nGetting a list of available collections for the script, please wait...")
        
        # logger = logging.getLogger('eodms')
        
        if self.rapi_collections and not redo:
            if as_list:
                if titles:
                    collections = [i['title'] for i in \
                                self.rapi_collections.values()]
                else:
                    collections = list(self.rapi_collections.keys())
                return collections
            return self.rapi_collections
        
        # print("\n%sGetting Collection information, please wait..." % \
        #         self._header)
        
        # List of collections that are either commercial products or not available 
        #   to the general public
        # ignore_collNames = ['RCMScienceData', 'Radarsat2RawProducts', 
                            # 'Radarsat1RawProducts', 'COSMO-SkyMed1', '162', 
                            # '165', '164']
        
        # Create the query to get available collections for the current user
        query_url = "%s/collections" % self.rapi_root
        
        msg = "Getting Collection information, please wait..."
        self._log_msg(msg)
        logger.debug("RAPI URL: %s" % query_url)
        
        # Send the query URL
        coll_res = self._submit(query_url, timeout=20.0)
        
        # print("coll_res: %s" % coll_res)
        
        if coll_res is None: return None
        
        # If an error occurred
        if isinstance(coll_res, QueryError):
            msg = "Could not get a list of collections due to '%s'." % \
                coll_res._get_msgs(True)
            self._log_msg(msg, 'error')
            return None
        
        # If a list is returned from the query, return it
        # if isinstance(coll_res, list):
            # return coll_res
        
        # Convert query to JSON
        # coll_json = coll_res.json()
        
        # Create the collections dictionary
        for coll in coll_res:
            for child in coll['children']:                
                for c in child['children']:
                    coll_id = c['collectionId']
                    # Add aliases for specific collections allowing easier access for users
                    aliases = []
                    if coll_id == 'RCMImageProducts':
                        aliases = ['rcm']
                    elif coll_id == 'Radarsat1':
                        aliases = ['r1', 'rs1', 'radarsat', 'radarsat-1']
                    elif coll_id == 'Radarsat2':
                        aliases = ['r2', 'rs2', 'radarsat-2']
                    elif coll_id == 'PlanetScope':
                        aliases = ['planet']
                    fields = self.get_availableFields(coll_id, 'all')
                    if fields is None: continue
                    self.rapi_collections[c['collectionId']] = {
                        'title': c['title'], 
                        'aliases': aliases, 
                        'fields': fields}
        
        # print("self.rapi_collections: %s" % self.rapi_collections)
        # for coll, info in self.rapi_collections.items():
            # print("\n%s:" % coll)
            # for k, v in info.items():
                # print("%s: %s" % (k, v))
        # answer = input("Press enter...")
        
        # If as_list is True, convert dictionary to list of collection IDs
        if as_list:
            if titles:
                collections = [i['title'] for i in \
                            self.rapi_collections.values()]
            else:
                collections = list(self.rapi_collections.keys())
            return collections
        
        return self.rapi_collections
        
    # def get_collIdByName(self, in_title, unsupported=False):
        # """
        # Gets the Collection ID based on the tile/name of the collection.
        
        # @type  in_title:    str
        # @param in_title:    The title/name of the collection.
                            # (ex: 'RCM Image Products' for ID 'RCMImageProducts')
        # @type  unsupported: boolean
        # @param unsupported: Determines whether to check in the unsupported list 
                            # or not.
        # """
        
        # if isinstance(in_title, list):
            # in_title = in_title[0]
        
        # if unsupported:
            # for k, v in self.unsupport_collections.items():
                # if v.find(in_title) > -1 or in_title.find(v) > -1 \
                    # or in_title.find(k) > -1 or k.find(in_title) > -1:
                    # return k
        
        # for k, v in self.rapi_collections.items():
            # if v['title'].find(in_title) > -1:
                # return k
                
        # return self.get_fullCollId(in_title)
                
    # def get_collectionName(self, in_id):
        # """
        # Gets the collection name for a specified collection ID.
        
        # @type  in_id: str
        # @param in_id: The collection ID.
        # """
        
        # return self.rapi_collections[in_id]
                
    def get_orderItem(self, itemId):
        """
        Submits a query to the EODMS RAPI to get a specific order item.
        
        :param itemId: The Order Item ID of the image to retrieve from the RAPI.
        :type  itemId: str or int
        
        :return: A dictionary containing the JSON format of the results from the RAPI. 
        :rtype:  dict
        
        """
        
        query = "%s/order?itemId=%s" % (self.rapi_root, itemId)
        log_msg = "Getting order item %s (RAPI query): %s" % (itemId, query)
        msg = "Getting order item %s..." % itemId
        
        messages = (log_msg, msg)
        self._log_msg(messages, log_indent='\n\n\t', out_indent='\n')
        
        res = self._submit(query, timeout=self.timeout_order)
        
        if res is None: return None
                
        return res
        
    def get_order(self, orderId):
        """
        Gets an specified order from the EODMS RAPI.
        
        :param orderId: The Order ID of the specific order.
        :type  orderId: str or int
        
        :return: A JSON dictionary of the specific order.
        :rtype:  dict
        
        """
        
        orders = self.get_orders()
        
        order = []
        for item in order:
            if item['orderId'] == orderId:
                order.append(item)
                
        return order
                
    def get_orders(self, dtstart=None, dtend=None, maxOrders=10000, 
                    outFormat='json'):
        """
        Sends a query to retrieve orders from the RAPI.
        
        :param dtstart: The start date for the date range of the query.
        :type  dtstart: datetime.datetime
        :param dtend: The end date for the date range of the query.
        :type  dtend: datetime.datetime
        :param maxOrders: The maximum number of orders to retrieve.
        :type  maxOrders: int
        :param outFormat: The format of the results.
        :type  outFormat: str
        
        :return: A JSON dictionary of the query results containing the orders.
        :rtype:  dict
        
        """
        
        # print("%sGetting list of your current orders..." % self._header)
        msg = "Getting list of current orders..."
        self._log_msg(msg)
        
        tm_frm = '%Y-%m-%dT%H:%M:%SZ'
        # end = datetime.datetime.now()
        params = {}
        if dtstart is not None:
            params['dtstart'] = dtstart.strftime(tm_frm)
            params['dtend'] = dtend.strftime(tm_frm)
        params['maxOrders'] = maxOrders
        param_str = urlencode(params)
        
        query_url = "%s/order?%s" % (self.rapi_root, param_str)
                    
        # logger.info("Searching for images (RAPI query)")
        logger.debug("RAPI URL:\n\n%s\n" % query_url)
        # Send the query to the RAPI
        res = self._submit(query_url, self.timeout_query, quiet=False)
        
        if res is None or isinstance(res, QueryError):
            if isinstance(res, QueryError):
                msg = "Order submission was unsuccessful due to: %s." % \
                        res._get_msgs(True)
            else:
                msg = "Order submission was unsuccessful."
            self._log_msg(msg, 'warning')
            # print("%s%s" % (self._header, msg))
            return None
            
        if 'items' in res.keys():
            return res['items']
        else:
            return res
            
    def get_ordersByRecords(self, records):
        """
        Gets a list of orders from the RAPI based on a list of records.
        
        :param records: A list of records used to get the list of orders.
        :type  records: list
            
        :return: A list of results from the RAPI.
        :rtype:  list
        """
        
        if records is None or len(records) == 0:
            msg = "Cannot get orders as no image items provided."
            self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
            return None
        
        start, end = self._get_dateRange(records)
        
        orders = self.get_orders(dtstart=start, dtend=end)
        
        # print("Number of records: %s" % len(records))
        
        # print("orders: %s" % orders)
        # answer = input("Press enter...")
        
        msg = "Getting a list of order items..."
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        found_orders = []
        unfound = []
        for idx, r in enumerate(records):
            
            # Go through each record
            rec_id = r['recordId']
            
            rec_orders = []
            
            for i in orders:
                # Go through each order item
                # i_date = datetime.datetime.strptime(i['dateSubmitted'], \
                        # '%Y-%m-%dT%H:%M:%SZ')
                
                if i['recordId'] == r['recordId']:
                    # Check in filt_orders for an older order item
                    #   and replace it
                    rec_orders.append(i)
                    # print("length of filt_orders: %s" % len(filt_orders))
                    # if len(filt_orders) == 0:
                        # filt_orders.append(i)
                    # else:
                        # filt_orders.append(i)
                        # for idx, o in enumerate(filt_orders):
                            # o_date = datetime.datetime.strptime(\
                                    # o['dateSubmitted'], \
                                    # '%Y-%m-%dT%H:%M:%SZ')
                            # print("i_date: %s" % i_date)
                            # print("o_date: %s" % o_date)
                            # print("o['recordId']: %s" % o['recordId'])
                            # print("i['recordId']: %s" % i['recordId'])
                            # if i_date > o_date and \
                                # o['recordId'] == i['recordId']:
                                # print("removing index: %s" % idx)
                                # del filt_orders[idx]
                                # #filt_orders.append(i)
                                # break
                                
            if len(rec_orders) == 0:
                unfound.append(rec_id)
                continue
        
            # Get the most recent order item with the given recordId
            order_item = max([r for r in rec_orders \
                        if r['recordId'] == rec_id], \
                        key=lambda x:x['dateSubmitted'])
                        
            found_orders.append(order_item)
        
        msg = "Found %s order items for the following records: %s" % \
                (len(found_orders), ', '.join([r['recordId'] \
                for r in found_orders]))
        self._log_msg(msg)
                    
        if len(unfound) > 0:
            msg = "No order items found for the following " \
                    "records: %s" % ', '.join(unfound)
            self._log_msg(msg)
        
        return found_orders
        
    def get_orderParameters(self, collection, recordId):
        """
        Gets the list of available Order parameters for a given image record.
        
        :param collection: The Collection ID for the query.
        :type  collection: str
        :param recordId: The Record ID for the image.
        :type  recordId: int or str
            
        :return: A JSON dictionary of the order parameters.
        :rtype:  dict
        
        """
        
        # Get the proper Collection ID for the RAPI
        collection = self._get_fullCollId(collection)
        
        msg = "\n\n\tGetting order parameters for image in " \
                "Collection %s with Record ID %s..." % \
                (collection, recordId)
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # Set the RAPI URL
        query_url = "%s/order/params/%s/%s" % (self.rapi_root, \
                    collection, recordId)
        
        # Send the JSON request to the RAPI
        try:
            # print("\n%sSubmitting orders..." % self._header)
            param_res = self._session.get(url=query_url)
            param_res.raise_for_status()
        except (requests.exceptions.HTTPError, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as req_err:
            msg = "%s Error: %s" % (req_err.__class__.__name__, req_err)
            self._log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt as err:
            msg = "Process ended by user."
            self._log_msg(msg, out_indent='\n')
            print()
            return None
        
        if not param_res.ok:
            err = self._get_exception(param_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self._log_msg(msg, 'warning')
                return msg
                
        msg = "Order removed successfully."
        # print("\n%s%s" % (self._header, msg))
        self._log_msg(msg)
        #logger.info("\n\n\t%s" % msg)
                
        return param_res.json()
        
    def search(self, collection, filters=None, features=None, dates=None, 
                resultFields=[], maxResults=None):
        """
        Sends a search to the RAPI to search for image results.
        
        :param collection: The Collection ID for the query.
        :type  collection: str
        :param filters: A dictionary of query filters and values in 
                    the following format:
                    
                ``{"|filter title|": ("|operator|", ["value1", "value2", ...]), ...}``
                
                Example: ``{"Beam Mnemonic": {'=': []}}``
        
        :type  filters: dict
        :param features: A list of tuples containing the operator and filenames or coordinates of features to use in the search. The features can be:
                
                - a filename (ESRI Shapefile, KML, GML or GeoJSON)
                - a WKT format string
                - the 'geometry' entry from a GeoJSON Feature
                - a list of coordinates (ex: ``[(x1, y1), (x2, y2), ...]``)
        :type  features: list
        :param dates: A list of date range dictionaries with keys ``start`` and ``end``.
                The values of the ``start`` and ``end`` can either be a string in format
                ``yyyymmdd_hhmmss`` or a datetime.datetime object.
                
                Example:
                    ``[{"start": "20201013_120000", "end": "20201013_150000"}]``
                    
        :type  dates: list
        :param resultFields: A name of a field to include in the query results.
        :type  resultFields: str
        :param maxResults: The maximum number of results to return from the query.
        :type  maxResults: str or int
        
        """
                
        # Query: {"Beam Mnemonic": {'=': []}}
        
        # Get the proper Collection ID for the RAPI
        self.collection = self._get_fullCollId(collection)
        
        if self.collection is None: return None
        
        # print("collection: %s" % self.collection)
        
        params = {'collection': self.collection}
        
        # print("query: %s" % query)
        
        if filters is not None or features is not None or dates is not None:
            params['query'] = self._parse_query(filters, features, dates)
            # full_query = query.get_query()
            # full_queryEnc = urllib.parse.quote(full_query)
            # params['query'] = full_query
            
        # print("full query: %s" % params['query'])
        # answer = input("Press enter...")
        
        if isinstance(resultFields, str):
            resultFields = [resultFields]
        
        result_field = []
        for field in resultFields:
            field_id = self._get_fieldId(field, field_type='results')
            if field_id is None:
                msg = "Field '%s' does not exist for collection '%s'. "\
                        "Excluding it from resultField entry." % (field, \
                        self.collection)
                self._log_msg(msg, 'warning')
            else:
                result_field.append(field_id)
        
        # Get the geometry field and add it to resultField
        footprint_id = self._get_fieldId('Footprint', collection)
        if footprint_id is not None:
            result_field.append(footprint_id)
                
        # Get the pixel spacing field and add it to resultField
        pixspace_id = self._get_fieldId('Spatial Resolution', \
                        collection)
        if pixspace_id is not None:
            result_field.append(pixspace_id)
        
        params['resultField'] = ','.join(result_field)
        
        params['maxResults'] = self.limit_interval
        if maxResults is None or maxResults == '':
            self.max_results = None
        else:
            self.max_results = int(maxResults)
            
            if self.max_results is not None:
                params['maxResults'] = self.max_results \
                        if int(self.max_results) < int(self.limit_interval) \
                        else self.limit_interval
        
        # print("params['maxResults']: %s" % params['maxResults'])
        
        params['format'] = "json"
        
        query_str = urlencode(params)
        self._search_url = "%s/search?%s" % (self.rapi_root, query_str)
        
        print()
        print(self._search_url)
        
        # Clear self.results
        self.results = []
        
        # print("\n%sSearching for images..." % self._header)
        #logger.info('\n')
        msg = "Searching for %s images on RAPI" % self.collection
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        logger.debug("RAPI URL:\n\n%s\n" % self._search_url)
        # Send the query to the RAPI
        #self.results = self._submit_search()
        self._submit_search()
        
        self.res_mdata = None
        
        msg = "Number of %s images returned from RAPI: %s" % \
                (self.collection, len(self.results))
        self._log_msg(msg)
        # print("%s%s" % (self._header, msg))
                
        # return self.results
        
    def get_results(self, form='raw'):
        """
        Gets the self.results in a given format
        
        :param form: The type of format to return.
            
            Available options:
            
            - ``raw``: Returns the JSON results straight from the RAPI.
            - ``full``: Returns a JSON with full metadata information.
            - ``geojson``: Returns a FeatureCollection of the results
                        (requires geojson package).
                            
        :type  form: str
        
        :return: A dictionary of the results from self.results variable.
        :rtype:  dict
        
        """
        
        if self.results is None or \
            isinstance(self.results, QueryError):
            msg = "No results exist. Please use search() to run a search " \
                    "on the RAPI."
            self._log_msg(msg, 'warning')
            # print("%s%s" % (self._header, msg))
            return None
            
        if len(self.results) == 0: return self.results
            
        self.res_format = form
            
        if self.res_format == 'full':
            if self.res_mdata is None:
                self.res_mdata = self._fetch_metadata()
            return self.res_mdata
        elif self.res_format == 'geojson':
            # self.name_conv = 'camel'
            if self.res_mdata is None:
                self.res_mdata = self._fetch_metadata()
            return self.geo.convert_toGeoJSON(self.res_mdata)
        else:
            return self.results
            
    def print_results(self, results=None):
        """
        Pretty prints the specified results.
        
        :param results: A JSON of results from the RAPI.
        :type  results: dict
        """
        
        if results is None:
            results = self.get_results('full')
            
        print(json.dumps(results, indent=4, ensure_ascii=False))
        
        # if results is None:
            # if self.res_mdata is not None:
                # results = self.res_mdata
            # else:
                # results = self.results
                
        # pp = pprint.PrettyPrinter(indent=4, sort_dicts=False)
        
        # if isinstance(results, dict):
            # results = results.get('items')
            
        # for r in results:
            # print()
            # pp.pprint(r)
        
    def order(self, results, priority="Medium", parameters=None, 
                destinations=[]):
        """
        Sends an order to EODMS using the RAPI.
        
        :param results: A list of JSON results from the RAPI.
                            
                The results list must contain a ``collectionId`` key and 
                a ``recordId`` key for each image.
                
        :type  results: list
        :param priority: Determines the priority of the order.
                
            If you'd like to specify a separate priority for each image,
            pass a list of dictionaries containing the ``recordId`` (matching 
            the IDs in results) and ``priority``, such as:
            
            ``[{"recordId": 7627902, "priority": "Low"}, ...]``
                    
            Priority options: "Low", "Medium", "High" or "Urgent"
        
        :type  priority: str or list
        :param parameter: Either a list of parameters or a list of record items.
                
                Use the get_orderParameters method to get a list of available parameters.
                
                **Parameter list**: ``[{"|internalName|": "|value|"}, ...]``
                
                    Example: ``[{"packagingFormat": "TARGZ"}, {"NOTIFICATION_EMAIL_ADDRESS": "kevin.ballantyne@canada.ca"}, ...]``
                
                **Parameters for each record**: ``[{"recordId": |recordId|, "parameters": [{"|internalName|": "|value|"}, ...]}]``
                  
                    Example: ``[{"recordId": 7627902, "parameters": [{"packagingFormat": "TARGZ"}, ...]}]``
        
        :type parameter: list
        
        """
        
        msg = "Submitting order items..."
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # Add the 'Content-Type' option to the header
        self._session.headers.update({'Content-Type': 'application/json'})
        
        # Create the items from the list of results
        # print("results: %s" % results[0])
        coll_key = self._get_conv('collectionId')
        recid_key = self._get_conv('recordId')
        
        items = [{'collectionId': item[coll_key], \
                'recordId': item[recid_key]} \
                for item in results]
        
        items = []
        for r in results:
            # Set the Collection ID and Record ID
            item = {'collectionId': r[coll_key], \
                    'recordId': r[recid_key]}
            
            # Set the priority
            if priority is not None and not priority.lower() == 'medium':
                item['priority'] = priority
            if 'priority' in r.keys():
                item['priority'] == r[self._get_conv('priority')]
            
            # Set parameters
            if parameters is not None:
                item['parameters'] = parameters
            if 'parameters' in r.keys():
                item['parameters'] = r[self._get_conv('parameters')]
                
            if item['collectionId'] == 'NAPL':
                params = item.get('parameters')
                if params is None: params = []
                params.append({"MediaType": "DIGITAL"})
                params.append({"FreeMode": "true"})
                item['parameters'] = params
                
            items.append(item)
        
        # Create the dictionary for the POST request JSON
        post_dict = {"destinations": destinations, 
                    "items": items}
                    
        # Dump the dictionary into a JSON object
        post_json = json.dumps(post_dict)
        
        # Set the RAPI URL
        order_url = "%s/order" % self.rapi_root
        
        logger.debug("RAPI URL:\n\n%s\n" % order_url)
        logger.debug("RAPI POST:\n\n%s\n" % post_json)
        
        # Send the JSON request to the RAPI
        # time_submitted = datetime.datetime.now(tzlocal()).strftime(\
                            # "%Y-%m-%dT%H:%M:%S %Z%z")
        time_submitted = datetime.datetime.now(tzlocal()).isoformat()
        try:
            order_res = self._session.post(url=order_url, data=post_json)
            order_res.raise_for_status()
        except (requests.exceptions.HTTPError, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as req_err:
            msg = "%s Error: %s" % (req_err.__class__.__name__, req_err)
            self._log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt as err:
            msg = "Process ended by user."
            self._log_msg(msg, out_indent='\n')
            print()
            return None
        
        if not order_res.ok:
            err = self._get_exception(order_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self._log_msg(msg, 'warning')
                return msg
        
        # Add the time the order was submitted
        items = order_res.json()['items']
        
        # print("items: %s" % items)
        # answer = input("Press enter...")
        
        for i in items:
            i['dateRapiOrdered'] = time_submitted
            
        order_res = {'items': items}
                
        msg = "Order submitted successfully."
        # print("\n%s%s" % (self._header, msg))
        self._log_msg(msg)
        #logger.info("\n\n\t%s" % msg)
                
        return order_res
        
    def cancel_orderItem(self, orderId, itemId):
        
        """
        Removes an Order Item from the EODMS using the RAPI.
        
        :param orderId: The Order ID of the Order Item to remove.
        :type  orderId: int or str
        :param itemId: The Order Item ID of the Order Item to remove.
        :type  itemId: int or str
            
        :return: Returns the contents of the Delete request (always empty).
        :rtype:  byte str
        
        """
        
        msg = "Removing order item %s..." % itemId
        self._log_msg(msg, log_indent='\n\n\t', out_indent='\n')
        
        # Set the RAPI URL
        order_url = "%s/order/%s/%s" % (self.rapi_root, orderId, itemId)
        
        # Send the JSON request to the RAPI
        try:
            # print("\n%sSubmitting orders..." % self._header)
            cancel_res = self._session.delete(url=order_url)
            cancel_res.raise_for_status()
        except (requests.exceptions.HTTPError, 
                requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout, 
                requests.exceptions.RequestException) as req_err:
            err = self._get_exception(cancel_res)._get_msgs()
            msg = "%s Error: %s - %s" % (req_err.__class__.__name__, \
                    req_err, err[1])
            self._log_msg(msg, 'warning')
            return msg
        except KeyboardInterrupt as err:
            msg = "Process ended by user."
            self._log_msg(msg, out_indent='\n')
            print()
            return None
        
        if not cancel_res.ok:
            err = self._get_exception(cancel_res)
            if isinstance(err, list):
                msg = '; '.join(err)
                self._log_msg(msg, 'warning')
                return msg
                
        msg = "Order removed successfully."
        # print("\n%s%s" % (self._header, msg))
        self._log_msg(msg)
        #logger.info("\n\n\t%s" % msg)
                
        return cancel_res.content
