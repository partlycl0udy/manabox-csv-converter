import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog
import webbrowser

# Vendor data
VENDORS = ["Card Kingdom", "TCGPlayer", "Card Conduit", "Star City Games"]
VENDOR_LINKS = {
    "Card Kingdom": "https://www.cardkingdom.com/static/csvImport",
    "TCGPlayer": "https://seller.tcgplayer.com/sell-with-us/marketplace",
    "Card Conduit": "https://cardconduit.com/estimates/create",
    "Star City Games": "https://sellyourcards.starcitygames.com/mtg/upload"  
}

def convert_for_cardkingdom_row(row):
    """Convert a single row for Card Kingdom."""
    title = str(row.get('Name', '')).split("//")[0].strip()
    edition = row.get('Set name', '')
    foil = 1 if str(row.get('Foil', '')).strip().lower() == 'foil' else 0
    qty = row.get('Quantity', 0)
    return {'title': title, 'edition': edition, 'foil': foil, 'quantity': qty}

def convert_placeholder_row(row, vendor_name):
    return None  # Not implemented yet

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

class ManaBoxConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ManaBox CSV Converter by Phil Harris 2025")
        self.geometry("1100x750")
        self.minsize(950, 600)
        self.configure(bg="#2C2F33")

        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.vendor = tk.StringVar(value="Card Kingdom")
        self.font = ("Inter", 12)

        self.df = None
        self.converted_data = []
        self.filter_values = {"title": "", "edition": "", "foil": "", "quantity": ""}
        self.sort_state = {"title": False, "edition": False, "foil": False, "quantity": False}

        self.create_widgets()
        self.create_progress_bar()
        self.create_preview_pane()
        self.create_status_frame()

    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        for i in range(9):
            self.grid_rowconfigure(i, weight=1)

        header = tk.Label(self, text="ManaBox CSV Converter", font=("Inter", 18, "bold"),
                          bg="#2C2F33", fg="#FFD700")
        header.grid(row=0, column=0, pady=(15,10))

        # Input frame
        input_frame = tk.LabelFrame(self, text="Input File", bg="#2C2F33", fg="#FFFFFF",
                                    font=self.font, padx=10, pady=10)
        input_frame.grid(row=1, column=0, padx=20, pady=(10,5), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        self.input_entry = tk.Entry(input_frame, textvariable=self.input_file, font=self.font)
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0,10))
        StyledButton(input_frame, text="Browse", bg="#7289DA", hover_bg="#99AAB5",
                     command=self.browse_input).grid(row=0, column=1)

        # Output frame
        output_frame = tk.LabelFrame(self, text="Output File", bg="#2C2F33", fg="#FFFFFF",
                                     font=self.font, padx=10, pady=10)
        output_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        output_frame.grid_columnconfigure(0, weight=1)
        self.output_entry = tk.Entry(output_frame, textvariable=self.output_file, font=self.font)
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0,10))
        StyledButton(output_frame, text="Save As", bg="#7289DA", hover_bg="#99AAB5",
                     font=("Inter", 11, "bold"), command=self.browse_output).grid(row=0, column=1)

        # Vendor frame (moved below output)
        vendor_frame = tk.LabelFrame(self, text="Vendor Selection", bg="#2C2F33", fg="#FFFFFF",
                                     font=self.font, padx=10, pady=10)
        vendor_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        vendor_frame.grid_columnconfigure(0, weight=1)
        ttk.Combobox(vendor_frame, textvariable=self.vendor, values=VENDORS,
                     state="readonly", font=self.font).grid(row=0, column=0, sticky="ew", padx=(0,10))
        StyledButton(vendor_frame, text="Open Vendor Page", bg="#43B581", hover_bg="#66CDAA",
                     font=("Inter", 11, "bold"), command=self.open_vendor_link).grid(row=0, column=1)

        # Buttons frame
        button_frame = tk.Frame(self, bg="#2C2F33")
        button_frame.grid(row=4, column=0, pady=15)
        StyledButton(button_frame, text="Convert & Preview", bg="#F04747", hover_bg="#FF6F61",
                     font=("Inter", 14, "bold"), command=self.start_conversion).pack(side="left", padx=20)
        self.save_button = StyledButton(button_frame, text="Save Converted CSV", bg="#7289DA", hover_bg="#99AAB5",
                                        font=("Inter", 14, "bold"), command=self.save_converted_data, state="disabled")
        self.save_button.pack(side="left", padx=20)

    def create_progress_bar(self):
        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.grid(row=5, column=0, sticky="ew", padx=20, pady=(0,10))

    def create_preview_pane(self):
        preview_frame = tk.LabelFrame(self, text="Preview Converted Data", bg="#2C2F33", fg="#FFFFFF",
                                      font=self.font, padx=10, pady=10)
        preview_frame.grid(row=6, column=0, padx=20, pady=10, sticky="nsew")
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(1, weight=1)

        # Filter row
        filter_frame = tk.Frame(preview_frame, bg="#2C2F33")
        filter_frame.grid(row=0, column=0, sticky="ew")
        for idx, col in enumerate(("title", "edition", "foil", "quantity")):
            entry = tk.Entry(filter_frame, width=15)
            entry.grid(row=0, column=idx, padx=5)
            entry.insert(0, f"Filter {col}")
            entry.bind("<FocusIn>", lambda e, ent=entry: ent.delete(0, "end"))
            entry.bind("<KeyRelease>", lambda e, col=col, ent=entry: self.update_filter(col, ent.get()))

        # Treeview
        self.preview_tree = ttk.Treeview(preview_frame, columns=("title", "edition", "foil", "quantity"), show="headings")
        for col in ("title", "edition", "foil", "quantity"):
            self.preview_tree.heading(col, text=col.capitalize(), command=lambda c=col: self.sort_preview(c))
            self.preview_tree.column(col, width=150, anchor="center")
        self.preview_tree.grid(row=1, column=0, sticky="nsew")

        scroll_y = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscroll=scroll_y.set)
        scroll_y.grid(row=1, column=1, sticky="ns")

    def create_status_frame(self):
        self.status_frame = tk.Frame(self, bg="#23272A", relief="sunken", bd=2, height=30)
        self.status_frame.grid(row=8, column=0, sticky="ew")
        self.status_label = tk.Label(self.status_frame, text="Ready", bg="#23272A", fg="#FFFFFF",
                                     font=("Inter", 11), anchor="w")
        self.status_label.pack(fill="both", padx=10, pady=5)

    def update_status(self, message, msg_type="info"):
        colors = {"info": "#FFFFFF", "success": "#00FF00", "warning": "#FFD700", "error": "#FF5555"}
        self.status_label.config(text=message, fg=colors.get(msg_type, "#FFFFFF"))
        self.update_idletasks()

    def browse_input(self):
        file = filedialog.askopenfilename(title="Select ManaBox Export CSV", filetypes=[("CSV Files", "*.csv")])
        if file:
            self.input_file.set(file)
            self.update_status(f"Selected input file: {file}", "info")

    def browse_output(self):
        file = filedialog.asksaveasfilename(title="Save Converted CSV As", defaultextension=".csv",
                                            filetypes=[("CSV Files", "*.csv")])
        if file:
            self.output_file.set(file)
            self.update_status(f"Output will be saved to: {file}", "info")

    def open_vendor_link(self):
        vendor_name = self.vendor.get()
        if vendor_name in VENDOR_LINKS:
            webbrowser.open(VENDOR_LINKS[vendor_name])
        else:
            self.update_status("No link available for this vendor.", "warning")

    def start_conversion(self):
        if not self.input_file.get():
            self.update_status("Please select an input file.", "warning")
            return

        try:
            self.df = pd.read_csv(self.input_file.get())
        except Exception as e:
            self.update_status(f"Failed to read input CSV: {e}", "error")
            return

        self.converted_data = []
        self.progress["value"] = 0
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.update_status("Converting rows...", "info")

        self.total_rows = len(self.df)
        self.current_row = 0
        self.save_button.config(state="disabled")
        self.convert_next_row()

    def convert_next_row(self):
        if self.current_row < self.total_rows:
            row = self.df.iloc[self.current_row]
            vendor = self.vendor.get().lower().replace(" ", "")
            if vendor == "cardkingdom":
                converted_row = convert_for_cardkingdom_row(row)
            else:
                converted_row = convert_placeholder_row(row, self.vendor.get())

            if converted_row:
                self.converted_data.append(converted_row)
                self.preview_tree.insert("", "end", values=(
                    converted_row['title'], converted_row['edition'],
                    converted_row['foil'], converted_row['quantity']
                ))

            self.current_row += 1
            self.progress["value"] = (self.current_row / self.total_rows) * 100
            self.after(10, self.convert_next_row)
        else:
            self.update_status("Conversion complete!", "success")
            self.save_button.config(state="normal")

    def save_converted_data(self):
        if not self.output_file.get():
            self.update_status("Please select an output file.", "warning")
            return

        try:
            pd.DataFrame(self.converted_data).to_csv(self.output_file.get(), index=False)
            self.update_status("✅ File saved successfully!", "success")
        except Exception as e:
            self.update_status(f"Failed to save output CSV: {e}", "error")

    def update_filter(self, column, value):
        self.filter_values[column] = value.lower()
        self.refresh_preview()

    def refresh_preview(self):
        self.preview_tree.delete(*self.preview_tree.get_children())
        for row in self.converted_data:
            if all(str(row[col]).lower().find(self.filter_values[col]) != -1 or self.filter_values[col] == "" for col in self.filter_values):
                self.preview_tree.insert("", "end", values=(row['title'], row['edition'], row['foil'], row['quantity']))

    def sort_preview(self, column):
        self.sort_state[column] = not self.sort_state[column]
        reverse = self.sort_state[column]
        self.converted_data.sort(key=lambda x: str(x[column]).lower(), reverse=reverse)
        self.refresh_preview()

if __name__ == "__main__":
    app = ManaBoxConverterApp()
    app.mainloop()
