import tkinter as tk
from tkinter import filedialog, messagebox, font
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import io  # For handling image data
from PIL import Image, ImageTk  # For displaying images in Tkinter

class ComplexTextEditorWithCharts:
    def __init__(self, root):
        self.root = root
        self.root.title("Complex Tkinter Text Editor with Charts")

        self.text_area = tk.Text(self.root, wrap=tk.WORD, undo=True)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()

        self.current_file = None
        self.default_font = font.Font(family="Arial", size=12)
        #self.bold_font = font.Font(self.default_font, weight="bold")
        #self.italic_font = font.Font(self.default_font, slant="italic")

        self.text_area.configure(font=self.default_font)
        #self.text_area.tag_configure("bold", font=self.bold_font)
        #self.text_area.tag_configure("italic", font=self.italic_font)

    def create_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self.new_file)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_editor)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.text_area.edit_undo)
        edit_menu.add_command(label="Redo", command=self.text_area.edit_redo)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        format_menu = tk.Menu(menubar, tearoff=0)
        format_menu.add_command(label="Bold", command=self.toggle_bold)
        format_menu.add_command(label="Italic", command=self.toggle_italic)
        menubar.add_cascade(label="Format", menu=format_menu)

        visualize_menu = tk.Menu(menubar, tearoff=0)
        visualize_menu.add_command(label="Show Line Graph", command=self.show_line_graph)
        visualize_menu.add_command(label="Show Bar Chart", command=self.show_bar_chart)
        visualize_menu.add_command(label="Show Equation", command=self.show_equation)
        menubar.add_cascade(label="Visualize", menu=visualize_menu)

        self.root.config(menu=menubar)

    def create_toolbar(self):
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        bold_button = tk.Button(toolbar, text="B", font=("Arial", 12, "bold"), command=self.toggle_bold)
        bold_button.pack(side=tk.LEFT, padx=2, pady=2)

        italic_button = tk.Button(toolbar, text="I", font=("Arial", 12, "italic"), command=self.toggle_italic)
        italic_button.pack(side=tk.LEFT, padx=2, pady=2)

    def create_statusbar(self):
        self.statusbar = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def new_file(self):
        self.text_area.delete(1.0, tk.END)
        self.current_file = None
        self.root.title("Complex Tkinter Text Editor with Charts")
        self.update_statusbar("New file created")

    def open_file(self):
        filepath = filedialog.askopenfilename(defaultextension=".txt",
                                               filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filepath:
            try:
                with open(filepath, "r") as file:
                    content = file.read()
                    self.text_area.delete(1.0, tk.END)
                    self.text_area.insert(tk.END, content)
                    self.current_file = filepath
                    self.root.title(f"Complex Tkinter Text Editor with Charts - {os.path.basename(filepath)}")
                    self.update_statusbar(f"Opened: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")

    def save_file(self):
        if self.current_file:
            try:
                content = self.text_area.get(1.0, tk.END)
                with open(self.current_file, "w") as file:
                    file.write(content)
                    self.update_statusbar(f"Saved: {self.current_file}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{e}")
        else:
            self.save_file_as()

    def save_file_as(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".txt",
                                                   filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filepath:
            try:
                content = self.text_area.get(1.0, tk.END)
                with open(filepath, "w") as file:
                    file.write(content)
                    self.current_file = filepath
                    self.root.title(f"Complex Tkinter Text Editor with Charts - {os.path.basename(filepath)}")
                    self.update_statusbar(f"Saved as: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file:\n{e}")

    def exit_editor(self):
        if messagebox.askyesno("Confirm Exit", "Do you want to exit?"):
            self.root.destroy()

    def toggle_bold(self):
        try:
            current_tags = self.text_area.tag_names(tk.SEL_FIRST)
            if "bold" in current_tags:
                self.text_area.tag_remove("bold", tk.SEL_FIRST, tk.SEL_LAST)
            else:
                self.text_area.tag_add("bold", tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass  # No text selected

    def toggle_italic(self):
        try:
            current_tags = self.text_area.tag_names(tk.SEL_FIRST)
            if "italic" in current_tags:
                self.text_area.tag_remove("italic", tk.SEL_FIRST, tk.SEL_LAST)
            else:
                self.text_area.tag_add("italic", tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass  # No text selected

    def update_statusbar(self, message):
        self.statusbar.config(text=message)

    def show_line_graph(self):
        top = tk.Toplevel(self.root)
        top.title("Line Graph")

        # Sample data for the line graph
        x = np.linspace(0, 10, 50)
        y = np.sin(x)

        figure = plt.Figure(figsize=(6, 4), dpi=100)
        subplot = figure.add_subplot(111)
        subplot.plot(x, y)
        subplot.set_xlabel("X-axis")
        subplot.set_ylabel("Y-axis")
        subplot.set_title("Sample Line Graph")

        canvas = FigureCanvasTkAgg(figure, master=top)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def show_bar_chart(self):
        top = tk.Toplevel(self.root)
        top.title("Bar Chart")

        # Sample data for the bar chart
        categories = ['A', 'B', 'C', 'D', 'E']
        values = [20, 35, 30, 45, 25]

        figure = plt.Figure(figsize=(6, 4), dpi=100)
        subplot = figure.add_subplot(111)
        subplot.bar(categories, values)
        subplot.set_xlabel("Categories")
        subplot.set_ylabel("Values")
        subplot.set_title("Sample Bar Chart")

        canvas = FigureCanvasTkAgg(figure, master=top)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def show_equation(self):
        top = tk.Toplevel(self.root)
        top.title("Equation")

        # The LaTeX equation you want to display
        equation = r'$E = mc^2$'

        # Create a Matplotlib figure without any axes
        fig = plt.figure(figsize=(4, 2), dpi=100)
        fig.text(0.1, 0.5, equation, fontsize=20)  # Adjust position and fontsize as needed

        # Save the figure to an in-memory buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        buf.seek(0)

        # Open the image using Pillow (PIL) and display it in Tkinter
        img = Image.open(buf)
        img_tk = ImageTk.PhotoImage(img)

        label = tk.Label(top, image=img_tk)
        label.image = img_tk  # Keep a reference!
        label.pack(padx=10, pady=10)

        plt.close(fig) # Close the Matplotlib figure to free resources
if __name__ == "__main__":
    root = tk.Tk()
    editor = ComplexTextEditorWithCharts(root)
    root.mainloop()
# Create main window
#root = tk.Tk()
#root.title("Simple GUI")
#root.geometry("300x200")

# Function for button click event
#def on_button_click():
#    messagebox.showinfo("Hello", "You clicked the button!")

# Create a button
#button = tk.Button(root, text="Click Me", command=on_button_click)
#button.pack(pady=20)

# Run the application
#root.mainloop()