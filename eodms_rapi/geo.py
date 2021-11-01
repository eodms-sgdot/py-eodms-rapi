##############################################################################
# MIT License
# 
# Copyright (c) 2020-2021 Her Majesty the Queen in Right of Canada, as 
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
import re
from xml.etree import ElementTree
import json
import logging
import traceback
from geomet import wkt
import decimal

try:
    import osgeo.ogr as ogr
    import osgeo.osr as osr
    GDAL_INSTALLED = True
except ImportError:
    try:
        import ogr
        import osr
        GDAL_INSTALLED = True
    except ImportError:
        GDAL_INSTALLED = False
        
# try:
    # import ogr
    # import osr
    # GDAL_INSTALLED = True
# except ImportError:
    # GDAL_INSTALLED = False
    
# try:
    # import geojson
    # GEOJSON_INSTALLED = True
# except ImportError:
    # GEOJSON_INSTALLED = False

class EODMSGeo:
    """
    The Geo class contains all the methods and functions used to perform geographic processes mainly using OGR.
    """
    
    def __init__(self, eodmsrapi):
        """
        Initializer for the Geo object.
        
        :param eodmsrapi: The parent EODMSRAPI object.
        :type  eodmsrapi: eodms.EODMSRAPI
        
        """
        self.aoi = None
        
        self.logger = logging.getLogger('EODMSRAPI')
        
        self.wkt_types = ['point', 'linestring', 'polygon', \
                        'multipoint', 'multilinestring', 'multipolygon']
        self.eodmsrapi = eodmsrapi
    
    def _check_ogr(self):
        """
        There is another ogr Python package. This will check if it was
            imported instead of the proper ogr.
        """
        
        if ogr.__doc__ is not None and \
            ogr.__doc__.find("Module providing one api for multiple git " \
            "services") > -1:
            msg = "Another package named 'ogr' is installed."
            self.eodmsrapi._log_msg(msg, 'warning')
            return False
        
        return True
    
    def _convert_list(self, in_feat, out='wkt'):
        """
        Converts a list to a specified output.
        
        :param in_feat: The input feature(s).
        :type  in_feat: list
        :param out: The type of output, either 'wkt' or 'json'.
        :type  out: str
        
        :return: The converted feature(s) to the specified output.
        :rtype: json or str
        """
        
        pnts = [list(p) for p in in_feat]
            
        if len(pnts) == 1:
            geojson = {"type": "Point", "coordinates": pnts[0]}
        else:
            geojson = {"type": "Polygon", "coordinates": [pnts]}
        
        if out == 'json':
            return geojson
        else:
            out_wkt = wkt.dumps(geojson)
            
        return out_wkt
    
    def _is_wkt(self, in_feat, show_error=False, return_wkt=False):
        """
        Verifies if a string is WKT.
        
        :param in_feat: Input string containing a WKT.
        :type  in_feat: str
        :param show_error: Determines whether to display the error.
        :type  show_error: boolean
        :param return_wkt: Determines whether to return the converted WKT if True.
        :type  return_wkt: boolean
        
        :return: If the input is a valid WKT, return WKT if return_wkt is True or return just True; False if not valid.
        :rtype: str or boolean
        """
        
        try:
            wkt_val = wkt.loads(in_feat.upper())
        except (ValueError, TypeError) as e:
            if show_error:
                self.eodmsrapi._log_msg(str(e), 'warning')
            return False
            
        if return_wkt:
            return wkt_val
        else:
            return True
            
    def _remove_zeroTrail(self, in_wkt):
        """
        Removes the trailing zeros in coordinates after the decimal in a WKT.
        
        :param in_wkt: The input WKT.
        :type  in_wkt: str
        
        :return: The WKT without trailing zeros after the decimal.
        :rtype: str
        """
        
        numbers = re.findall("\d+\.\d+", in_wkt)
        
        out_wkt = in_wkt
        for num in numbers:
            flt_num = float(num)
            out_wkt = out_wkt.replace(num, str(flt_num))
            
        return out_wkt
        
    def _split_multi(self, feats, in_type='json', out='wkt'):
        """
        Splits multi-geometry into several valid geometry for the RAPI.
        
        :param feats: The input feature(s).
        :type  feats: json, str or list
        :param in_type: Helps determine the type of input (either 'wkt', 'json' or 'list').
        :type  in_type: str
        :param out: Determines the type of output (either 'wkt' or 'json').
        :type  out: str
        
        :return: The geometry (or geometries) in the specified output type.
        :rtype: json, str
        """
        
        if in_type == 'wkt':
            
            # Convert feats to json for easier manipulation
            json_geom = self._is_wkt(feats, True, True)
            
        elif in_type == 'list':
            json_geom = self._convert_list(feats, 'json')
        else:
            json_geom = feats
        
        geom_type = json_geom.get('type').lower()
        if geom_type.find('multi') > -1:
            feat_coords = json_geom.get('coordinates')
            out_geom = []
            if geom_type == 'multipoint':
                for pnt in feat_coords:
                    geom = {'type': 'Point', 'coordinates': pnt}
                    out_geom.append(geom)
            elif geom_type == 'multilinestring':
                for line in feat_coords:
                    geom = {'type': 'LineString', 'coordinates': line}
                    out_geom.append(geom)
            elif geom_type == 'multipolygon':
                for poly in feat_coords:
                    geom = {'type': 'Polygon', 'coordinates': poly}
                    out_geom.append(geom)
        else:
            out_geom = json_geom
        
        if out == 'wkt':
            out_feats = []
            if isinstance(out_geom, list):
                for g in out_geom:
                    wkt_feat = self.convert_toWKT(g, 'json')
                    out_feats.append(wkt_feat)
            else:
                out_feats = self.convert_toWKT(out_geom, 'json')
        else:
            out_feats = out_geom
        
        return out_feats
        
    def add_geom(self, in_src):
        """
        Processes the source and converts it for use in the RAPI.
        
        :param in_src: The in_src can either be:
                    
            - a filename (ESRI Shapefile, KML, GML or GeoJSON) of multiple features
            - a WKT format string of a single feature
            - the 'geometry' entry from a GeoJSON Feature
            - a list of coordinates (ex: ``[(x1, y1), (x2, y2), ...]``)
        
        :type  in_src: str
        
        :return: A string of the WKT of the feature.
        :rtype:  str
        
        """
        
        if in_src is None:
            return None
            
        # If the source is in JSON format
        if self.eodmsrapi._is_json(in_src):
            in_src = json.loads(in_src)
            
        if isinstance(in_src, dict):
            # self.feats = self.convert_toWKT(in_src, 'json')
            self.feats = self._split_multi(in_src, 'json')
            return self.feats
            
        if isinstance(in_src, list):
            # self.feats = self.convert_toWKT(in_src, 'list')
            self.feats = self._split_multi(in_src, 'list')
            return self.feats
        
        # If the source is a file
        if os.path.isfile(in_src):
            self.feats = self.get_features(in_src)
            return self.feats
        
        if os.path.isdir(in_src):
            return None
        
        if in_src.find('(') > -1 and in_src.find(')') > -1:
            if self._is_wkt(in_src, True):
                # Can only be a single WKT object
                self.feats = self._split_multi(in_src, 'wkt')
                return self.feats
            
        # If the source is a list of coordinates
        if not isinstance(in_src, list):
            try:
                in_src = eval(in_src)
            except SyntaxError as err:
                self.logger.warning("%s" % err)
                return err
                
    def convert_coords(self, coord_lst, geom_type):
        """
        Converts a list of points to GeoJSON format.
        
        :param coord_lst: A list of points.
        :type  coord_lst: list
        :param geom_type: The type of geometry, either 'Point', 
                'LineString' or 'Polygon'.
        :type  geom_type: str
                
        :return: A dictionary in the GeoJSON format.
        :rtype:  dict
        
        """
        
        pnts_array = []
        for c in coord_lst:
            pnts = [p.strip('\n').strip('\t').split(',') for p in \
                    c.split(' ') if not p.strip('\n').strip('\t') == '']
            pnts_array += pnts
        
        if geom_type == 'Point':
            json_geom = {'type': 'Point', 'coordinates': \
                        [float(pnts[0][0]), float(pnts[0][1])]}
        elif geom_type == 'LineString':
            json_geom = {'type': 'LineString', 'coordinates': \
                        [[float(p[0]), float(p[1])] \
                        for p in pnts]}
        else:
            json_geom = {'type': 'Polygon', 'coordinates': \
                        [[[float(p[0]), float(p[1])] \
                        for p in pnts]]}
                        
        return json_geom
        
    def convert_imageGeom(self, coords, output='array'):
        """
        Converts a list of coordinates from the RAPI to a polygon geometry, array of points or as WKT.
        
        :param coords: A list of coordinates from the RAPI results.
        :type  coords: list
        :param output: The type of return, can be 'array', 'wkt' or 'geom'.
        :type  output: str
        
        :return: Either a polygon geometry, WKT or array of points.
        :rtype:  multiple types
        
        """
        
        if isinstance(coords, dict):
            
            if 'coordinates' in coords.keys():
                val = coords['coordinates']
                level = 0
                while isinstance(val, list):
                    val = val[0]
                    level += 1
                lst_level = level - 2
                
                if lst_level > -1:
                    pnt_array = eval("coords['coordinates']" + '[0]'*(lst_level))
                else:
                    pnt_array = coords['coordinates']
            else:
                logger.warning("No coordinates provided.")
                return None
        else:
            pnt_array = coords[0]
        
        # Get the points from the coordinates list
        pnt1 = pnt_array[0]
        pnt2 = pnt_array[1]
        pnt3 = pnt_array[2]
        pnt4 = pnt_array[3]
        
        if GDAL_INSTALLED:
            if not self._check_ogr(): 
                msg = "Cannot convert geometry."
                self.eodmsrapi._log_msg(msg, 'warning')
                return None
            
            # Create ring
            ring = ogr.Geometry(ogr.wkbLinearRing)
            ring.AddPoint(pnt1[0], pnt1[1])
            ring.AddPoint(pnt2[0], pnt2[1])
            ring.AddPoint(pnt3[0], pnt3[1])
            ring.AddPoint(pnt4[0], pnt4[1])
            ring.AddPoint(pnt1[0], pnt1[1])

            # Create polygon
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            
            # Send specified output
            if output == 'wkt':
                return poly.ExportToWkt()
            elif output == 'geom':
                return poly
            else:
                return pnt_array
                
        else:
            if output == 'wkt':
                # Convert values in point array to strings
                pnt_array = [[str(p[0]), str(p[1])] for p in pnt_array]
                
                return "POLYGON ((%s))" % ', '.join([' '.join(pnt) \
                    for pnt in pnt_array])
            else:
                return pnt_array
            
    # def convert_fromWKT(self, in_feat):
        # """
        # Converts a WKT to a GDAL geometry.
        
        # :param in_feat: The WKT of the feature.
        # :type  in_feat: str
        
        # :return: The polygon geometry of the input WKT.
        # :rtype:  ogr.Geometry
        
        # """
        
        # if GDAL_INSTALLED:
            # out_poly = ogr.CreateGeometryFromWkt(in_feat)
        
        # return out_poly
        
    def convert_toWKT(self, in_feat, in_type):
        """
        Converts a feature into WKT format.
        
        :param in_feat: The input feature, either as a GeoJSON 
                dictionary or list of points.
        :type  in_feat: dict or list
            
        :return: The input feature converted to WKT.
        :rtype:  str
        
        """
        
        out_wkt = None
        if in_type == 'json':
            out_wkt = wkt.dumps(in_feat)
        elif in_type == 'list':
            out_wkt = self._convert_list(in_feat)
        
        out_wkt = self._remove_zeroTrail(out_wkt)
        
        return out_wkt
            
    def convert_toGeoJSON(self, results, output='FeatureCollection'):
        """
        Converts a get of RAPI results to GeoJSON geometries.
        
        :param results: A list of results from the RAPI.
        :type  results: list
        :param output: The output of the results (either 'FeatureCollection' 
                or 'list' for a list of features in geojson)
        :type  output: str
        
        :return: A dictionary of a GeoJSON FeatureCollection.
        :rtype: dict
        """
        
        if isinstance(results, dict):
            results = [results]
            
        features = []
        for rec in results:
            geom = rec.get(self.eodmsrapi._get_conv('geometry'))
            props = self.eodmsrapi._parse_metadata(rec)
            
            feat = {"type": "Feature", "geometry": geom, "properties": props}
            
            features.append(feat)
        
        if output == 'list': return features
        
        feature_collection = {"type": "FeatureCollection", 
                            "features": features}
        
        return feature_collection
        
    def process_polygon(self, geom, t_crs):
        
        # Convert the geometry to WGS84
        s_crs = geom.GetSpatialReference()
        
        if s_crs is None:
            s_crs = osr.SpatialReference()
            s_crs.ImportFromEPSG(4326)
        
        # Get the EPSG codes from the spatial references
        epsg_sCrs = s_crs.GetAttrValue("AUTHORITY", 1)
        epsg_tCrs = t_crs.GetAttrValue("AUTHORITY", 1)
        
        if not str(epsg_sCrs) == '4326':
            if epsg_tCrs is None:
                print("\nCannot reproject AOI.")
                return None
            
            if not s_crs.IsSame(t_crs) and not epsg_sCrs == epsg_tCrs:
                # Create the CoordinateTransformation
                print("\nReprojecting input AOI...")
                coordTrans = osr.CoordinateTransformation(s_crs, t_crs)
                geom.Transform(coordTrans)
                
                # Reverse x and y of transformed geometry
                ring = geom.GetGeometryRef(0)
                for i in range(ring.GetPointCount()):
                    ring.SetPoint(i, ring.GetY(i), ring.GetX(i))
        
        # Convert multipolygon to polygon (if applicable)
        if geom.GetGeometryType() == 6:
            geom = geom.UnionCascaded()
        
        # Convert to WKT
        return geom.ExportToWkt()
        
    def get_features(self, in_src):
        """
        Extracts the features from an AOI file.
        
        :param in_src: The input filename of the AOI file. Can either be 
                            a GML, KML, GeoJSON, or Shapefile.
        :type  in_src: str
        
        :return: The AOI in WKT format.
        :rtype:  str
        
        """
        
        out_feats = []
        if GDAL_INSTALLED:
            # There is another ogr Python package that might have been imported
            #   Check if its the wrong ogr
            if not self._check_ogr(): 
                msg = "Cannot import feature using OGR."
                self.eodmsrapi._log_msg(msg, 'warning')
                return None
        
            # Determine the OGR driver of the input AOI
            if in_src.find('.gml') > -1:
                ogr_driver = 'GML'
            elif in_src.find('.kml') > -1:
                ogr_driver = 'KML'
            elif in_src.find('.json') > -1 or in_src.find('.geojson') > -1:
                ogr_driver = 'GeoJSON'
            elif in_src.find('.shp') > -1:
                ogr_driver = 'ESRI Shapefile'
            else:
                err_msg = "The AOI file type could not be determined."
                self.logger.error(err_msg)
                return None
                
            # Open AOI file and extract AOI
            driver = ogr.GetDriverByName(ogr_driver)
            ds = driver.Open(in_src, 0)
            
            # Get the layer from the file
            lyr = ds.GetLayer()
            
            # Set the target spatial reference to WGS84
            t_crs = osr.SpatialReference()
            t_crs.ImportFromEPSG(4326)
            
            for feat in lyr:
                # Create the geometry
                geom = feat.GetGeometryRef()
                
                if geom.GetGeometryName() == 'MULTIPOLYGON':
                    for geom_part in geom:
                        # print("geom_part: %s" % geom_part)
                        out_feats.append(self.process_polygon(geom_part, t_crs))
                else:
                    out_feats.append(self.process_polygon(geom, t_crs))
                
        else:
            
            geom_choices = ['Point', 'LineString', 'Polygon']
            
            # Determine the OGR driver of the input AOI
            if in_src.find('.gml') > -1 or in_src.find('.kml') > -1:
                
                with open(in_src, 'rt') as f:
                    tree = ElementTree.parse(f)
                    root = tree.getroot()
                
                if in_src.find('.gml') > -1:
                    for feat in root.findall('.//{http://www.opengis.net/' \
                        'gml}featureMember'):
                        
                        # Get geometry type
                        geom_type = 'Polygon'
                        for elem in feat.findall('*'):
                            tag = elem.tag.replace('{http://ogr.maptools.' \
                                'org/}', '')
                            if tag in geom_choices:
                                geom_type = tag
                        
                        coord_lst = []
                        for coords in root.findall('.//{http://www.opengis' \
                            '.net/gml}coordinates'):
                            coord_lst.append(coords.text)
                            
                        json_geom = self.convert_coords(coord_lst, geom_type)
                        
                        wkt_feat = self._split_multi(json_geom)
                            
                        if isinstance(wkt_feat, list):
                            out_feats += wkt_feat
                        else:
                            out_feats.append(wkt_feat)
                else:
                    for plcmark in root.findall('.//{http://www.opengis.net/' \
                        'kml/2.2}Placemark'):
                        
                        # Get geometry type
                        geom_type = 'Polygon'
                        for elem in plcmark.findall('*'):
                            tag = elem.tag.replace('{http://www.opengis.net/' \
                                    'kml/2.2}', '')
                            if tag in geom_choices:
                                geom_type = tag
                        
                        coord_lst = []
                        for coords in plcmark.findall(\
                            './/{http://www.opengis.net/kml/2.2}coordinates'):
                            coord_lst.append(coords.text)
                        
                        json_geom = self.convert_coords(coord_lst, geom_type)
                        
                        wkt_feat = self._split_multi(json_geom)
                        
                        if isinstance(wkt_feat, list):
                            out_feats += wkt_feat
                        else:
                            out_feats.append(wkt_feat)
                
            elif in_src.find('.json') > -1 or in_src.find('.geojson') > -1:
                with open(in_src) as f:
                    data = json.load(f)
                
                feats = data['features']
                for f in feats:
                    
                    wkt_feat = self._split_multi(f['geometry'])
                                
                    if isinstance(wkt_feat, list):
                        out_feats += wkt_feat
                    else:
                        out_feats.append(wkt_feat)
                            
            elif in_src.find('.shp') > -1:
                msg = "Could not open shapefile. The GDAL Python Package " \
                        "must be installed to use shapefiles."
                self.logger.warning(msg)
                return None
            else:
                self.logger.warning(msg)
                return None
            
        return out_feats
