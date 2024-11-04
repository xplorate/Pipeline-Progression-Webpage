"""

Filedialog box open and save functions

"""

import tkinter as tk
from tkinter import filedialog

# Selects KML files using a file dialog
def select_kml_files():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    kml_file_paths = filedialog.askopenfilenames(filetypes=[("KML files", "*.kml")])
    root.destroy()
    return kml_file_paths

# Saves an HTML file using a file dialog 
def save_html_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    html_file_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML files", "*.html")])
    root.destroy()
    return html_file_path