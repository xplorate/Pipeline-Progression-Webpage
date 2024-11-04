"""
Handles the KML data and presents it in a useable format.

"""


import json
import xmltodict
from shapely.geometry import shape, mapping, Point

# Converts ABGR colour format
def abgr_to_rgba(abgr_color):
    if len(abgr_color) == 8:
        a, b, g, r = abgr_color[:2], abgr_color[2:4], abgr_color[4:6], abgr_color[6:8]
        rgba_color = f"#{r}{g}{b}{a}"
        return rgba_color
    print(f"Invalid ABGR color: {abgr_color}")
    return "#00000000" # black with 0% opacity

# Extracts styles from KML content, including nested styles and style maps
def extract_styles(kml_content):
    styles = {}

    def _extract_styles_from_element(element):
        if isinstance(element, dict):
            if 'Style' in element:
                style_elements = element['Style']
                if not isinstance(style_elements, list):
                    style_elements = [style_elements]
                for style in style_elements:
                    style_id = style.get('@id', '')
                    line_color = style.get('LineStyle', {}).get('color', 'ff0000ff')
                    poly_color = style.get('PolyStyle', {}).get('color', '4d0000ff')
                    styles[style_id] = {
                        'line_color': line_color,
                        'poly_color': poly_color
                    }

            if 'StyleMap' in element:
                style_map_elements = element['StyleMap']
                if not isinstance(style_map_elements, list):
                    style_map_elements = [style_map_elements]
                for style_map in style_map_elements:
                    style_map_id = style_map.get('@id', '')
                    pairs = style_map.get('Pair', [])
                    if not isinstance(pairs, list):
                        pairs = [pairs]
                    for pair in pairs:
                        if pair.get('key') == 'normal':
                            style_url = pair.get('styleUrl', '').replace('#', '')
                            if style_url in styles:
                                styles[style_map_id] = styles[style_url]

            for key in element:
                _extract_styles_from_element(element[key])
        elif isinstance(element, list):
            for item in element:
                _extract_styles_from_element(item)

    _extract_styles_from_element(kml_content)
    return styles

# Extracts all placemarks from KML content, this includes polygons etc.
def extract_all_placemarks(kml_dict):
    placemarks = []

    def _extract_placemarks(element):
        if isinstance(element, dict):
            if 'Placemark' in element:
                placemarks_elem = element['Placemark']
                if not isinstance(placemarks_elem, list):
                    placemarks_elem = [placemarks_elem]
                placemarks.extend(placemarks_elem)
            for key in element:
                _extract_placemarks(element[key])
        elif isinstance(element, list):
            for item in element:
                _extract_placemarks(item)

    _extract_placemarks(kml_dict)
    return placemarks

# Converts a placemark to a GeoJSON feature, which includes the geometry and properties, this must be done otherwise the conversion takes forever.
def convert_placemark_to_feature(placemark, styles):
    geometry = None
    properties = {"name": placemark.get('name', 'Unnamed')}
    style_url = placemark.get('styleUrl', '').replace('#', '')
    properties['style'] = styles.get(style_url, {})

    if 'LineString' in placemark:
        coordinates = placemark['LineString']['coordinates'].strip()
        coords = [[float(coord) for coord in point.split(',')] for point in coordinates.split()]
        geometry = {"type": "LineString", "coordinates": coords}

    elif 'Polygon' in placemark:
        outer_boundary = placemark['Polygon']['outerBoundaryIs']['LinearRing']['coordinates'].strip()
        coords = [[float(coord) for coord in point.split(',')] for point in outer_boundary.split()]
        geometry = {"type": "Polygon", "coordinates": [coords]}

    if geometry:
        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        }
    return None

# Simplifies the geometry of a GeoJSON feature using Shapely, 
#this is only to make the files email friendly. The final version will not have reduced geometry.
def simplify_geometry(geometry, tolerance):
    geom = shape(geometry)
    simplified_geom = geom.simplify(tolerance, preserve_topology=True)
    return mapping(simplified_geom)

def kml_to_geojson(kml_path, geojson_path=None, simplify_tolerance=0.001): # <----------- (0.001 Testing) (0.00001 publish)
    if geojson_path is None:
        geojson_path = kml_path.replace('.kml', '.geojson')

    with open(kml_path, 'r') as file:
        kml_content = xmltodict.parse(file.read())

    if 'kml' in kml_content:
        kml_content = kml_content['kml']
    if 'Document' in kml_content:
        kml_content = kml_content['Document']
    elif 'Folder' in kml_content:
        kml_content = kml_content['Folder']
    else:
        raise KeyError("Unsupported KML structure. Could not find 'kml', 'Document' or 'Folder' key.")

    styles = extract_styles(kml_content)
    placemarks = extract_all_placemarks(kml_content)
    print(f"Total placemarks found in {kml_path}: {len(placemarks)}")

    features = []
    for placemark in placemarks:
        feature = convert_placemark_to_feature(placemark, styles)
        if feature:
            feature['geometry'] = simplify_geometry(feature['geometry'], simplify_tolerance)
            features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    with open(geojson_path, 'w') as f:
        json.dump(geojson, f)

    return geojson_path