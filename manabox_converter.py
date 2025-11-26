import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, Menu, messagebox
import webbrowser
from threading import Thread
import time
import requests
from PIL import Image, ImageTk
from io import BytesIO

# --- Vendor data ---
VENDORS = ["Card Kingdom", "TCGPlayer", "Card Conduit", "Star City Games"]
VENDOR_LINKS = {
    "Card Kingdom": "https://www.cardkingdom.com/static/csvImport",
    "TCGPlayer": "https://seller.tcgplayer.com/sell-with-us/marketplace",
    "Card Conduit": "https://cardconduit.com/estimates/create",
    "Star City Games": "https://sellyourcards.starcitygames.com/mtg/upload"
}

def convert_for_cardkingdom_row(row):
    title = str(row.get('Name', '')).split("//")[0].strip()
    edition = row.get('Set name', '')
    foil = 1 if str(row.get('Foil', '')).strip().lower() == 'foil' else 0
    qty = int(row.get('Quantity', 0))
    return {'title': title, 'edition': edition, 'foil': foil, 'quantity': qty}

# --- Styled Button ---
class StyledButton(tk.Button):
    def __init__(self, master, text, bg="#7289DA", fg="#FFFFFF",
                 hover_bg=None, font=("Inter", 12, "bold"), command=None, **kwargs):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font,
                         bd=0, relief="flat", padx=15, pady=6, command=command, **kwargs)
        self.default_bg = bg
        self.hover_bg = hover_bg if hover_bg else bg
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        self.config(bg=self.hover_bg)

    def on_leave(self, e):
        self.config(bg=self.default_bg)

# --- Main App ---
class ManaBoxConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ManaBox CSV Converter V4 - with Card Previews")
        self.configure(bg="#2C2F33")

        # --- Maximize window ---
        self.state('zoomed')

        # --- Data ---
        self.df = None
        self.converted_data = []
        self.filter_values = {"title": "", "edition": "", "foil": "", "quantity": ""}
        self.sort_state = {"title": False, "edition": False, "foil": False, "quantity": False}
        self.sorted_column = None
        self.vendor = tk.StringVar(value="Card Kingdom")
        self.font = ("Inter", 12)
        
        # --- Image cache ---
        self.image_cache = {}
        self.current_image = None

        # --- Progress bar colors ---
        self.progress_colors = {
            "Orange": "#FFA500",
            "Green": "#43B581",
            "Blue": "#0078d4",
            "Purple": "#9B59B6",
            "Red": "#F04747",
            "Teal": "#1ABC9C",
            "Yellow": "#FFD700",
            "Pink": "#E91E63"
        }
        self.current_progress_color = tk.StringVar(value="Green")

        self.create_menu()
        self.create_widgets()
        self.create_progress_bar()
        self.create_preview_pane()
        self.create_status_frame()

    # --- Menu ---
    def create_menu(self):
        menubar = Menu(self)
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        settings_menu = Menu(menubar, tearoff=0)
        color_menu = Menu(settings_menu, tearoff=0)
        for color_name in self.progress_colors:
            color_menu.add_radiobutton(label=color_name, variable=self.current_progress_color,
                                       value=color_name, command=self.apply_progress_color)
        settings_menu.add_cascade(label="Progress Bar Color", menu=color_menu)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.config(menu=menubar)

    # --- Widgets ---
    def create_widgets(self):
        # Vendor frame
        vendor_frame = tk.LabelFrame(self, text="Vendor Selection", bg="#2C2F33", fg="#FFFFFF",
                                     font=self.font, padx=10, pady=10)
        vendor_frame.pack(fill="x", padx=20, pady=(10,5))
        ttk.Combobox(vendor_frame, textvariable=self.vendor, values=VENDORS,
                     state="readonly", font=self.font).pack(side="left", padx=(0,10))
        StyledButton(vendor_frame, text="Open Vendor Page", bg="#43B581", hover_bg="#66CDAA",
                     font=("Inter", 11, "bold"), command=self.open_vendor_link).pack(side="left")

        # Buttons frame
        button_frame = tk.Frame(self, bg="#2C2F33")
        button_frame.pack(fill="x", padx=20, pady=20)
        StyledButton(button_frame, text="Select File", bg="#88FF00", hover_bg="#ACFF4D",
                     font=("Inter", 14, "bold"), command=self.open_file).pack(side="left", padx=10)
        StyledButton(button_frame, text="Convert & Preview", bg="#F04747", hover_bg="#FF6F61",
                     font=("Inter", 14, "bold"), command=self.start_conversion).pack(side="left", padx=10)
        self.save_button = StyledButton(button_frame, text="Save Converted CSV", bg="#7289DA", hover_bg="#99AAB5",
                                        font=("Inter", 14, "bold"), command=self.save_converted_data, state="disabled")
        self.save_button.pack(side="left", padx=10)

    # --- Progress bar ---
    def create_progress_bar(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Dark.Horizontal.TProgressbar',
                        troughcolor='#23272A',
                        background=self.progress_colors[self.current_progress_color.get()],
                        thickness=20)
        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate",
                                        style='Dark.Horizontal.TProgressbar')
        self.progress.pack(fill="x", padx=20, pady=(0,10))

    def apply_progress_color(self):
        color_name = self.current_progress_color.get()
        style = ttk.Style(self)
        style.configure('Dark.Horizontal.TProgressbar', background=self.progress_colors[color_name])
        self.update_status(f"Progress bar color set to {color_name}", "info")

    # --- Preview pane ---
    def create_preview_pane(self):
        preview_frame = tk.LabelFrame(self, text="Preview Converted Data", bg="#2C2F33", fg="#FFFFFF",
                                      font=self.font, padx=10, pady=10)
        preview_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Filter row with dynamic placeholders
        filter_frame = tk.Frame(preview_frame, bg="#2C2F33")
        filter_frame.pack(fill="x", pady=(0,5))
        self.filter_entries = {}
        for idx, col in enumerate(("title", "edition", "foil", "quantity")):
            entry = tk.Entry(filter_frame, width=15)
            entry.grid(row=0, column=idx, padx=5)
            placeholder = f"Filter {col}"
            entry.insert(0, placeholder)

            def on_focus_in(e, ent=entry, ph=placeholder):
                if ent.get() == ph:
                    ent.delete(0, "end")
            def on_focus_out(e, ent=entry, ph=placeholder):
                if not ent.get():
                    ent.insert(0, ph)

            entry.bind("<FocusIn>", on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)
            entry.bind("<KeyRelease>", lambda e, col=col, ent=entry: self.update_filter(col, ent.get()))
            self.filter_entries[col] = entry

        # Main content frame (treeview + image preview)
        content_frame = tk.Frame(preview_frame, bg="#2C2F33")
        content_frame.pack(fill="both", expand=True)

        # Treeview frame
        tree_frame = tk.Frame(content_frame, bg="#2C2F33")
        tree_frame.pack(side="left", fill="both", expand=True)
        
        self.preview_tree = ttk.Treeview(tree_frame, columns=("title", "edition", "foil", "quantity"), show="headings")
        for col in ("title", "edition", "foil", "quantity"):
            self.preview_tree.heading(col, text=f"{col.capitalize()} ↑↓", command=lambda c=col: self.sort_preview(c))
            self.preview_tree.column(col, width=150, anchor="center")
        self.preview_tree.pack(fill="both", expand=True, side="left")
        
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscroll=scroll_y.set)
        scroll_y.pack(fill="y", side="right")
        
        # Bind selection event
        self.preview_tree.bind("<<TreeviewSelect>>", self.on_card_select)

        # Image preview frame
        image_frame = tk.LabelFrame(content_frame, text="Card Preview", bg="#2C2F33", fg="#FFFFFF",
                                   font=("Inter", 10, "bold"), width=300, height=400)
        image_frame.pack(side="right", fill="y", padx=(10, 0))
        image_frame.pack_propagate(False)
        
        self.image_label = tk.Label(image_frame, bg="#23272A", fg="#FFFFFF", 
                                    text="Select a card to preview", font=("Inter", 10))
        self.image_label.pack(fill="both", expand=True, padx=5, pady=5)

        # Summary label
        self.summary_label = tk.Label(self, text="Rows: 0 | Total Quantity: 0", bg="#2C2F33", fg="#FFFFFF", font=self.font)
        self.summary_label.pack(anchor="w", padx=25, pady=(0,10))

    # --- Card Image Functions ---
    def on_card_select(self, event):
        selection = self.preview_tree.selection()
        if not selection:
            return
        
        item = self.preview_tree.item(selection[0])
        values = item['values']
        if not values:
            return
        
        card_name = values[0]
        set_name = values[1] if len(values) > 1 else ""
        # Convert to int to handle both string and int values from treeview
        is_foil = int(values[2]) if len(values) > 2 else 0
        
        # Show loading message
        foil_text = " ✨ FOIL" if is_foil == 1 else ""
        self.image_label.config(image='', text=f"Loading card image{foil_text}...", compound='center')
        self.update_idletasks()
        
        # Fetch image in background thread
        Thread(target=self.fetch_and_display_card, args=(card_name, set_name, is_foil), daemon=True).start()

    def fetch_and_display_card(self, card_name, set_name, is_foil=0):
        cache_key = f"{card_name}_{set_name}_{is_foil}"
        
        # Check cache first
        if cache_key in self.image_cache:
            self.display_image(self.image_cache[cache_key], is_foil)
            return
        
        try:
            # Strategy 1: Try with set name/code if provided
            if set_name:
                search_url = "https://api.scryfall.com/cards/named"
                params = {"fuzzy": card_name, "set": set_name}
                response = requests.get(search_url, params=params, timeout=5)
                
                if response.status_code == 200:
                    card_data = response.json()
                    image_url = self.extract_image_url(card_data, is_foil)
                    if image_url:
                        if self.download_and_cache_image(image_url, cache_key, is_foil):
                            return
            
            # Strategy 2: Try without set (gets most recent printing)
            search_url = "https://api.scryfall.com/cards/named"
            params = {"fuzzy": card_name}
            response = requests.get(search_url, params=params, timeout=5)
            
            if response.status_code == 200:
                card_data = response.json()
                image_url = self.extract_image_url(card_data, is_foil)
                if image_url:
                    if self.download_and_cache_image(image_url, cache_key, is_foil):
                        return
            
            # Strategy 3: Try general search API
            search_url = "https://api.scryfall.com/cards/search"
            params = {"q": f'!"{card_name}"', "unique": "prints", "order": "released"}
            response = requests.get(search_url, params=params, timeout=5)
            
            if response.status_code == 200:
                search_results = response.json()
                if search_results.get('data'):
                    # Get first result
                    card_data = search_results['data'][0]
                    image_url = self.extract_image_url(card_data, is_foil)
                    if image_url:
                        if self.download_and_cache_image(image_url, cache_key, is_foil):
                            return
            
            # If we get here, nothing worked
            foil_text = " (Foil)" if is_foil == 1 else ""
            self.after(0, lambda: self.image_label.config(
                image='', text=f"Card not found:\n{card_name}{foil_text}\n\nSet: {set_name or 'Any'}", compound='center'))
                
        except requests.Timeout:
            self.after(0, lambda: self.image_label.config(
                image='', text="Request timeout\nTry again", compound='center'))
        except Exception as e:
            self.after(0, lambda: self.image_label.config(
                image='', text=f"Error loading image:\n{str(e)[:50]}", compound='center'))
    
    def extract_image_url(self, card_data, is_foil=0):
        """Extract image URL from Scryfall card data, preferring foil if requested"""
        image_uris = card_data.get('image_uris', {})
        if not image_uris and 'card_faces' in card_data:
            # Double-faced cards
            image_uris = card_data['card_faces'][0].get('image_uris', {})
        
        # If foil is requested, try to get foil version first, then fall back to normal
        if is_foil == 1:
            foil_url = image_uris.get('normal') or image_uris.get('large') or image_uris.get('small')
            # Check if this card has a foil treatment available
            # Scryfall doesn't have separate foil/non-foil images in image_uris,
            # but we can check if the card is available in foil
            if card_data.get('finishes') and 'foil' in card_data.get('finishes', []):
                return foil_url
            # If no foil finish available, return normal anyway
            return foil_url
        
        # Non-foil or fallback
        return image_uris.get('normal') or image_uris.get('small') or image_uris.get('large')
    
    def download_and_cache_image(self, image_url, cache_key, is_foil=0):
        """Download image and cache it. Returns True on success."""
        try:
            img_response = requests.get(image_url, timeout=5)
            if img_response.status_code == 200:
                img_data = Image.open(BytesIO(img_response.content))
                self.image_cache[cache_key] = img_data
                self.display_image(img_data, is_foil)
                return True
        except Exception:
            pass
        return False

    def display_image(self, pil_image, is_foil=0):
        try:
            # Resize to fit preview area (maintain aspect ratio)
            target_width = 280
            aspect_ratio = pil_image.height / pil_image.width
            target_height = int(target_width * aspect_ratio)
            
            resized = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Apply foil effect if needed
            if is_foil == 1:
                resized = self.apply_foil_effect(resized)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(resized)
            
            # Display (need to keep reference to prevent garbage collection)
            self.current_image = photo
            self.after(0, lambda: self.image_label.config(image=photo, text='', compound='center'))
        except Exception as e:
            self.after(0, lambda: self.image_label.config(
                image='', text=f"Display error:\n{str(e)[:50]}", compound='center'))
    
    def apply_foil_effect(self, image):
        """Apply a holographic foil effect to the image"""
        from PIL import ImageEnhance, ImageDraw, ImageFilter
        import numpy as np
        
        print(f"Applying foil effect to image...")  # Debug output
        
        # Create a copy to work with
        foil_img = image.copy().convert('RGBA')
        width, height = foil_img.size
        
        # Create a smooth gradient overlay using numpy for better blending
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        overlay_array = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Create a smooth, organic gradient using Perlin-like noise
        for y in range(height):
            for x in range(width):
                # Use multiple sine waves to create smooth, organic color shifts
                # This avoids hard diagonal lines
                wave1 = np.sin(x * 0.02 + y * 0.015)
                wave2 = np.sin(x * 0.015 - y * 0.02)
                wave3 = np.cos(x * 0.01 + y * 0.025)
                
                # Combine waves to get smooth position in color spectrum (0 to 1)
                color_pos = ((wave1 + wave2 + wave3) / 3.0 + 1.0) / 2.0
                
                # Map to smooth rainbow spectrum using continuous HSV-like transformation
                hue = color_pos * 360  # 0-360 degrees
                
                # Convert HSV-like hue to RGB for smooth rainbow
                h = hue / 60.0
                h_int = int(h) % 6
                f = h - int(h)
                
                if h_int == 0:  # Red to Yellow
                    r, g, b = 255, int(f * 255), 0
                elif h_int == 1:  # Yellow to Green
                    r, g, b = int((1 - f) * 255), 255, 0
                elif h_int == 2:  # Green to Cyan
                    r, g, b = 0, 255, int(f * 255)
                elif h_int == 3:  # Cyan to Blue
                    r, g, b = 0, int((1 - f) * 255), 255
                elif h_int == 4:  # Blue to Magenta
                    r, g, b = int(f * 255), 0, 255
                else:  # Magenta to Red
                    r, g, b = 255, 0, int((1 - f) * 255)
                
                # Add subtle shimmer variation
                shimmer = abs(np.sin(x * 0.08 + y * 0.06)) * 0.2 + 0.8
                
                # Set pixel with moderate opacity
                overlay_array[y, x] = [
                    int(r * shimmer),
                    int(g * shimmer),
                    int(b * shimmer),
                    40  # Overall opacity
                ]
        
        # Convert array back to image
        overlay = Image.fromarray(overlay_array, 'RGBA')
        
        # Apply stronger Gaussian blur for very smooth blending
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=8))
        
        # Blend the overlay with the original image
        foil_img = Image.alpha_composite(foil_img, overlay)
        
        # Add caustic effect
        foil_img = self.add_caustic_effect(foil_img)
        
        # Increase saturation and brightness slightly for that "shiny" look
        enhancer = ImageEnhance.Color(foil_img)
        foil_img = enhancer.enhance(1.25)
        
        enhancer = ImageEnhance.Brightness(foil_img)
        foil_img = enhancer.enhance(1.12)
        
        # Add slight contrast boost
        enhancer = ImageEnhance.Contrast(foil_img)
        foil_img = enhancer.enhance(1.1)
        
        print(f"Foil effect applied successfully!")  # Debug output
        
        return foil_img.convert('RGB')
    
    def add_caustic_effect(self, image):
        """Add caustic light patterns like light through water"""
        from PIL import ImageFilter
        import numpy as np
        
        width, height = image.size
        
        # Create caustic pattern layer
        caustic = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        caustic_array = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Generate organic caustic patterns using multiple sine waves
        for y in range(height):
            for x in range(width):
                # Multiple overlapping sine waves at different frequencies
                wave1 = np.sin(x * 0.05 + y * 0.03) * 0.5 + 0.5
                wave2 = np.sin(x * 0.08 - y * 0.06) * 0.5 + 0.5
                wave3 = np.sin((x + y) * 0.04) * 0.5 + 0.5
                wave4 = np.cos(x * 0.03 + y * 0.08) * 0.5 + 0.5
                
                # Combine waves with different weights
                combined = (wave1 * 0.3 + wave2 * 0.3 + wave3 * 0.2 + wave4 * 0.2)
                
                # Create bright spots where waves align (caustic effect)
                # Use power function to create sharper bright spots
                intensity = pow(combined, 3) * 255
                
                # Only show bright caustics (threshold)
                if intensity > 120:
                    brightness = int(intensity)
                    caustic_array[y, x] = [
                        brightness,
                        brightness,
                        brightness,
                        int((intensity - 120) * 0.8)  # Varying opacity for bright spots
                    ]
        
        # Convert to image and blur for smoother caustics
        caustic = Image.fromarray(caustic_array, 'RGBA')
        caustic = caustic.filter(ImageFilter.GaussianBlur(radius=4))
        
        # Blend caustics onto the foil image
        return Image.alpha_composite(image, caustic)


    # --- Status frame ---
    def create_status_frame(self):
        self.status_frame = tk.Frame(self, bg="#23272A", relief="sunken", bd=2, height=30)
        self.status_frame.pack(fill="x", side="bottom", padx=10, pady=5)
        self.status_label = tk.Label(self.status_frame, text="Ready", bg="#23272A", fg="#FFFFFF",
                                     font=("Inter", 11), anchor="w")
        self.status_label.pack(fill="both", padx=10, pady=5)

    def update_status(self, message, msg_type="info"):
        colors = {"info": "#FFFFFF", "success": "#00FF00", "warning": "#FFD700", "error": "#FF5555"}
        self.status_label.config(text=message, fg=colors.get(msg_type, "#FFFFFF"))
        self.update_idletasks()

    # --- File menu actions ---
    def open_file(self):
        file = filedialog.askopenfilename(title="Select ManaBox Export CSV", filetypes=[("CSV Files", "*.csv")])
        if file:
            self.input_file = file
            self.update_status(f"Selected input file: {file}", "info")

    def save_converted_data(self):
        file = filedialog.asksaveasfilename(title="Save Converted CSV As", defaultextension=".csv",
                                            filetypes=[("CSV Files", "*.csv")])
        if file:
            try:
                pd.DataFrame(self.converted_data).to_csv(file, index=False)
                self.update_status("✅ File saved successfully!", "success")
            except Exception as e:
                self.update_status(f"Failed to save output CSV: {e}", "error")

    # --- Vendor / Conversion ---
    def open_vendor_link(self):
        vendor_name = self.vendor.get()
        if vendor_name in VENDOR_LINKS:
            webbrowser.open(VENDOR_LINKS[vendor_name])
        else:
            self.update_status("No link available for this vendor.", "warning")

    def start_conversion(self):
        if not hasattr(self, "input_file") or not self.input_file:
            self.update_status("Please select a CSV file first.", "warning")
            return
        try:
            self.df = pd.read_csv(self.input_file)
        except Exception as e:
            self.update_status(f"Failed to read input CSV: {e}", "error")
            return

        self.converted_data = []
        self.progress["value"] = 0
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.update_status("Converting rows...", "info")

        self.total_rows = len(self.df)
        self.progress["maximum"] = self.total_rows

        def convert_thread():
            for idx, row in self.df.iterrows():
                converted = convert_for_cardkingdom_row(row)
                self.converted_data.append(converted)
                self.progress["value"] = idx + 1
                self.update_idletasks()
            self.populate_preview()
            self.save_button.config(state="normal")
            self.update_status("Conversion complete!", "success")

        Thread(target=convert_thread).start()

    def populate_preview(self):
        self.preview_tree.delete(*self.preview_tree.get_children())
        total_qty = 0
        for row in self.converted_data:
            self.preview_tree.insert("", "end", values=(row['title'], row['edition'], row['foil'], row['quantity']))
            total_qty += row['quantity']
        self.summary_label.config(text=f"Rows: {len(self.converted_data)} | Total Quantity: {total_qty}")

    # --- Filtering & Sorting ---
    def update_filter(self, col, value):
        # Remove placeholder text before filtering
        placeholder = f"Filter {col}"
        if value == placeholder:
            value = ""
        
        self.filter_values[col] = value.lower()
        filtered = [row for row in self.converted_data
                    if all(str(row[c]).lower().find(self.filter_values[c]) != -1 for c in self.filter_values)]
        self.preview_tree.delete(*self.preview_tree.get_children())
        total_qty = 0
        for row in filtered:
            self.preview_tree.insert("", "end", values=(row['title'], row['edition'], row['foil'], row['quantity']))
            total_qty += row['quantity']
        self.summary_label.config(text=f"Rows: {len(filtered)} | Total Quantity: {total_qty}")

    def sort_preview(self, col):
        reverse = not self.sort_state[col]
        self.sort_state[col] = reverse
        self.converted_data.sort(key=lambda x: x[col], reverse=reverse)
        self.populate_preview()

if __name__ == "__main__":
    app = ManaBoxConverterApp()
    app.mainloop()
