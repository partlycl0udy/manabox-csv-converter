import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, Menu, messagebox
import webbrowser
from threading import Thread
import time

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
        self.title("ManaBox CSV Converter V3")
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
        button_frame.pack(fill="x", pady=10)
        StyledButton(button_frame, text="Select File", bg="#FFA500", hover_bg="#FFB84D",
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

        # Treeview
        self.preview_tree = ttk.Treeview(preview_frame, columns=("title", "edition", "foil", "quantity"), show="headings")
        for col in ("title", "edition", "foil", "quantity"):
            self.preview_tree.heading(col, text=f"{col.capitalize()} ↑↓", command=lambda c=col: self.sort_preview(c))
            self.preview_tree.column(col, width=150, anchor="center")
        self.preview_tree.pack(fill="both", expand=True, side="left")
        scroll_y = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscroll=scroll_y.set)
        scroll_y.pack(fill="y", side="right")

        # Summary label
        self.summary_label = tk.Label(self, text="Rows: 0 | Total Quantity: 0", bg="#2C2F33", fg="#FFFFFF", font=self.font)
        self.summary_label.pack(anchor="w", padx=25, pady=(0,10))

    # --- Status frame ---
    def create_status_frame(self):
        self.status_frame = tk.Frame(self, bg="#23272A", relief="sunken", bd=2, height=30)
        self.status_frame.pack(fill="x", side="bottom")
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
