import os
import json
import folium
from folium.plugins import Search, MeasureControl, MousePosition
from shapely.geometry import Point
import base64
import geopandas as gpd
import requests
from kml_handler import abgr_to_rgba, kml_to_geojson
from get_files import select_kml_files, save_html_file
import tkinter as tk
from tkinter import simpledialog, filedialog


# Function to fetch data from Overpass API
def fetch_osm_data(query):
    response = requests.get('http://overpass-api.de/api/interpreter', params={'data': query})
    response.raise_for_status()
    return response.json()

def create_map_with_overlay(kml_paths, output_html_path, simplify_tolerance, changes_file, km_completed):
    # Load saved changes
    all_coords = []
    features_list = []

    for kml_path in kml_paths:
        geojson_path = kml_to_geojson(kml_path, simplify_tolerance=simplify_tolerance)
        with open(geojson_path, 'r') as f:
            geojson_data = json.load(f)
            features_list.append(geojson_data['features'])
            for feature in geojson_data['features']:
                coords = feature['geometry']['coordinates']
                if feature['geometry']['type'] == 'Polygon':
                    coords = coords[0]
                all_coords.extend(coords)

    if not all_coords:
        print("No coordinates found in GeoJSON data.")
        return

    avg_lat = sum(coord[1] for coord in all_coords) / len(all_coords)
    avg_lon = sum(coord[0] for coord in all_coords) / len(all_coords)
    map_center = [avg_lat, avg_lon]

    # Create the base map with the default tiles
    map = folium.Map(location=map_center, zoom_start=8, keyboard=False, tiles='Esri.WorldImagery', name='Satellite')


    folium.TileLayer(
        tiles='https://services.arcgisonline.com/arcgis/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        name='Cities, Towns, Localities',
        attr='Esri',
        overlay=True
    ).add_to(map)

    for kml_path, features in zip(kml_paths, features_list):
        geojson_data = {"type": "FeatureCollection", "features": features}

        def style_function(feature):
            style = feature['properties'].get('style', {})
            line_color = abgr_to_rgba(style.get('line_color', 'ff0000ff'))
            poly_color = abgr_to_rgba(style.get('poly_color', '4d0000ff'))
            return {'color': line_color, 'fillColor': poly_color, 'weight': 2, 'fillOpacity': 0.6}

        layer_name = os.path.splitext(os.path.basename(kml_path))[0]
        layer = folium.GeoJson(geojson_data, name=layer_name, style_function=style_function)
        layer.add_child(folium.features.GeoJsonTooltip(fields=['name']))
        layer.add_to(map)

    # Add Mouse Position to the map
    formatter = "function(num) {return L.Util.formatNum(num, 3) + ' &deg; ';};"

    # Define the bounding box coordinates
    bbox = "-27.4,149,-23.7,151.25"

    # Fetch detailed city and town data using Overpass API within the bounding box
    overpass_query = f"""
    [out:json];
    node["place"~"city|town|locality"]({bbox});
    out body;
    >;
    out skel qt;
    """

    osm_data = fetch_osm_data(overpass_query)

    # Convert OSM data to GeoDataFrame
    places = []
    for element in osm_data['elements']:
        if element['type'] == 'node':
            places.append({
                'name': element['tags'].get('name', 'unknown'),
                'lat': element['lat'],
                'lon': element['lon']
            })

    gdf = gpd.GeoDataFrame(places, geometry=[Point(xy) for xy in zip([place['lon'] for place in places], [place['lat'] for place in places])])
    gdf.crs = "EPSG:4326"

    # Convert to GeoJSON
    cities_towns_geojson = gdf.to_json()

    # Define the style function for the markers
    def cities_towns_marker_style(feature):
        return {
            "radius": 2.5,
            "fillColor": "#000",
            "color": "#000",
            "weight": 1,
            "opacity": 0,
            "fillOpacity": 0,
        }

    # Add city and town search using custom marker style
    cities_towns_layer = folium.GeoJson(
        cities_towns_geojson,
        style_function=None,
        marker=folium.CircleMarker(**cities_towns_marker_style(None)),
        show=False,
        control=False  # This prevents the layer from appearing in Layer Control
    ).add_to(map)

    # # Add a marker for the not flown section
    # Problem_message_1 = "Link range issues prevented completion of this section,<br>but will be rectified from another deployment location"

    # Marker_Lookerbie_Link_Loss = folium.Marker(popup='Problem', tooltip=Problem_message_1, location=[-24.631878, 150.618560], icon=folium.Icon('red'))
    # Marker_Lookerbie_Link_Loss.add_to(map)    # Add Search control to the map

    Search(
        layer=cities_towns_layer,
        geom_type="Point",
        placeholder="Search for locations...",
        collapsed=False,
        search_label="name",
    ).add_to(map)

    folium.LayerControl().add_to(map)

    MousePosition(
        position="bottomright",
        separator=" | ",
        empty_string="NaN",
        lng_first=True,
        num_digits=20,
        prefix="Coordinates:",
        lat_formatter=formatter,
        lng_formatter=formatter,
    ).add_to(map)

    # Add Measure Control to the map
    MeasureControl().add_to(map)
    
    # Encode the image to base64
    image_path = "Xplorate_Logo.png"
    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    image_data_url = f"data:image/png;base64,{encoded_image}"

    logo_html = f"""
    <div style="position: fixed; 
                bottom: 10px; 
                left: 10px; 
                width: 270px; 
                height: 65px; 
                z-index:9999;
                box-shadow: 0px 0px 10px 0px black;">
        <img src="{image_data_url}" style="width: 100%; height: 100%;">
    </div>
    """
    map.get_root().html.add_child(folium.Element(logo_html))

    # Add Xplorate_Logo_tab.ico to the webpage tab
    icon_path = "Xplorate_Logo_tab.ico"
    with open(icon_path, "rb") as icon_file:
        encoded_icon = base64.b64encode(icon_file.read()).decode('utf-8')
    icon_data_url = f"data:image/x-icon;base64,{encoded_icon}"
    
    favicon_html = f'''
    <link rel="shortcut icon" href="{icon_data_url}">
    <link rel="icon" href="{icon_data_url}" type="image/x-icon">
    '''
    map.get_root().html.add_child(folium.Element(favicon_html))

    # Ensure the favicon is set in the head of the HTML
    map.get_root().header.add_child(folium.Element(favicon_html))

    # Add custom legend
    legend_html = '''
        <div style="
            position: fixed; 
            bottom: 90px; 
            left: 10px; 
            width: 270px; 
            height: 110px; 
            background-color: white; 
            border:2px solid grey; 
            z-index:9999; 
            font-size:10px;
            box-shadow: 0px 0px 10px 0px black;
            padding: 10px;
        ">
            <div style="margin-bottom: 5px;">
                &nbsp; <span style="display: inline-block; vertical-align: middle;">
                    <div style="display: inline-block; height: 15px; width: 15px; background-color: rgba(128, 0, 128, 0.5); border-radius: 50%; position: relative; box-shadow: 0 0 0 2px rgba(128, 0, 128, 1.0);"></div>
                </span>&nbsp; <span style="font-size: 10px;">QGC Pty Limited as Shell</span> 
            </div>
            <div style="margin-bottom: 5px;">
                &nbsp; <span style="display: inline-block; vertical-align: middle;">
                    <div style="display: inline-block; height: 15px; width: 15px; background-color: rgba(0, 255, 0, 0.4); border-radius: 50%; position: relative; box-shadow: 0 0 0 2px rgba(0, 255, 0, 1.0);"></div>
                </span>&nbsp; <span style="font-size: 10px;">Xplorate - Data captured successfully</span> 
            </div>
            <div style="margin-bottom: 5px;">
                &nbsp; <span style="display: inline-block; vertical-align: middle;">
                    <div style="display: inline-block; height: 15px; width: 15px; background-color: rgba(255, 0, 0, 0.4); border-radius: 50%; position: relative; box-shadow: 0 0 0 2px rgba(255, 0, 0, 1.0);"></div>
                </span>&nbsp; <span style="font-size: 10px;">Xplorate - Data NOT captured</span> 
            </div>
            <div style="margin-bottom: 5px;">
                &nbsp; <span style="display: inline-block; vertical-align: middle;">
                    <div style="display: inline-block; height: 15px; width: 15px; background-color: rgba(0, 0, 0, 0.2); border-radius: 50%; position: relative; box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.4);"></div>
                </span>&nbsp; <span style="font-size: 10px;">Cities, Towns & Localities (layer control, top right)</span> 
            </div>
        </div>
    '''

    map.get_root().html.add_child(folium.Element(legend_html))

    # Add static text for kilometers completed
    static_text_html = f"""
    <div style="position: fixed; 
                top: 10px; 
                left: 50%; 
                transform: translateX(-50%);
                font-size: 20px; 
                font-weight: bold; 
                color: red;
                background-color: white;
                border: 2px solid red;
                box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
                padding: 10px 10px;
                z-index:9999;">
        Kilometers completed: {km_completed}
    </div>
    """
    map.get_root().html.add_child(folium.Element(static_text_html))

    map.save(output_html_path)
    print(f"Map saved as HTML at: {output_html_path}")

def main():
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    kml_file_paths = select_kml_files()
    if not kml_file_paths:
        print("No KML files selected.")
        return

    km_completed = simpledialog.askstring("Input", "Enter the number of kilometers completed:")
    if not km_completed:
        print("No input for kilometers completed.")
        return

    try:
        simplify_tolerance = float(simpledialog.askstring("Input", "Enter simplify tolerance (e.g., 0.001):"))
    except ValueError:
        print("Invalid input for simplify tolerance. Using default value: 0.001")
        simplify_tolerance = 0.0001

    output_html_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML files", "*.html")])
    if not output_html_path:
        print("No output HTML file selected.")
        return

    changes_file = "changes.txt"  # File to store changes
    create_map_with_overlay(kml_file_paths, output_html_path, simplify_tolerance, changes_file, km_completed)

if __name__ == "__main__":
    main()
